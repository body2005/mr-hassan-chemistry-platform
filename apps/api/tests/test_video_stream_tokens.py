import uuid

from fastapi.testclient import TestClient

from app.core.security import create_session_token
from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Lesson
from app.models.institution import Institution
from app.models.user import User, UserRole


def test_video_stream_requires_a_scoped_token_and_supports_ranges(db, monkeypatch, tmp_path):
    """Native playback is short-lived token streaming, not a fabricated HLS feed."""
    institution = Institution(name="Video Token Institute", slug=f"video-{uuid.uuid4().hex[:8]}")
    db.add(institution)
    db.flush()
    teacher = User(
        institution_id=institution.id,
        username=f"video-teacher-{uuid.uuid4().hex[:8]}",
        email=f"video-teacher-{uuid.uuid4().hex[:8]}@example.test",
        display_name="Video Teacher",
        password_hash="test",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.flush()
    student_without_entitlement = User(
        institution_id=institution.id,
        username=f"video-student-{uuid.uuid4().hex[:8]}",
        email=f"video-student-{uuid.uuid4().hex[:8]}@example.test",
        display_name="Video Student",
        password_hash="test",
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
    auth = {"Authorization": f"Bearer {create_session_token(teacher)}"}

    token_response = client.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=auth)
    assert token_response.status_code == 200
    payload = token_response.json()
    assert set(payload) == {"video_token", "stream_url", "expires_in"}
    assert "manifest" not in payload

    no_access = client.post(
        f"/api/v1/lessons/{lesson.id}/video-token",
        headers={"Authorization": f"Bearer {create_session_token(student_without_entitlement)}"},
    )
    assert no_access.status_code == 403

    assert client.get(f"/api/v1/lessons/{lesson.id}/stream").status_code == 401
    assert client.get(f"/api/v1/lessons/{lesson.id}/manifest.m3u8?token={payload['video_token']}").status_code == 404

    response = client.get(payload["stream_url"], headers={"Range": "bytes=0-3"})
    assert response.status_code == 206
    assert response.content == b"0123"
    assert response.headers["accept-ranges"] == "bytes"
