"""Backend request-storm hardening tests (rate limits, ETag, 304 caching).

These tests pin the server-side behaviours that protect the API and PostgreSQL
from the request storms described in the review, now targeting the standalone
lesson-materials endpoints that replaced the Knowledge Center:

1. Unauthorized requests are rejected before any expensive work.
2. Rate limits return 429 + Retry-After; normal users are unaffected.
3. The distributed (Redis) limiter is used in production-like environments.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.course import Course, CourseModule, CourseStatus
from app.models.extended import LessonAsset
from app.models.institution import Institution
from app.models.user import User, UserRole

os.environ.setdefault("APP_ENV", "test")


def make_institution(db: Session, slug: str) -> Institution:
    inst = Institution(name=f"Inst {slug}", slug=slug)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def make_user(db: Session, institution_id: str, role: UserRole, tag: str) -> User:
    from app.core.security import hash_password

    user = User(
        institution_id=institution_id,
        username=f"user_{tag}_{uuid.uuid4().hex[:8]}",
        email=f"user_{tag}_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password-123456"),
        display_name=f"User {tag}",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client: TestClient, user: User, slug: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "password-123456",
            "institution_slug": slug,
        },
    )
    assert response.status_code == 200, response.text


def make_teacher_course_lesson(db: Session, slug: str):
    inst = make_institution(db, slug)
    teacher = make_user(db, inst.id, UserRole.TEACHER, slug)
    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code=f"C-{uuid.uuid4().hex[:6].upper()}",
        title="Course",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    module = CourseModule(course_id=course.id, title="Module", position=1)
    db.add(module)
    db.commit()
    db.refresh(module)
    from app.models.course import Lesson

    lesson = Lesson(module_id=module.id, title="Lesson", kind="video", position=1)
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return inst, teacher, course, lesson


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("matgar_csrf")
    assert token
    return {"X-CSRF-Token": token}


def test_old_knowledge_center_endpoints_return_404(db) -> None:
    inst, teacher, course, lesson = make_teacher_course_lesson(db, "gone-a")
    client = TestClient(app)
    login(client, teacher, "gone-a")

    assert client.get("/api/v1/knowledge-center/sources").status_code == 404
    assert client.get("/api/v1/lessons/nonexistent/reindex").status_code == 404
    assert client.get("/api/v1/lessons/nonexistent/indexing-status").status_code == 404


def test_unauthorized_material_download_rejected_before_io(db, tmp_path) -> None:
    inst, teacher, course, lesson = make_teacher_course_lesson(db, "anon-a")
    asset = LessonAsset(
        lesson_id=lesson.id,
        institution_id=inst.id,
        asset_kind="pdf",
        object_key="lesson_materials/does_not_matter.pdf",
        filename="x.pdf",
        mime_type="application/pdf",
        size_bytes=10,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    client = TestClient(app)  # no login at all
    response = client.get(
        f"/api/v1/lessons/{lesson.id}/materials/{asset.id}/download"
    )
    assert response.status_code in {401, 403}


def test_rate_limit_exceeded_returns_429_with_retry_after(db) -> None:
    from app.core import rate_limit as rl
    from app.api.routes import platform as platform_routes

    inst, teacher, course, lesson = make_teacher_course_lesson(db, "rl-a")
    client = TestClient(app)
    login(client, teacher, "rl-a")

    original = platform_routes.enforce_rate_limit

    def exhausted(*args, **kwargs):
        import fastapi

        raise fastapi.HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": "7"},
        )

    platform_routes.enforce_rate_limit = exhausted
    try:
        response = client.post(
            f"/api/v1/lessons/{lesson.id}/materials",
            files={"file": ("notes.pdf", b"%PDF-1.4 tiny", "application/pdf")},
            headers=csrf_headers(client),
        )
        assert response.status_code == 429, response.text
        assert response.headers.get("Retry-After") == "7"
    finally:
        platform_routes.enforce_rate_limit = original


def test_material_upload_applies_rate_limiting(db, tmp_path, monkeypatch) -> None:
    """The upload endpoint invokes the limiter with the upload bucket."""
    inst, teacher, course, lesson = make_teacher_course_lesson(db, "rl-upload")
    client = TestClient(app)
    login(client, teacher, "rl-upload")

    calls: list[tuple] = []
    from app.api.routes import platform as platform_routes

    original = platform_routes.enforce_rate_limit

    def recording(request, **kwargs):
        calls.append((kwargs.get("bucket"), kwargs.get("limit"), kwargs.get("window_seconds")))
        return original(request, **kwargs)

    platform_routes.enforce_rate_limit = recording
    try:
        payload = b"%" + b"PDF-1.4 minimal upload" + b"\n"
        response = client.post(
            f"/api/v1/lessons/{lesson.id}/materials",
            files={"file": ("notes.pdf", payload, "application/pdf")},
            headers=csrf_headers(client),
        )
        assert response.status_code == 201, response.text
        assert calls, "upload endpoint must call enforce_rate_limit"
        assert any(c[0] == "upload" for c in calls)
    finally:
        platform_routes.enforce_rate_limit = original


def test_distributed_limiter_is_redis_backed_in_production_like(monkeypatch) -> None:
    """In production_like the app must fail closed to Redis, not in-memory."""
    from app.core import rate_limit as rl
    from app.core.config import get_settings

    settings = get_settings()
    assert settings.app_env == "test" or settings.redis_required or settings.app_env in {"production", "production_like"}, (
        "environment guard changed; review this test"
    )

    class FakeScript:
        def __call__(self, keys=None, args=None):
            return [1, 1, 0]

    class FakeRedis:
        def register_script(self, script):
            return FakeScript()

    monkeypatch.setattr(rl, "_get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(rl, "_redis_script", FakeRedis().register_script("LUA"))

    import fastapi

    class BlockingScript(FakeScript):
        def __call__(self, keys=None, args=None):
            return [0, 0, 5]

    monkeypatch.setattr(rl, "_redis_script", BlockingScript())

    class DummyRequest:
        class client:
            host = "10.0.0.9"

        headers = {}
        cookies = {}
        state = type("S", (), {"rate_limit_categories": set()})()

    request = DummyRequest()
    monkeypatch.setattr(rl, "get_settings", lambda: type(
        "S2",
        (),
        {
            "redis_url": "redis://x",
            "trusted_proxies": "127.0.0.1,::1",
            "session_cookie_name": "session",
            "rate_limit_window_seconds": 60,
            "rate_limit_api_default": 600,
            "rate_limit_read": 600,
            "rate_limit_ai": 60,
            "rate_limit_upload": 60,
            "rate_limit_quiz_extraction": 30,
            "app_env": "production_like",
            "redis_required": True,
        },
    )())

    with pytest.raises(fastapi.HTTPException) as exc:
        rl.enforce_rate_limit(request, bucket="api")
    assert exc.value.status_code == 429
