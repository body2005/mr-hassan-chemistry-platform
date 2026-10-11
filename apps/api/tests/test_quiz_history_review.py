"""Bank revisions must not change a published exam or a student's evidence."""
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.models.course import Enrollment
from app.models.extended import LearningObjective
from app.models.platform import Question, Quiz, QuizQuestion, QuizAttempt, QuizAttemptAnswer, AttemptStatus
from app.models.user import UserRole
from tests.test_security_and_tenancy import make_institution, make_user, make_course, login, csrf_headers


def domain(db, *, kind="essay", answer=None, options=None):
    inst = make_institution(db, "frozen-evidence")
    teacher = make_user(db, inst.id, UserRole.TEACHER, "teacher")
    student = make_user(db, inst.id, UserRole.STUDENT, "student")
    course = make_course(db, inst, teacher)
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.add(LearningObjective(institution_id=inst.id, course_id=course.id, code="CHEM", title="Chemistry"))
    question = Question(institution_id=inst.id, author_id=teacher.id, course_id=course.id,
        question_type=kind, prompt="Explain conservation of mass", learning_objective="CHEM",
        options=options, correct_answer=answer, points=1, version=1)
    quiz = Quiz(institution_id=inst.id, creator_id=teacher.id, course_id=course.id, title="Weighted quiz")
    db.add_all([question, quiz]); db.flush()
    db.add(QuizQuestion(quiz_id=quiz.id, question_id=question.id, position=1, points=10))
    db.commit()
    owner = login(TestClient(app), teacher, inst.slug)
    learner = login(TestClient(app), student, inst.slug)
    response = owner.post(f"/api/v1/quizzes/{quiz.id}/publish", headers=csrf_headers(owner))
    assert response.status_code == 200, response.text
    return owner, learner, question, quiz, student


def solve(learner, quiz):
    response = learner.get(f"/api/v1/quizzes/{quiz.id}/solve")
    assert response.status_code == 200, response.text
    # Answer keys never travel with the exam-opening response.
    assert "correct_answer" not in response.json()["questions"][0]
    return response.json()


def submit(learner, attempt, question, answer):
    response = learner.post(f'/api/v1/quiz-attempts/{attempt["id"]}/submit',
        json={"submission_key": uuid.uuid4().hex, "answers": [{"question_id": str(question.id), "answer": answer}]},
        headers=csrf_headers(learner))
    assert response.status_code == 200, response.text
    return response.json()


def test_weighted_mastery_and_result_stay_50_percent_after_bank_revision(db):
    owner, learner, question, quiz, student = domain(db)
    opened = solve(learner, quiz)
    attempt = submit(learner, opened["attempt"], question, "Synthetic chemistry explanation")
    graded = owner.post(f'/api/v1/quiz-attempts/{attempt["id"]}/answers/{question.id}/grade',
        json={"awarded_points": 5}, headers=csrf_headers(owner))
    assert graded.status_code == 200, graded.text
    path = f"/api/v1/analytics/students/{student.id}/mastery"
    assert owner.get(path).json()["items"][0]["mastery"] == 0.5
    changed = owner.post(f"/api/v1/questions/{question.id}/versions",
        json={"points": 20, "prompt": "Different bank question", "question_type": "short_answer"},
        headers=csrf_headers(owner))
    assert changed.status_code == 201, changed.text
    assert owner.get(path).json()["items"][0]["mastery"] == 0.5
    approval = owner.post(f'/api/v1/quiz-attempts/{attempt["id"]}/approve', headers=csrf_headers(owner))
    assert approval.status_code == 200, approval.text
    result = learner.get(f"/api/v1/quizzes/{quiz.id}/result").json()
    assert result["total_points"] == 10 and result["score"] == 5
    assert result["questions"][0]["prompt"] == "Explain conservation of mass"
    assert result["questions"][0]["question_type"] == "essay"
    assert result["questions"][0]["points"] == 10


def test_published_exam_and_in_progress_grading_ignore_bank_answer_changes(db):
    owner, learner, question, quiz, _ = domain(db, kind="mcq", answer="A", options=["First", "Second"])
    changed = owner.post(f"/api/v1/questions/{question.id}/versions", json={"correct_answer": "B", "points": 20},
        headers=csrf_headers(owner))
    assert changed.status_code == 201, changed.text
    opened = solve(learner, quiz)
    assert opened["questions"][0]["points"] == 10
    attempt = submit(learner, opened["attempt"], question, "A")
    assert attempt["score"] is None and attempt["total_points"] == 10
    assert db.get(QuizAttempt, uuid.UUID(attempt['id'])).score == 10
    row = db.query(QuizAttemptAnswer).filter_by(question_id=question.id).one()
    assert row.question_snapshot["question_version"] == 1
    assert row.question_snapshot["correct_answer"] == "A"


def test_manual_grade_uses_frozen_weight_and_type_after_bank_changes(db):
    owner, learner, question, quiz, _ = domain(db)
    opened = solve(learner, quiz)
    attempt = submit(learner, opened["attempt"], question, "Essay answer")
    changed = owner.post(f"/api/v1/questions/{question.id}/versions",
        json={"points": 100, "question_type": "mcq", "options": ["First", "Second"], "correct_answer": "A"},
        headers=csrf_headers(owner))
    assert changed.status_code == 201, changed.text
    path = f'/api/v1/quiz-attempts/{attempt["id"]}/answers/{question.id}/grade'
    assert owner.post(path, json={"awarded_points": 11}, headers=csrf_headers(owner)).status_code == 422
    accepted = owner.post(path, json={"awarded_points": 5}, headers=csrf_headers(owner))
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["score"] == 5


def test_legacy_evidence_is_reported_without_bank_weight_reinterpretation(db):
    owner, learner, question, quiz, student = domain(db)
    now = datetime.now(timezone.utc)
    legacy = QuizAttempt(institution_id=question.institution_id, quiz_id=quiz.id, student_id=student.id,
        attempt_number=1, started_at=now, submitted_at=now, status=AttemptStatus.SUBMITTED,
        score=5, total_points=10)
    db.add(legacy); db.flush()
    db.add(QuizAttemptAnswer(attempt_id=legacy.id, question_id=question.id, awarded_points=5, graded_at=now))
    db.commit()
    report = owner.get(f"/api/v1/analytics/students/{student.id}/mastery").json()
    assert report["items"] == [] and report["legacy_unverified_count"] == 1
    result = learner.get(f"/api/v1/quizzes/{quiz.id}/result").json()
    assert result["score"] is None and result["total_points"] == 10
    assert result["approval_status"] == "pending"
    assert 'correct_answer' not in str(result)
    response = owner.post(f"/api/v1/quiz-attempts/{legacy.id}/answers/{question.id}/grade",
        json={"awarded_points": 6}, headers=csrf_headers(owner))
    assert response.status_code == 409
    db.refresh(legacy)
    assert legacy.score == 5  # No implicit reconstruction or regrading.


def test_incomplete_grading_excludes_entire_attempt_from_mastery(db):
    owner, learner, question, quiz, student = domain(db)
    opened = solve(learner, quiz)
    submit(learner, opened["attempt"], question, "Pending essay")
    report = owner.get(f"/api/v1/analytics/students/{student.id}/mastery").json()
    assert report["items"] == [] and report["pending_attempt_count"] == 1


def test_invalid_frozen_award_is_not_clamped_into_mastery(db):
    owner, learner, question, quiz, student = domain(db, kind="mcq", answer="A", options=["First", "Second"])
    opened = solve(learner, quiz)
    submit(learner, opened["attempt"], question, "A")
    row = db.query(QuizAttemptAnswer).filter_by(question_id=question.id).one()
    row.awarded_points = 20
    db.commit()
    report = owner.get(f"/api/v1/analytics/students/{student.id}/mastery").json()
    assert report["items"] == [] and report["invalid_evidence_count"] == 1
