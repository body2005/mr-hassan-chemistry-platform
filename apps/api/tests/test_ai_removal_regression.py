"""AI isolation regression test (2026-09 removal).

The platform deliberately removed every AI feature except quiz generation,
quiz extraction from files and the Knowledge Center infrastructure they
depend on. This suite pins that contract:

* every removed AI endpoint answers with a plain 404, and
* the kept quiz extraction endpoint still works end to end.
"""
from __future__ import annotations

import io
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.institution import Institution
from app.models.user import User, UserRole


REMOVED_AI_ENDPOINTS = [
    ("POST", "/api/v1/tutor/chat"),
    ("POST", "/api/v1/tutor/index-course"),
    ("GET", "/api/v1/ai/refusal-log"),
    ("POST", "/api/v1/ai/invocations"),
    ("POST", "/api/v1/ai/jobs"),
    ("GET", "/api/v1/ai/runs"),
    ("POST", "/api/v1/grading/essay"),
    ("POST", "/api/v1/risk/predict"),
    ("POST", "/api/v1/risk/train"),
    ("POST", "/api/v1/analytics/interpret"),
    ("GET", "/api/v1/reports/narrative"),
    ("GET", "/api/v1/system/metrics"),
    ("GET", "/api/v1/system/health"),
    ("POST", "/api/v1/system/cache/clear"),
    ("POST", "/api/v1/analytics/students/00000000-0000-0000-0000-000000000000/risk"),
    ("POST", "/api/v1/quiz/draft"),
    ("GET", "/api/v1/system/asr-config"),
    ("POST", "/api/v1/system/asr-config"),
    ("GET", "/api/v1/payments/me/ai-access"),
    ("GET", "/api/v1/transcription/jobs/00000000-0000-0000-0000-000000000000"),
    ("POST", "/api/v1/transcription/jobs/00000000-0000-0000-0000-000000000000/callback"),
    ("GET", "/api/v1/transcription/download/some-token"),
]


@pytest.fixture
def teacher(db):
    institution = Institution(name="AI removal inst", slug=f"ai-removal-{uuid.uuid4().hex[:6]}")
    db.add(institution)
    db.commit()
    teacher = User(
        institution_id=institution.id,
        username=f"teacher_{uuid.uuid4().hex[:6]}",
        email=f"teacher_{uuid.uuid4().hex[:6]}@test.edu",
        password_hash="hash",
        display_name="أستاذ",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


def test_removed_ai_endpoints_return_404(teacher):
    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_current_user] = lambda: teacher
    try:
        for method, endpoint in REMOVED_AI_ENDPOINTS:
            response = client.request(method, endpoint, json={})
            assert response.status_code == 404, (
                f"{method} {endpoint} must answer 404 after the AI removal, "
                f"got {response.status_code}: {response.text[:200]}"
            )
    finally:
        app.dependency_overrides.clear()


def test_quiz_extraction_still_works_end_to_end(teacher):
    """The kept feature: extracting quiz questions from an uploaded file."""
    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_current_user] = lambda: teacher
    try:
        sample_quiz = (
            "1. ما هو ناتج تفاعل الصوديوم مع الماء؟\n"
            "أ) هيدروكسيد الصوديوم وغاز الهيدروجين\n"
            "ب) أكسيد الصوديوم\n"
            "ج) كلوريد الصوديوم\n"
            "د) كربونات الصوديوم\n"
            "الإجابة الصحيحة: أ\n"
        )
        response = client.post(
            "/api/v1/quiz/extract-from-file",
            files={"file": ("quiz.txt", io.BytesIO(sample_quiz.encode("utf-8")), "text/plain")},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("questions"), "extraction must return questions"
        assert len(data["questions"]) >= 1
    finally:
        app.dependency_overrides.clear()
