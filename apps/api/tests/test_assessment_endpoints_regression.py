"""Regression coverage for assessment helpers that must be imported at runtime."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import app
from app.models.course import Course, CourseStatus
from app.models.institution import Institution
from app.models.knowledge_center import AssessmentQuestion, AssessmentSource, KnowledgeSource
from app.models.user import User, UserRole


@pytest.fixture
def assessment_fixture(db):
    institution = Institution(name="Assessment Regression", slug="assessment-regression")
    db.add(institution)
    db.flush()
    teacher = User(
        institution_id=institution.id,
        username="assessment-regression-teacher",
        email="assessment-regression@example.com",
        password_hash=hash_password("teacher-secret-123"),
        display_name="Assessment Regression Teacher",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.flush()
    course = Course(
        institution_id=institution.id,
        teacher_id=teacher.id,
        code="CHEM-REG",
        title="Chemistry Regression",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.flush()
    source = KnowledgeSource(
        institution_id=institution.id,
        course_id=course.id,
        teacher_id=teacher.id,
        filename="exam.pdf",
        file_format="pdf",
        mime_type="application/pdf",
        storage_path="storage/knowledge_center/test/exam.pdf",
        size_bytes=1024,
        source_role="ASSESSMENT",
        checksum=uuid.uuid4().hex,
        status="INDEXED",
    )
    db.add(source)
    db.flush()
    assessment = AssessmentSource(
        source_id=source.id,
        assessment_type="exam",
        title="Iron compounds exam",
        total_questions=1,
        processing_status="COMPLETED",
        review_status="needs_review",
    )
    db.add(assessment)
    db.flush()
    question = AssessmentQuestion(
        assessment_source_id=assessment.id,
        course_id=course.id,
        question_text="What is the chemical formula of iron(II) oxide?",
        question_type="multiple_choice",
        difficulty="medium",
        learning_objective="iron-oxides",
        topic_concept="oxides",
        points=1.0,
        source_kind="extracted",
        correct_answer="FeO",
        answer_status="resolved",
        options_json=[{"text": "FeO"}, {"text": "Fe2O3"}, {"text": "Fe3O4"}, {"text": "Fe"}],
        normalized_hash=uuid.uuid4().hex,
        semantic_fingerprint=uuid.uuid4().hex,
    )
    db.add(question)
    db.commit()
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": teacher.email, "password": "teacher-secret-123", "institution_slug": institution.slug},
    )
    assert login.status_code == 200, login.text
    client.headers.update({"X-CSRF-Token": client.cookies.get("matgar_csrf") or ""})
    return {"client": client, "teacher": teacher, "course": course, "assessment": assessment, "question": question}


def test_assessment_helpers_are_imported():
    from app.api.routes import knowledge_center

    assert callable(knowledge_center.validate_assessment_question)
    assert callable(knowledge_center.relink_answer_key)


def test_quiz_attempt_answer_is_imported():
    from app.services import extended_service

    assert extended_service.QuizAttemptAnswer.__name__ == "QuizAttemptAnswer"


def test_assessment_question_update_reaches_validation(assessment_fixture):
    response = assessment_fixture["client"].patch(
        f"/api/v1/knowledge-center/assessment-questions/{assessment_fixture['question'].id}",
        json={"question_text": "Which formula represents iron(II) oxide?"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["validation_errors"] == []


def test_assessment_question_invalid_update_is_reported(assessment_fixture):
    response = assessment_fixture["client"].patch(
        f"/api/v1/knowledge-center/assessment-questions/{assessment_fixture['question'].id}",
        json={"question_text": "ab", "options_json": [{"text": "only-one"}]},
    )
    assert response.status_code == 200, response.text
    assert "Question text is too short" in response.json()["validation_errors"]


def test_assessment_approval_reaches_validation(assessment_fixture):
    response = assessment_fixture["client"].post(
        f"/api/v1/knowledge-center/assessments/{assessment_fixture['assessment'].id}/approve"
    )
    assert response.status_code in {200, 422}, response.text


def test_student_mastery_query_executes(assessment_fixture, db):
    from app.models.extended import LearningObjective
    from app.services import extended_service

    teacher = assessment_fixture["teacher"]
    course = assessment_fixture["course"]
    db.add(LearningObjective(institution_id=teacher.institution_id, course_id=course.id, code="iron-oxides", title="Iron oxides"))
    db.commit()
    assert isinstance(extended_service.compute_student_mastery(db, teacher, teacher.id), list)
