import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.config import get_settings
from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Enrollment, EnrollmentStatus, Lesson
from app.models.institution import Institution
from app.models.user import User, UserRole


class MemoryObjectStorage:
    """Small object-store double proving media survives outside the web disk."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def save_file(self, local_source_path, storage_key, content_type=None):
        self.objects[storage_key] = Path(local_source_path).read_bytes()
        return f"s3://test-bucket/{storage_key}"

    def get_local_path(self, storage_key):
        return None

    def get_size(self, storage_key):
        return len(self.objects[storage_key.removeprefix("s3://test-bucket/")])

    def open_stream(self, storage_key, start=0, length=None):
        data = self.objects[storage_key.removeprefix("s3://test-bucket/")]
        yield data[start:] if length is None else data[start : start + length]

    def delete(self, storage_key):
        self.objects.pop(storage_key.removeprefix("s3://test-bucket/"), None)
        return True


def test_video_stream_requires_a_scoped_token_and_supports_ranges(db, monkeypatch, tmp_path):
    """Native playback is short-lived token streaming, not a fabricated HLS feed."""
    institution = Institution(name="Video Token Institute", slug=f"video-{uuid.uuid4().hex[:8]}")
    db.add(institution)
    db.flush()
    teacher = User(
        institution_id=institution.id,
        username=f"video-teacher-{uuid.uuid4().hex[:8]}",
        email=f"video-teacher-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Video Teacher",
        password_hash=hash_password("TeacherPass123!"),
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.flush()
    student_without_entitlement = User(
        institution_id=institution.id,
        username=f"video-student-{uuid.uuid4().hex[:8]}",
        email=f"video-student-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Video Student",
        password_hash=hash_password("StudentPass123!"),
        role=UserRole.STUDENT,
    )
    db.add(student_without_entitlement)
    db.flush()
    course = Course(
        institution_id=institution.id,
        teacher_id=teacher.id,
        code=f"VIDEO-{uuid.uuid4().hex[:6]}",
        title="Video course",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.flush()
    module = CourseModule(course_id=course.id, title="Module", position=1)
    db.add(module)
    db.flush()
    lesson = Lesson(module_id=module.id, title="Protected video", kind="video", position=1)
    db.add(lesson)
    db.commit()

    monkeypatch.setenv("VIDEO_UPLOAD_DIR", str(tmp_path))
    (tmp_path / f"{lesson.id}.mp4").write_bytes(b"0123456789abcdef")
    client = TestClient(app)
    # Exercise the actual cookie-only login flow, not a legacy Bearer header.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": teacher.email, "password": "TeacherPass123!", "institution_slug": institution.slug},
    )
    assert login.status_code == 200, login.text

    csrf_headers = {"X-CSRF-Token": client.cookies.get(get_settings().csrf_cookie_name)}
    object_store = MemoryObjectStorage()
    monkeypatch.setattr("app.api.routes.platform.get_storage_provider", lambda: object_store)
    video_bytes = b"\x00\x00\x00\x18ftypisom" + b"persistent-video-content"
    upload = client.post(
        f"/api/v1/lessons/{lesson.id}/video",
        headers=csrf_headers,
        files={"file": ("lesson.mp4", video_bytes, "video/mp4")},
    )
    assert upload.status_code == 200, upload.text
    db.refresh(lesson)
    assert lesson.video_asset_key and lesson.video_asset_key.startswith("s3://test-bucket/")
    assert object_store.objects

    token_response = client.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=csrf_headers)
    assert token_response.status_code == 200
    payload = token_response.json()
    assert set(payload) == {"video_token", "stream_url", "expires_in", "format"}
    assert payload["format"] == "progressive"
    assert "manifest" not in payload

    # Range streaming works with the SAME session that requested the token:
    # the stream is bound to the issuing session (nonce == session jti), so
    # sharing the URL with another account or an anonymous client dies here.
    response = client.get(payload["stream_url"], headers={"Range": "bytes=12-15"})
    assert response.status_code == 206
    assert response.content == b"pers"
    assert response.headers["accept-ranges"] == "bytes"

    # Open-ended video requests must finish, rather than reserving a slot for
    # the entire lesson behind a buffering reverse proxy. Seeking still reads
    # the exact requested position, for object storage, local and legacy media.
    from app.api.routes.platform import MAX_VIDEO_RANGE_BYTES
    from app.core.storage import LocalStorageProvider

    large_video = bytes(range(256)) * ((MAX_VIDEO_RANGE_BYTES * 2) // 256 + 1)
    original_key = lesson.video_asset_key
    object_store.objects[original_key.removeprefix("s3://test-bucket/")] = large_video
    local_store = LocalStorageProvider(str(tmp_path / "objects"))
    local_key = local_store.save_bytes(large_video, "lesson.mp4")
    (tmp_path / f"{lesson.id}.mp4").write_bytes(large_video)
    for provider, key in [(object_store, original_key), (local_store, local_key), (local_store, None)]:
        monkeypatch.setattr("app.api.routes.platform.get_storage_provider", lambda: provider)
        lesson.video_asset_key = key
        db.commit()
        for start in [0, 5, MAX_VIDEO_RANGE_BYTES + 23] * 3:
            ranged = client.get(payload["stream_url"], headers={"Range": f"bytes={start}-"})
            end = min(len(large_video), start + MAX_VIDEO_RANGE_BYTES)
            assert ranged.status_code == 206
            assert ranged.content == large_video[start:end]
            assert ranged.headers["content-length"] == str(end - start)
            assert ranged.headers["content-range"] == f"bytes {start}-{end - 1}/{len(large_video)}"
        tail = client.get(payload["stream_url"], headers={"Range": "bytes=-7"})
        assert tail.content == large_video[-7:]
        assert client.get(payload["stream_url"], headers={"Range": f"bytes={len(large_video)}-"}).status_code == 416
    lesson.video_asset_key = original_key
    db.commit()
    monkeypatch.setattr("app.api.routes.platform.get_storage_provider", lambda: object_store)

    # A password change or "sign out everywhere" must also invalidate a
    # previously issued stream URL, even if the old browser keeps its cookie.
    revoke = client.post("/api/v1/auth/revoke-all", headers=csrf_headers)
    assert revoke.status_code == 204
    assert client.get(payload["stream_url"]).status_code == 403

    student_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": student_without_entitlement.email,
            "password": "StudentPass123!",
            "institution_slug": institution.slug,
        },
    )
    assert student_login.status_code == 200, student_login.text
    student_csrf_headers = {"X-CSRF-Token": client.cookies.get(get_settings().csrf_cookie_name)}
    no_access = client.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=student_csrf_headers)
    assert no_access.status_code == 403

    enrollment = Enrollment(course_id=course.id, student_id=student_without_entitlement.id)
    db.add(enrollment)
    db.commit()
    entitled = client.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=student_csrf_headers)
    assert entitled.status_code == 200, entitled.text
    entitled_url = entitled.json()["stream_url"]
    assert client.get(entitled_url, headers={"Range": "bytes=0-3"}).status_code == 206
    enrollment.status = EnrollmentStatus.WITHDRAWN
    db.commit()
    assert client.get(entitled_url, headers={"Range": "bytes=0-3"}).status_code == 403

    # Missing token is now uniformly 403 (invalid/absent credentials are not
    # distinguished to avoid revealing which part failed).
    assert client.get(f"/api/v1/lessons/{lesson.id}/stream").status_code == 403
    assert client.get(f"/api/v1/lessons/{lesson.id}/manifest.m3u8?token={payload['video_token']}").status_code == 404

    # Replay with the WRONG session (student cookies + teacher token) fails.
    replay = client.get(payload["stream_url"], headers={"Range": "bytes=0-3"})
    assert replay.status_code == 403


def test_external_video_link_is_not_an_allowed_protected_source():
    from pydantic import ValidationError

    from app.api.routes.courses import _video_playback_fields
    from app.schemas import LessonCreateRequest

    try:
        LessonCreateRequest(title="External", kind="video", position=1, external_video_url="https://example.com/video.mp4")
    except ValidationError:
        pass
    else:
        raise AssertionError("External video URL was accepted")

    legacy_lesson = type("LegacyLesson", (), {"id": uuid.uuid4(), "video_asset_key": "https://example.com/video.mp4"})()
    assert _video_playback_fields(legacy_lesson) == (False, None)
    assert _video_playback_fields(legacy_lesson, allow_external=True) == (True, "https://example.com/video.mp4")
