import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from sqlalchemy import select
from test_video_protection import _setup_world

from app.models.storage_cleanup import StorageCleanup
from app.models.video_upload import VideoUpload
from scripts import video_worker as worker


@pytest.mark.parametrize(
    "reprocess,fail_finalize,legacy_source_pointer",
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, False, True),
    ],
)
def test_finalize_retains_verified_private_source_without_copy_or_shared_source_cleanup(
    db, tmp_path, monkeypatch, reprocess, fail_finalize, legacy_source_pointer
):
    _, teacher, _, _, lesson = _setup_world(db, tmp_path, monkeypatch)
    source = "video-staging/verified/source.mp4"
    source_bytes = b"verified private original"
    remote = {source: source_bytes}
    if legacy_source_pointer:
        lesson.video_asset_key = f"s3://private/{source}"
    client = MagicMock()
    client.copy_object.side_effect = ReadTimeoutError(endpoint_url="https://private.invalid")

    def get_size(key):
        if fail_finalize and key == source:
            raise ReadTimeoutError(endpoint_url="https://private.invalid/?secret=redacted")
        if key not in remote:
            raise FileNotFoundError("Stored object is missing")
        return len(remote[key])

    storage = SimpleNamespace(
        bucket_name="private",
        open_stream=lambda key: iter([remote[key]]),
        get_size=get_size,
        _get_client=lambda: client,
    )
    saved = []

    def save_file(path, key, media):
        saved.append(key)
        remote[key] = Path(path).read_bytes()

    storage.save_file = save_file
    if reprocess:
        previous = VideoUpload(
            id=uuid.uuid4(),
            lesson_id=lesson.id,
            owner_id=teacher.id,
            request_key=uuid.uuid4().hex,
            filename="original.mp4",
            content_type="video/mp4",
            size_bytes=len(source_bytes),
            fingerprint="a" * 64,
            object_key=source,
            status="ready",
            expires_at=datetime.now(UTC) + timedelta(days=2),
            manifest_key="video-assets/old/master.m3u8",
            outputs=[
                f"s3://private/{source}" if legacy_source_pointer else source,
                "video-assets/old/master.m3u8",
            ],
        )
        if not legacy_source_pointer:
            lesson.video_asset_key = "s3://private/video-assets/old/master.m3u8"
        db.add(previous)
    job = VideoUpload(
        id=uuid.uuid4(),
        lesson_id=lesson.id,
        owner_id=teacher.id,
        request_key=uuid.uuid4().hex,
        filename="source.mp4",
        content_type="video/mp4",
        size_bytes=len(source_bytes),
        fingerprint="a" * 64,
        object_key=source,
        status="queued",
        expires_at=datetime.now(UTC) + timedelta(days=2),
        outputs=[],
    )
    db.add(job)
    db.commit()
    identity = job.id
    monkeypatch.setattr(worker, "get_storage_provider", lambda: storage)
    guard = MagicMock()
    guard.scalar.return_value = True
    engine = MagicMock()
    engine.connect.return_value.execution_options.return_value.__enter__.return_value = guard
    monkeypatch.setattr(worker, "engine", engine)
    temporary_directory = worker.tempfile.TemporaryDirectory
    monkeypatch.setattr(
        worker.tempfile,
        "TemporaryDirectory",
        lambda prefix, dir: temporary_directory(prefix=prefix, dir=tmp_path),
    )
    monkeypatch.setattr(
        worker.shutil, "disk_usage", lambda path: SimpleNamespace(free=100 * 1024**3)
    )

    def encode(source_path, output, progress):
        assert source_path.read_bytes() == source_bytes
        output.mkdir()
        (output / "master.m3u8").write_text("#EXTM3U\n")
        (output / "segment.ts").write_bytes(b"encoded segment")
        return {"duration": 9000}, ["master.m3u8", "segment.ts"]

    encoder = MagicMock(side_effect=encode)
    monkeypatch.setattr(worker, "encode", encoder)
    worker.process(identity)
    db.expire_all()
    result = db.get(VideoUpload, identity)
    if fail_finalize:
        assert result.status == "queued" and result.outputs == []
        assert result.object_key == source and remote[source] == source_bytes
    else:
        assert result.status == "ready" and result.processing_percent == 100
        assert result.object_key == source and source in result.outputs
        assert result.duration_seconds == 9000
    client.copy_object.assert_not_called()
    cleanup = list(db.scalars(select(StorageCleanup.object_key)))
    assert source not in cleanup
    assert f"s3://private/{source}" not in cleanup
    if reprocess:
        assert db.get(VideoUpload, previous.id).status == "superseded"
        assert "video-assets/old/master.m3u8" in cleanup


def test_worker_error_diagnostics_never_include_provider_messages_or_signed_urls():
    error = ClientError(
        {"Error": {"Code": "SlowDown", "Message": "https://private.invalid/?token=secret"}},
        "CopyObject",
    )
    assert worker.failure_diagnostic(error) == ("ClientError", "SlowDown")
    error.response["Error"]["Code"] = "https://private.invalid/?token=secret"
    assert worker.failure_diagnostic(error) == ("ClientError", "unknown")
    assert worker.failure_diagnostic(
        ReadTimeoutError(endpoint_url="https://private.invalid/?token=secret")
    ) == ("ReadTimeoutError", "unknown")
