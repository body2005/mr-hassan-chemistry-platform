"""Percentages and opportunity counts, not raw marks or number of retries."""
from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models.course import Enrollment, EnrollmentStatus
from app.models.platform import (AttemptStatus, Question, Quiz, QuizStatus, QuizAttempt,
                                QuizAttemptAnswer, Assignment, AssignmentStatus, AssignmentSubmission)
from app.models.user import UserRole
from tests.test_security_and_tenancy import make_institution, make_user, make_course, login

NOW = datetime.now(timezone.utc)


def domain(db):
    inst = make_institution(db, "analytics-units")
    teacher = make_user(db, inst.id, UserRole.TEACHER, "owner")
    student = make_user(db, inst.id, UserRole.STUDENT, "student")
    course = make_course(db, inst, teacher)
    db.add(Enrollment(course_id=course.id, student_id=student.id, status=EnrollmentStatus.ACTIVE))
    db.commit()
    client = TestClient(app); login(client, teacher, inst.slug)
    return inst, teacher, student, course, client


def quiz(db, inst, teacher, course):
    row = Quiz(institution_id=inst.id, creator_id=teacher.id, course_id=course.id,
               title="Synthetic assessment", status=QuizStatus.PUBLISHED)
    db.add(row); db.flush()
    return row


def attempt(db, inst, student, quiz, score, total, *, number=1, submitted=True,
            graded=True, practice=False, empty=False):
    row = QuizAttempt(institution_id=inst.id, quiz_id=quiz.id, student_id=student.id,
        attempt_number=number, started_at=NOW, submitted_at=NOW if submitted else None,
        status=AttemptStatus.SUBMITTED if submitted else AttemptStatus.IN_PROGRESS,
        score=score, total_points=total, is_practice=practice)
    db.add(row); db.flush()
    if not empty:
        question = Question(institution_id=inst.id, author_id=quiz.creator_id,
            question_type="essay", prompt="Synthetic answer", points=1)
        db.add(question); db.flush()
        db.add(QuizAttemptAnswer(attempt_id=row.id, question_id=question.id,
            awarded_points=score or 0, graded_at=NOW if graded else None))
    db.commit()
    return row


def summary(client):
    response = client.get("/api/v1/reports/summary")
    assert response.status_code == 200, response.text
    return response.json()


def test_percentage_average_order_and_mastery_use_each_attempt_total(db):
    inst, teacher, student, course, client = domain(db)
    quizzes = [quiz(db, inst, teacher, course) for _ in range(3)]
    for row, score, total in zip(quizzes, [10, 5, 80], [10, 10, 200]):
        attempt(db, inst, student, row, score, total)
    result = summary(client)
    assert result["quiz_avg_score"] == 63.33
    assert result["quiz_completion_rate"] == 100
    assert [item["quiz_id"] for item in result["top_quizzes"]] == [str(q.id) for q in quizzes]
    assert [item["score"] for item in result["top_quizzes"]] == [100, 50, 40]
    assert result["mastery_distribution"] == {"ممتاز": 1, "جيد جداً": 0, "جيد": 0, "مقبول": 0, "ضعيف": 2}


def test_empty_in_progress_pending_and_practice_are_not_results(db):
    inst, teacher, student, course, client = domain(db)
    quizzes = [quiz(db, inst, teacher, course) for _ in range(4)]
    attempt(db, inst, student, quizzes[0], 10, 10)
    attempt(db, inst, student, quizzes[1], None, 10, submitted=False, empty=True)
    attempt(db, inst, student, quizzes[2], 0, 10, graded=False)
    attempt(db, inst, student, quizzes[3], 10, 10, practice=True)
    result = summary(client)
    assert result["quiz_avg_score"] == 100
    assert result["quiz_completion_rate"] == 25
    assert sum(result["mastery_distribution"].values()) == 1


def test_official_revisions_count_one_opportunity_latest_submission_wins(db):
    inst, teacher, student, course, client = domain(db)
    row = quiz(db, inst, teacher, course)
    attempt(db, inst, student, row, 1, 10)
    attempt(db, inst, student, row, 9, 10, number=2)
    result = summary(client)
    assert result["quiz_avg_score"] == 90
    assert result["quiz_completion_rate"] == 100
    assert sum(result["mastery_distribution"].values()) == 1
    # A newer pending submission is not silently replaced by an older result.
    attempt(db, inst, student, row, 0, 10, number=3, graded=False)
    assert summary(client)["quiz_avg_score"] is None
    assert summary(client)["quiz_completion_rate"] == 0


def test_zero_missing_or_inconsistent_totals_are_explicit_not_clamped(db):
    inst, teacher, student, course, client = domain(db)
    for score, total in [(0, 0), (None, 10), (5, None), (20, 10), (-1, 10)]:
        attempt(db, inst, student, quiz(db, inst, teacher, course), score, total)
    result = summary(client)
    assert result["quiz_avg_score"] is None
    assert result["invalid_score_count"] == 5
    assert sum(result["mastery_distribution"].values()) == 0
    assert result["top_quizzes"] == []


def test_enrollment_opportunities_not_retries_or_all_students_are_denominator(db):
    inst, teacher, student, course, client = domain(db)
    colleague = make_user(db, inst.id, UserRole.TEACHER, "colleague")
    other_course = make_course(db, inst, colleague)
    row = quiz(db, inst, teacher, course)
    attempt(db, inst, student, row, 10, 10)
    quiz(db, inst, teacher, course)  # Not attempted: denominator still includes it.
    assignment = Assignment(institution_id=inst.id, creator_id=teacher.id, course_id=course.id,
        title="Assignment", prompt="Answer", status=AssignmentStatus.PUBLISHED)
    db.add(assignment); db.flush()
    for version in [1, 2, 3]:
        db.add(AssignmentSubmission(institution_id=inst.id, assignment_id=assignment.id,
            student_id=student.id, version=version, answer_text="Answer",
            submitted_at=NOW, idempotency_key=uuid.uuid4().hex))
    outsider = make_user(db, inst.id, UserRole.STUDENT, "not-enrolled")
    # Even same-tenant evidence must belong to an active/completed enrollment.
    attempt(db, inst, outsider, row, 0, 10)
    attempt(db, inst, student, quiz(db, inst, colleague, other_course), 0, 10)
    result = summary(client)
    assert result["quiz_avg_score"] == 100
    assert result["quiz_completion_rate"] == 50
    assert result["assignment_submission_rate"] == 100
    assert result["quiz_eligible_count"] == 2
    assert result["assignment_eligible_count"] == 1


def test_no_opportunities_returns_none_instead_of_artificial_denominator(db):
    *_, client = domain(db)
    result = summary(client)
    assert result["quiz_avg_score"] is None
    assert result["quiz_completion_rate"] is None
    assert result["assignment_submission_rate"] is None
    assert result["lesson_completion_rate"] is None
