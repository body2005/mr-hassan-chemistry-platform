"""Video protection regression tests (student anti-download hardening).

Covers:
* The API never serializes the private storage key.
* Students cannot use the management preview endpoint.
* Stream requests fail without a valid, lesson-scoped token.
* Another student's or an anonymous request cannot replay a token that is
  bound to a live session.
* Logout revokes playback for previously issued tokens.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_video_token, hash_password
from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Lesson
from app.models.institution import Institution
from app.models.user import User, UserRole


def _setup_world(db: Session, tmp_path, monkeypatch) -> tuple[Institution, User, User, User, Lesson]:
    inst = Institution(name=f"VidGuard {uuid.uuid4().hex[:6]}", slug=f"vidguard-{uuid.uuid4().hex[:8]}")
    db.add(inst)
    db.flush()

    def make_user(role: UserRole, tag: str) -> User:
        user = User(
            institution_id=inst.id,
            username=f"{tag}-{uuid.uuid4().hex[:8]}",
            email=f"{tag}-{uuid.uuid4().hex[:8]}@example.com",
            display_name=tag,
            password_hash=hash_password("Passw0rd!secure"),
            role=role,
        )
        db.add(user)
        db.flush()
        return user

    teacher = make_user(UserRole.TEACHER, "teacher")
    student_in = make_user(UserRole.STUDENT, "studentin")
    student_out = make_user(UserRole.STUDENT, "studentout")
    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code=f"VG-{uuid.uuid4().hex[:6].upper()}",
        title="Video guard course",
        status=CourseStatus.PUBLISHED,
        price_egp=0,
    )
    db.add(course)
    db.flush()
    module = CourseModule(course_id=course.id, title="Module", position=1)
    db.add(module)
    db.flush()
    lesson = Lesson(
        module_id=module.id,
        title="Guarded lesson",
        kind="video",
        position=1,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    # Provide a real local video object so authorized streams can be served.
    monkeypatch.setenv("VIDEO_UPLOAD_DIR", str(tmp_path))
    (tmp_path / f"{lesson.id}.mp4").write_bytes(b"0123456789abcdef-video-payload")

    from app.models.course import Enrollment, EnrollmentStatus

    db.add(Enrollment(student_id=student_in.id, course_id=course.id, status=EnrollmentStatus.ACTIVE))
    db.commit()

    return inst, teacher, student_in, student_out, lesson


def _login(client: TestClient, user: User, slug: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Passw0rd!secure", "institution_slug": slug},
    )
    assert response.status_code == 200, response.text


def _csrf(client: TestClient) -> dict:
    return {"X-CSRF-Token": client.cookies.get(get_settings().csrf_cookie_name, "")}


def test_lesson_response_never_leaks_storage_key(db, tmp_path, monkeypatch) -> None:
    inst, teacher, student_in, _student_out, lesson = _setup_world(db, tmp_path, monkeypatch)
    client = TestClient(app)
    _login(client, teacher, inst.slug)

    listing = client.get("/api/v1/courses")
    assert listing.status_code == 200
    raw = listing.text
    assert "secret/private-key.mp4" not in raw
    assert "video_asset_key" not in raw
    assert "lesson_videos" not in raw


def test_student_blocked_from_management_preview(db, tmp_path, monkeypatch) -> None:
    inst, _teacher, student_in, _student_out, lesson = _setup_world(db, tmp_path, monkeypatch)
    client = TestClient(app)
    _login(client, student_in, inst.slug)
    response = client.get(f"/api/v1/lessons/{lesson.id}/video")
    assert response.status_code == 403


def test_stream_requires_token_and_rejects_anonymous_replay(db, tmp_path, monkeypatch) -> None:
    inst, _teacher, student_in, student_out, lesson = _setup_world(db, tmp_path, monkeypatch)
    client = TestClient(app)
    _login(client, student_in, inst.slug)

    no_token = client.get(f"/api/v1/lessons/{lesson.id}/stream")
    assert no_token.status_code in {401, 403}

    token_resp = client.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=_csrf(client))
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["video_token"]

    # The issuing client (same session cookies) may stream.
    ok = client.get(f"/api/v1/lessons/{lesson.id}/stream?token={token}")
    assert ok.status_code == 200, ok.text

    # A different logged-in student cannot replay the same token URL:
    # the token nonce is bound to the issuing session, not just the lesson.
    other = TestClient(app)
    _login(other, student_out, inst.slug)
    replay = other.get(f"/api/v1/lessons/{lesson.id}/stream?token={token}")
    assert replay.status_code == 403

    # Fully anonymous client cannot replay it either (no session family).
    anon = TestClient(app)
    anon_replay = anon.get(f"/api/v1/lessons/{lesson.id}/stream?token={token}")
    assert anon_replay.status_code == 403


def test_expired_token_rejected(db, tmp_path, monkeypatch) -> None:
    inst, _teacher, student_in, _student_out, lesson = _setup_world(db, tmp_path, monkeypatch)
    expired = create_video_token(
        user=student_in,
        lesson_id=lesson.id,
        expires_in_seconds=-10,
        nonce="deadbeefdeadbeefdeadbeefdeadbeef",
    )
    client = TestClient(app)
    _login(client, student_in, inst.slug)
    response = client.get(f"/api/v1/lessons/{lesson.id}/stream?token={expired}")
    assert response.status_code == 403


def test_logout_revokes_outstanding_video_tokens(db, tmp_path, monkeypatch) -> None:
    inst, _teacher, student_in, _student_out, lesson = _setup_world(db, tmp_path, monkeypatch)
    client = TestClient(app)
    _login(client, student_in, inst.slug)

    token_resp = client.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=_csrf(client))
    assert token_resp.status_code == 200
    token = token_resp.json()["video_token"]
    assert client.get(f"/api/v1/lessons/{lesson.id}/stream?token={token}").status_code == 200

    logout = client.post("/api/v1/auth/logout", headers=_csrf(client))
    assert logout.status_code == 204

    replayed = client.get(f"/api/v1/lessons/{lesson.id}/stream?token={token}")
    assert replayed.status_code == 403, "logout must kill outstanding video tokens"


def test_unenrolled_student_cannot_get_token(db, tmp_path, monkeypatch) -> None:
    inst, _teacher, _student_in, student_out, lesson = _setup_world(db, tmp_path, monkeypatch)
    client = TestClient(app)
    _login(client, student_out, inst.slug)
    response = client.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=_csrf(client))
    assert response.status_code == 403
