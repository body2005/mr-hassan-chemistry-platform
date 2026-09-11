from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.course import Course, CourseStatus, Enrollment
from app.models.institution import Institution
from app.models.knowledge_center import AssessmentQuestion, KnowledgeSource, SourceRole
from app.models.platform import (
    Assignment,
    AssignmentAttempt,
    AssignmentAttemptStatus,
    AssignmentStatus,
    AttemptStatus,
    Quiz,
    QuizAttempt,
    QuizStatus,
)
from app.models.user import User, UserRole
from app.services.ai_access_policy import evaluate_ai_access
from app.services.document_parsers import parse_assessment_bank
from app.services.knowledge_center_service import create_knowledge_source, process_knowledge_source


def _seed(db):
    inst = Institution(name="Assessment Academy", slug="assessment-academy")
    db.add(inst)
    db.flush()
    teacher = User(
        institution_id=inst.id,
        username="assessment-teacher",
        email="assessment-teacher@example.com",
        password_hash="hash",
        display_name="Assessment Teacher",
        role=UserRole.TEACHER,
    )
    student = User(
        institution_id=inst.id,
        username="assessment-student",
        email="assessment-student@example.com",
        password_hash="hash",
        display_name="Assessment Student",
        role=UserRole.STUDENT,
    )
    db.add_all([teacher, student])
    db.flush()
    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="BIO-201",
        title="Biology",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.flush()
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()
    return inst, teacher, student, course


def test_assessment_bank_does_not_guess_first_option_without_answer() -> None:
    questions = parse_assessment_bank(
        b"""[
          {
            "question_text": "Which organelle makes ATP?",
            "options": [{"key": "A", "text": "Nucleus"}, {"key": "B", "text": "Mitochondria"}]
          }
        ]""",
        "bank.json",
    )

    assert questions[0].correct_answer is None


def test_document_exam_materializes_questions_with_review_status(db) -> None:
    _, teacher, _, course = _seed(db)
    source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        filename="exam.md",
        file_bytes=b"1. What is photosynthesis?\nA. Food making\nB. Breathing\n",
        source_role=SourceRole.ASSESSMENT,
        metadata={"assessment_type": "exam"},
    )

    process_knowledge_source(db, source.id)

    assessment = db.scalar(select(KnowledgeSource).where(KnowledgeSource.id == source.id))
    questions = db.scalars(
        select(AssessmentQuestion).where(AssessmentQuestion.course_id == course.id)
    ).all()
    assert assessment is not None
    assert questions
    assert questions[0].answer_status in {"needs_review", "unresolved"}
    assert questions[0].review_status == "needs_review"


def test_ai_access_denied_for_active_quiz_and_assignment_attempts(db) -> None:
    inst, teacher, student, course = _seed(db)
    assert evaluate_ai_access(db, teacher).allowed is True

    quiz = Quiz(
        institution_id=inst.id,
        course_id=course.id,
        creator_id=teacher.id,
        title="Check",
        status=QuizStatus.PUBLISHED,
    )
    db.add(quiz)
    db.flush()
    db.add(
        QuizAttempt(
            institution_id=inst.id,
            quiz_id=quiz.id,
            student_id=student.id,
            attempt_number=1,
            started_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            status=AttemptStatus.IN_PROGRESS,
        )
    )
    db.commit()
    quiz_decision = evaluate_ai_access(db, student)
    assert quiz_decision.allowed is False
    assert quiz_decision.reason == "active_quiz_attempt"

    db.query(QuizAttempt).delete()
    assignment = Assignment(
        institution_id=inst.id,
        course_id=course.id,
        creator_id=teacher.id,
        title="Essay",
        prompt="Write a paragraph",
        status=AssignmentStatus.PUBLISHED,
    )
    db.add(assignment)
    db.flush()
    db.add(
        AssignmentAttempt(
            institution_id=inst.id,
            assignment_id=assignment.id,
            student_id=student.id,
            attempt_number=1,
            started_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            status=AssignmentAttemptStatus.IN_PROGRESS,
        )
    )
    db.commit()
    assignment_decision = evaluate_ai_access(db, student)
    assert assignment_decision.allowed is False
    assert assignment_decision.reason == "active_assignment_attempt"
