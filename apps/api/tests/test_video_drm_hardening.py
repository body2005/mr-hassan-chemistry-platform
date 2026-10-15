"""Synthetic DRM preparation regressions; no provider or production objects."""
import base64
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.config import get_settings
from app.models.video_upload import VideoUpload
from app.services import video_drm, video_drm_packaging
from test_video_protection import _setup_world


def ready_generation(db, lesson, teacher, *, qualified=False):
    manifest = f"video-hls/{uuid.uuid4()}/master.m3u8"
    asset = VideoUpload(
        lesson_id=lesson.id, owner_id=teacher.id, request_key=uuid.uuid4().hex,
        filename="synthetic.mp4", content_type="video/mp4", size_bytes=64,
        fingerprint="0" * 64, object_key=f"video-originals/{uuid.uuid4()}.mp4",
        status="ready", expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        manifest_key=manifest, outputs=[manifest],
    )
    db.add(asset)
    lesson.video_asset_key = f"s3://private/{manifest}" if qualified else manifest
    db.commit()
    return asset


@pytest.mark.parametrize("qualified", [False, True])
def test_current_generation_accepts_exact_local_or_s3_pointer(db, tmp_path, monkeypatch, qualified):
    _, teacher, _, _, lesson = _setup_world(db, tmp_path, monkeypatch)
    asset = ready_generation(db, lesson, teacher, qualified=qualified)
    assert video_drm.current_asset(db, lesson).id == asset.id


def test_hls_local_generation_does_not_fall_back_to_progressive(db, tmp_path, monkeypatch):
    from app.api.routes import platform, video_uploads
    _, teacher, _, _, lesson = _setup_world(db, tmp_path, monkeypatch)
    asset = ready_generation(db, lesson, teacher)
    monkeypatch.setattr(platform, "_authorize_video_stream", lambda *args: lesson)
    manifest = b"#EXTM3U\n"
    provider = SimpleNamespace(get_size=lambda key: len(manifest), open_stream=lambda key, **kwargs: iter([manifest]))
    monkeypatch.setattr("app.core.storage.get_storage_provider", lambda: provider)
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    response = video_uploads.hls(lesson.id, asset.id, "master.m3u8", request, db, "synthetic")
    assert response.status_code == 200
    assert response.body == manifest


def test_local_hls_remains_available_while_drm_replacement_is_queued(db, tmp_path, monkeypatch):
    from app.services.lesson_release import lesson_is_available
    from app.models.course import Course
    _, teacher, _, _, lesson = _setup_world(db, tmp_path, monkeypatch)
    ready_generation(db, lesson, teacher)
    replacement = VideoUpload(
        lesson_id=lesson.id, owner_id=teacher.id, request_key=uuid.uuid4().hex,
        filename="synthetic.mp4", content_type="video/mp4", size_bytes=64,
        fingerprint="0" * 64, object_key="video-originals/synthetic.mp4",
        status="queued", expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        drm={"requested": True, "replaces": lesson.video_asset_key}, outputs=[],
    )
    db.add(replacement); db.commit()
    assert lesson_is_available(db, lesson, db.get(Course, lesson.course_id)) is True


def package_command(tmp_path, monkeypatch, *, fail=False):
    clear, output = tmp_path / "clear", tmp_path / "encrypted"
    (clear / "360p").mkdir(parents=True)
    (clear / "360p/index.m3u8").write_text("#EXTM3U\n")
    packager = tmp_path / "packager"
    packager.write_bytes(b"synthetic-not-executed")
    monkeypatch.setattr(get_settings(), "video_drm_packager_path", str(packager))
    monkeypatch.setattr(video_drm_packaging.os, "access", lambda *args: True)
    metadata = {"key_id": str(uuid.uuid4()), "iv": base64.b64encode(b"i" * 16).decode()}
    raw_key = b"s" * 16
    monkeypatch.setattr(video_drm_packaging, "new_content_key", lambda: (raw_key, metadata))
    # The test may run on Windows, unlike the production Linux worker.
    actual_mkstemp = video_drm_packaging.tempfile.mkstemp
    monkeypatch.setattr(video_drm_packaging.tempfile, "mkstemp", lambda **kw: actual_mkstemp(
        **{**kw, "dir": tmp_path}))
    commands, flags = [], []
    def run(argv, *args, **kwargs):
        commands.append(argv)
        for arg in argv:
            if arg.startswith("--flagfile="):
                path = Path(arg.partition("=")[2]); flags.append(path)
                assert raw_key.hex() in path.read_text()
                assert all(raw_key.hex() not in arg for arg in argv)
                if fail:
                    raise video_drm_packaging.InvalidVideo("synthetic failure")
    monkeypatch.setattr(video_drm_packaging, "_run", run)
    monkeypatch.setattr(video_drm_packaging, "validate_output", lambda *args: ["master.m3u8"])
    if fail:
        with pytest.raises(video_drm_packaging.InvalidVideo):
            video_drm_packaging.package(clear, output, {"duration": 12, "has_audio": False})
    else:
        video_drm_packaging.package(clear, output, {"duration": 12, "has_audio": False})
    return commands, flags


def test_packaging_encrypts_from_first_segment_without_default_clear_lead(tmp_path, monkeypatch):
    commands, flags = package_command(tmp_path, monkeypatch)
    assert "--clear_lead=0" in commands[-1]
    assert flags and all(not path.exists() for path in flags)


def test_packaging_erases_private_key_flags_even_after_failure(tmp_path, monkeypatch):
    _, flags = package_command(tmp_path, monkeypatch, fail=True)
    assert flags and all(not path.exists() for path in flags)


def test_license_entitlement_is_nonpersistent_and_expires_with_lesson(monkeypatch):
    import jwt
    key_id, communication_id = str(uuid.uuid4()), str(uuid.uuid4())
    secret = b"synthetic-communication-key-12345!"
    monkeypatch.setattr(video_drm, "communication_key", lambda identity=None: (communication_id, secret))
    end = datetime.now(timezone.utc) + timedelta(seconds=60)
    asset = SimpleNamespace(drm={"provider": "axinom", "scheme": "cbcs", "key_id": key_id,
        "encrypted_key": "synthetic-wrapped-key", "iv": "synthetic-iv", "communication_key_id": communication_id})
    lesson = SimpleNamespace(available_until=end)
    token = video_drm.license_message(asset, lesson, "synthetic-student")
    message = jwt.decode(token, secret, algorithms=["HS256"])
    policy = message["message"]["license"]
    assert policy["allow_persistence"] is False
    assert datetime.fromisoformat(policy["expiration_datetime"]) == end
    lesson.available_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(HTTPException) as denied:
        video_drm.license_message(asset, lesson, "synthetic-student")
    assert denied.value.status_code == 403
