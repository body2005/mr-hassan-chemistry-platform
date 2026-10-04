import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.storage import S3StorageProvider
from app.models.video_upload import VideoUpload
from app.services import video_uploads as service
from app.services.video_processing import renditions
from test_video_protection import _setup_world, _login, _csrf


@pytest.fixture
def world(db, tmp_path, monkeypatch):
    inst, teacher, student, other, lesson = _setup_world(db, tmp_path, monkeypatch)
    provider = S3StorageProvider(endpoint_url="http://s3:8333", bucket_name="test", access_key_id="test", secret_access_key="test", region_name="us-east-1")
    client = MagicMock()
    provider._client = client
    client.get_paginator.return_value.paginate.return_value = [{}]
    client.create_multipart_upload.return_value = {"UploadId": "private-upload-identity"}
    monkeypatch.setattr(service, "storage", lambda: provider)
    return inst, teacher, student, other, lesson, provider, client


def payload(size=service.PART_BYTES + 20):
    return SimpleNamespace(filename="lecture.mp4", content_type="video/mp4", size_bytes=size, fingerprint="a" * 64, request_key=uuid.uuid4().hex)


def test_upload_retry_ownership_and_quota(db, world):
    _, teacher, student, _, lesson, _, client = world
    data = payload()
    first = service.create(db, teacher, lesson, data)
    service.initialize(db, first)
    assert service.create(db, teacher, lesson, data).id == first.id
    assert client.create_multipart_upload.call_count == 1
    assert service.summary(first)["status"] == "uploading"
    assert "object_key" not in service.summary(first)
    with pytest.raises(HTTPException) as result:
        service.owned(db, first.id, student)
    assert result.value.status_code == 404
    with pytest.raises(HTTPException) as result:
        service.create(db, teacher, lesson, payload())
    assert result.value.status_code == 409


def test_completion_uses_actual_parts_and_is_idempotent(db, world):
    _, teacher, _, _, lesson, _, client = world
    upload = service.create(db, teacher, lesson, payload())
    service.initialize(db, upload)
    client.get_paginator.return_value.paginate.return_value = [{"Parts": [
        {"PartNumber": 1, "Size": service.PART_BYTES, "ETag": "etag1"},
        {"PartNumber": 2, "Size": 19, "ETag": "etag2"}]}]
    with pytest.raises(HTTPException) as result:
        service.complete(db, upload)
    assert result.value.status_code == 409
    client.complete_multipart_upload.assert_not_called()
    client.get_paginator.return_value.paginate.return_value[0]["Parts"][1]["Size"] = 20
    service.complete(db, upload)
    service.complete(db, upload)
    assert upload.status == "queued"
    assert client.complete_multipart_upload.call_count == 1
    assert lesson.video_asset_key is None  # Quarantine is never playable.


def test_crash_after_storage_complete_recovers(db, world):
    _, teacher, _, _, lesson, _, client = world
    upload = service.create(db, teacher, lesson, payload())
    service.initialize(db, upload)
    upload.status = "completing"
    db.commit()
    client.head_object.return_value = {"ContentLength": upload.size_bytes, "Metadata": {"video-id": str(upload.id)}}
    service.complete(db, upload)
    assert upload.status == "queued"
    client.complete_multipart_upload.assert_not_called()


def test_crash_after_allocation_reuses_multipart_identity(db, world):
    _, teacher, _, _, lesson, _, client = world
    upload = service.create(db, teacher, lesson, payload())
    client.get_paginator.return_value.paginate.return_value = [{"Uploads": [{"Key": upload.object_key, "UploadId": "existing"}]}]
    service.initialize(db, upload)
    assert upload.multipart_id == "existing"
    client.create_multipart_upload.assert_not_called()


@pytest.mark.parametrize("size", [0, service.MAX_VIDEO_BYTES + 1])
def test_upload_size_policy(size):
    with pytest.raises(HTTPException) as result:
        service.validate_upload("lecture.mp4", size, "video/mp4", "a" * 64, "identity123")
    assert result.value.status_code == 413


def test_content_type_matches_extension():
    with pytest.raises(HTTPException) as result:
        service.validate_upload("lecture.webm", 100, "video/mp4", "a" * 64, "identity123")
    assert result.value.status_code == 422


def test_expired_completion_cannot_enter_queue(db, world):
    _, teacher, _, _, lesson, _, client = world
    upload = service.create(db, teacher, lesson, payload())
    service.initialize(db, upload)
    upload.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    with pytest.raises(HTTPException) as result:
        service.complete(db, upload)
    assert result.value.status_code == 409
    client.complete_multipart_upload.assert_not_called()


def test_missing_storage_session_can_restart_after_storage_loss(db, world):
    from botocore.exceptions import ClientError
    from fastapi.testclient import TestClient
    from app.main import app
    inst, teacher, _, _, lesson, _, storage_client = world
    upload = service.create(db, teacher, lesson, payload())
    service.initialize(db, upload)
    storage_client.get_paginator.return_value.paginate.side_effect = ClientError(
        {"Error": {"Code": "NoSuchUpload", "Message": "QA missing multipart session"}}, "ListParts")
    browser = TestClient(app, raise_server_exceptions=False)
    _login(browser, teacher, inst.slug)
    response = browser.get(f"/api/v1/video-uploads/{upload.id}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "expired"
    assert response.json()["error_code"] == "VIDEO_UPLOAD_STORAGE_SESSION_LOST"


def test_missing_parts_do_not_queue_and_outages_are_not_expiry(db, world):
    from botocore.exceptions import ClientError
    _, teacher, _, _, lesson, _, storage_client = world
    upload = service.create(db, teacher, lesson, payload())
    service.initialize(db, upload)
    paginator = storage_client.get_paginator.return_value
    paginator.paginate.side_effect = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "ListParts")
    with pytest.raises(ClientError):
        service.recover_parts(db, upload)
    assert upload.status == "uploading"
    paginator.paginate.side_effect = ClientError({"Error": {"Code": "NoSuchUpload"}}, "ListParts")
    with pytest.raises(HTTPException) as result:
        service.complete(db, upload)
    assert result.value.status_code == 409 and upload.status == "expired"
    storage_client.complete_multipart_upload.assert_not_called()


def test_part_signatures_are_upload_only_exact_size_and_short_lived(world, monkeypatch):
    _, teacher, _, _, lesson, _, _ = world
    monkeypatch.setattr(get_settings(), "video_upload_public_endpoint", "https://upload.example.test")
    upload = VideoUpload(id=uuid.uuid4(), lesson_id=lesson.id, owner_id=teacher.id, size_bytes=service.PART_BYTES + 20,
        object_key="video-staging/unit/source.mp4", multipart_id="secret-id", status="uploading", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    signed = service.sign_part(upload, 2)
    from urllib.parse import parse_qs, urlsplit
    url = urlsplit(signed["url"])
    query = parse_qs(url.query)
    assert url.netloc == "upload.example.test"
    assert "content-length" in query["X-Amz-SignedHeaders"][0]
    assert query["X-Amz-Expires"] == ["300"]
    assert signed["size_bytes"] == 20
    with pytest.raises(HTTPException):
        service.sign_part(upload, 3)


def test_ladder_does_not_upscale():
    assert [height for height, _ in renditions(720)] == [360, 480, 720]
    assert [height for height, _ in renditions(240)] == [240]
    assert [height for height, _ in renditions(2160)] == [360, 480, 720, 1080, 2160]


def test_hls_authentication_checks_every_manifest_and_segment(db, world, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    inst, teacher, student, _, lesson, provider, client = world
    job = VideoUpload(id=uuid.uuid4(), lesson_id=lesson.id, owner_id=teacher.id, request_key=uuid.uuid4().hex,
        filename="video.mp4", content_type="video/mp4", size_bytes=100, fingerprint="a" * 64,
        object_key="video-staging/test", status="ready", expires_at=datetime.now(timezone.utc),
        manifest_key="video-assets/test/master.m3u8", outputs=["video-assets/test/master.m3u8", "video-assets/test/360p/index.m3u8", "video-assets/test/360p/segment_000000.ts"])
    db.add(job)
    lesson.video_asset_key = "s3://test/video-assets/test/master.m3u8"
    db.commit()
    manifest = b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000\n360p/index.m3u8\n"
    monkeypatch.setattr(provider, "get_size", lambda key: len(manifest))
    monkeypatch.setattr(provider, "open_stream", lambda key, **kwargs: iter([manifest]))
    monkeypatch.setattr("app.core.storage.get_storage_provider", lambda: provider)
    browser = TestClient(app)
    _login(browser, student, inst.slug)
    issued = browser.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=_csrf(browser))
    assert issued.status_code == 200, issued.text
    url = issued.json()["stream_url"]
    assert issued.json()["format"] == "hls"
    response = browser.get(url)
    assert response.status_code == 200, response.text
    assert "?token=" in response.text
    assert "video-assets/" not in response.text
    assert "no-store" in response.headers["cache-control"]
    monkeypatch.setattr(get_settings(), "video_drm_required", True)
    assert browser.get(url).status_code == 503
    assert browser.get(f"/api/v1/lessons/{lesson.id}/stream?token=old").status_code == 503
    monkeypatch.setattr(get_settings(), "video_drm_required", False)
    assert TestClient(app).get(url).status_code == 403
    browser.post("/api/v1/auth/logout", headers=_csrf(browser))
    assert browser.get(url).status_code == 403
