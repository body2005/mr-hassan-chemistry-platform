import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.platform import QuizAttempt, QuizAttemptAnswer
from app.models.user import UserRole
from tests.test_quiz_history_review import domain, solve, submit
from tests.test_security_and_tenancy import login, make_user, make_institution, csrf_headers


def assert_hidden(learner, quiz, attempt_id):
    result = learner.get(f'/api/v1/quizzes/{quiz.id}/result?attempt_id={attempt_id}')
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['score'] is None and body['summary'] is None
    assert body['approval_status'] == 'pending'
    assert body['message'] == 'تم تسليم الاختبار، والنتيجة في انتظار اعتماد المدرس'
    for question in body['questions']:
        assert set(question) == {'id', 'student_answer'}
    history = learner.get(f'/api/v1/quizzes/{quiz.id}/attempts-history').json()
    assert next(row for row in history if row['id'] == attempt_id)['score'] is None


@pytest.mark.parametrize('mark', [0, 7])
def test_essay_requires_manual_grade_and_explicit_release_even_for_zero(db, mark):
    owner, learner, question, quiz, student = domain(db, answer='Model answer')
    opened = solve(learner, quiz)
    response = submit(learner, opened['attempt'], question, 'Different but potentially valid wording')
    attempt_id = response['id']
    row = db.query(QuizAttemptAnswer).filter_by(attempt_id=uuid.UUID(attempt_id)).one()
    assert row.graded_at is None and row.awarded_points == 0
    assert response['score'] is None
    assert_hidden(learner, quiz, attempt_id)
    approval_path = f'/api/v1/quiz-attempts/{attempt_id}/approve'
    assert owner.post(approval_path, headers=csrf_headers(owner)).status_code == 409
    graded = owner.post(f'/api/v1/quiz-attempts/{attempt_id}/answers/{question.id}/grade',
                       json={'awarded_points': mark}, headers=csrf_headers(owner))
    assert graded.status_code == 200, graded.text
    assert_hidden(learner, quiz, attempt_id)
    mastery_path = f'/api/v1/analytics/students/{student.id}/mastery'
    assert learner.get(mastery_path).json()['items'] == []
    approved = owner.post(approval_path, headers=csrf_headers(owner))
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body['results_approved_by'] and body['results_approved_at']
    again = owner.post(approval_path, headers=csrf_headers(owner))
    assert again.json()['results_approved_at'] == body['results_approved_at']
    # A fresh authenticated session simulates a different device/reload.
    fresh = login(TestClient(app), student, 'frozen-evidence')
    result = fresh.get(f'/api/v1/quizzes/{quiz.id}/result').json()
    assert result['score'] == mark and result['questions'][0]['correct_answer'] == 'Model answer'
    assert result['approval_status'] == 'approved'
    assert fresh.get(mastery_path).json()['items'][0]['mastery'] == mark / 10
    assert owner.post(f'/api/v1/quiz-attempts/{attempt_id}/answers/{question.id}/grade',
                      json={'awarded_points': 5}, headers=csrf_headers(owner)).status_code == 409


def test_objective_grade_is_computed_privately_until_teacher_releases_it(db):
    owner, learner, question, quiz, _ = domain(db, kind='mcq', answer='A', options=['First', 'Second'])
    opened = solve(learner, quiz)
    submitted = submit(learner, opened['attempt'], question, 'A')
    assert submitted['score'] is None and submitted['grading_status'] == 'pending'
    attempt = db.get(QuizAttempt, uuid.UUID(submitted['id']))
    assert attempt.score == 10
    assert_hidden(learner, quiz, submitted['id'])
    # Idempotent resubmission must not return a hidden internal grade either.
    repeat = submit(learner, opened['attempt'], question, 'B')
    assert repeat['score'] is None
    path = f'/api/v1/quiz-attempts/{attempt.id}/approve'
    assert learner.post(path, headers=csrf_headers(learner)).status_code == 403
    assert owner.post(path, headers=csrf_headers(owner)).status_code == 200
    result = learner.get(f'/api/v1/quizzes/{quiz.id}/result').json()
    assert result['score'] == 10 and result['questions'][0]['state'] == 'correct'


@pytest.mark.parametrize('other_tenant', [False, True])
def test_unrelated_teacher_cannot_grade_or_release(db, other_tenant):
    owner, learner, question, quiz, _ = domain(db)
    opened = solve(learner, quiz)
    submitted = submit(learner, opened['attempt'], question, 'Text')
    inst = make_institution(db, 'other-approval') if other_tenant else None
    teacher = make_user(db, inst.id if inst else quiz.institution_id, UserRole.TEACHER, 'unrelated')
    outsider = login(TestClient(app), teacher, inst.slug if inst else 'frozen-evidence')
    path = f'/api/v1/quiz-attempts/{submitted["id"]}'
    assert outsider.post(path + '/approve', headers=csrf_headers(outsider)).status_code == 404
    assert outsider.post(path + f'/answers/{question.id}/grade', json={'awarded_points': 5},
                         headers=csrf_headers(outsider)).status_code == 404
    assert_hidden(learner, quiz, submitted['id'])


def test_invalid_historical_total_cannot_be_approved(db):
    owner, learner, question, quiz, _ = domain(db, kind='mcq', answer='A', options=['First', 'Second'])
    opened = solve(learner, quiz)
    submitted = submit(learner, opened['attempt'], question, 'A')
    attempt = db.get(QuizAttempt, uuid.UUID(submitted['id']))
    attempt.total_points = 1
    db.commit()
    assert owner.post(f'/api/v1/quiz-attempts/{attempt.id}/approve', headers=csrf_headers(owner)).status_code == 409
    assert_hidden(learner, quiz, submitted['id'])
