import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.config import get_settings
from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Lesson
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
    upload = client.post(
        f"/api/v1/lessons/{lesson.id}/video",
        headers=csrf_headers,
        files={"file": ("lesson.mp4", b"persistent-video-content", "video/mp4")},
    )
    assert upload.status_code == 200, upload.text
    db.refresh(lesson)
    assert lesson.video_asset_key and lesson.video_asset_key.startswith("s3://test-bucket/")
    assert object_store.objects

    token_response = client.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=csrf_headers)
    assert token_response.status_code == 200
    payload = token_response.json()
    assert set(payload) == {"video_token", "stream_url", "expires_in"}
    assert "manifest" not in payload

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

    assert client.get(f"/api/v1/lessons/{lesson.id}/stream").status_code == 401
    assert client.get(f"/api/v1/lessons/{lesson.id}/manifest.m3u8?token={payload['video_token']}").status_code == 404

    response = client.get(payload["stream_url"], headers={"Range": "bytes=0-3"})
    assert response.status_code == 206
    assert response.content == b"pers"
    assert response.headers["accept-ranges"] == "bytes"
