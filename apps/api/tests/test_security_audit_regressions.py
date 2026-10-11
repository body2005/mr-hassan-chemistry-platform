"""External review regressions; each assertion is a server-side security gate."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.course import CourseModule, Enrollment, EnrollmentStatus, Lesson, LessonKind
from app.models.payment import PaymentOrder, PaymentProductType, PaymentMethod
from app.models.platform import Quiz, QuizStatus, Question, QuizQuestion, QuizAttempt, AttemptStatus, Assignment, AssignmentStatus, QuizAttemptAnswer
from app.models.user import UserRole
from app.core.security import hash_token
from app.models.platform import RefreshSession
from tests.test_security_and_tenancy import make_institution, make_user, make_course, login, csrf_headers


def test_course_grade_and_lesson_price_survive_creation_and_publication(db):
    inst = make_institution(db, 'grade-publication-audit')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'publisher')
    with TestClient(app) as client:
        login(client, teacher, inst.slug)
        course = client.post('/api/v1/courses', headers=csrf_headers(client), json={
            'code': 'GRADE2', 'title': 'Grade two', 'grade_level': 'SECONDARY_2'})
        assert course.status_code == 201, course.text
        assert course.json()['grade_level'] == 'SECONDARY_2'
        module = client.post(f"/api/v1/courses/{course.json()['id']}/modules", headers=csrf_headers(client),
                             json={'title': 'QA Unit', 'position': 1}).json()
        lesson = client.post(f"/api/v1/modules/{module['id']}/lessons", headers=csrf_headers(client),
                             json={'title': 'Paid note', 'kind': 'article', 'position': 1, 'price_egp': 50})
        assert lesson.status_code == 201, lesson.text
        assert lesson.json()['price_egp'] == 50
        assert client.post(f"/api/v1/courses/{course.json()['id']}/publish", headers=csrf_headers(client)).status_code == 200
        content = client.get(f"/api/v1/courses/{course.json()['id']}").json()
        assert content['status'] == 'published' and content['grade_level'] == 'SECONDARY_2'
        assert content['modules'][0]['lessons'][0]['price_egp'] == 50


def test_access_401_preserves_csrf_for_refresh_but_rejected_refresh_clears_credentials(db):
    inst = make_institution(db, 'refresh-csrf-audit')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'cookie-owner')
    with TestClient(app) as client:
        login(client, teacher, inst.slug)
        csrf = client.cookies.get('matgar_csrf')
        denied = client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer expired-access-token'})
        assert denied.status_code == 401
        assert denied.headers.get_list('set-cookie') == []
        assert client.cookies.get('matgar_csrf') == csrf
        renewed = client.post('/api/v1/auth/refresh', headers=csrf_headers(client))
        assert renewed.status_code == 200, renewed.text
        assert client.get('/api/v1/auth/me').status_code == 200
        # Use actual logout to revoke this family. A subsequent rejected
        # refresh must clear ALL credential cookies, not grant a new session.
        assert client.post('/api/v1/auth/logout', headers=csrf_headers(client)).status_code == 204
        rejected = client.post('/api/v1/auth/refresh')
        assert rejected.status_code == 401
        removed = rejected.headers.get_list('set-cookie')
        assert all(any(header.startswith(f'{name}=') and 'Max-Age=0' in header for header in removed)
                   for name in ('matgar_session', 'matgar_refresh', 'matgar_csrf'))


def paid_content(db):
    inst = make_institution(db, 'paid-audit')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    student = make_user(db, inst.id, UserRole.STUDENT, 'buyer')
    course = make_course(db, inst, teacher)
    module = CourseModule(course_id=course.id, title='Unit', position=1)
    db.add(module); db.flush()
    lesson = Lesson(module_id=module.id, title='Paid lesson', kind=LessonKind.ARTICLE, position=1, price_egp=25)
    db.add(lesson); db.flush()
    quiz = Quiz(institution_id=inst.id, course_id=course.id, creator_id=teacher.id, lesson_id=lesson.id,
                title='Paid quiz', status=QuizStatus.PUBLISHED, attempts_allowed=3)
    question = Question(institution_id=inst.id, author_id=teacher.id, prompt='Source question',
                        question_type='mcq', options=['A', 'B'], correct_answer='A')
    db.add_all([quiz, question]); db.flush()
    db.add_all([QuizQuestion(quiz_id=quiz.id, question_id=question.id, position=1, points=1),
                Enrollment(course_id=course.id, student_id=student.id, status=EnrollmentStatus.ACTIVE)])
    db.commit()
    return inst, teacher, student, course, lesson, quiz


def test_paid_quiz_bypass_chain_is_rejected(db):
    inst, _, student, _, _, quiz = paid_content(db)
    with TestClient(app) as client:
        login(client, student, inst.slug)
        assert client.get(f'/api/v1/quizzes/{quiz.id}/solve').status_code == 403
        attempt = client.post(f'/api/v1/quizzes/{quiz.id}/attempts', headers=csrf_headers(client))
        evidence = {'start': attempt.status_code}
        if attempt.status_code == 200:
            submitted = client.post(f"/api/v1/quiz-attempts/{attempt.json()['id']}/submit", headers=csrf_headers(client),
                                    json={'answers': [], 'submission_key': uuid.uuid4().hex})
            result = client.get(f'/api/v1/quizzes/{quiz.id}/result')
            evidence.update(submit=submitted.status_code, result=result.status_code)
        assert attempt.status_code == 403, evidence


def test_existing_attempt_cannot_bypass_revoked_lesson_entitlement(db):
    inst, _, student, _, _, quiz = paid_content(db)
    attempt = QuizAttempt(institution_id=inst.id, quiz_id=quiz.id, student_id=student.id, attempt_number=1,
                          started_at=datetime.now(timezone.utc), status=AttemptStatus.IN_PROGRESS)
    db.add(attempt); db.commit()
    with TestClient(app) as client:
        login(client, student, inst.slug)
        assert client.post(f'/api/v1/quiz-attempts/{attempt.id}/submit', headers=csrf_headers(client),
                           json={'answers': [], 'submission_key': uuid.uuid4().hex}).status_code == 403
        assert client.get(f'/api/v1/quizzes/{quiz.id}/result').status_code == 403
        assert client.get(f'/api/v1/quizzes/{quiz.id}/attempts-history').status_code == 403


@pytest.mark.parametrize('actor', ['other_teacher', 'foreign_teacher', 'other_student', 'owner', 'admin'])
def test_access_request_details_are_scoped(db, actor):
    inst, teacher, student, _, lesson, _ = paid_content(db)
    order = PaymentOrder(institution_id=inst.id, student_id=student.id, product_type=PaymentProductType.LESSON,
                         product_id=lesson.id, product_name=lesson.title, amount_egp=25,
                         payment_method=PaymentMethod.INSTAPAY, student_note='Private student note')
    db.add(order); db.commit()
    slug = inst.slug
    if actor == 'owner':
        user = teacher
    elif actor == 'foreign_teacher':
        other = make_institution(db, 'foreign-audit')
        user = make_user(db, other.id, UserRole.TEACHER, 'foreign'); slug = other.slug
    else:
        role = UserRole.INSTITUTION_ADMIN if actor == 'admin' else UserRole.STUDENT if actor == 'other_student' else UserRole.TEACHER
        user = make_user(db, inst.id, role, actor)
    with TestClient(app) as client:
        login(client, user, slug)
        response = client.get(f'/api/v1/lessons/access-requests/{order.id}')
        assert response.status_code == (200 if actor in {'owner', 'admin'} else 404)
        if response.status_code != 200:
            assert 'Private student note' not in response.text


def test_grace_refresh_cookie_is_committed_and_reusable(db):
    inst = make_institution(db, 'refresh-audit')
    user = make_user(db, inst.id, UserRole.STUDENT, 'tabs')
    with TestClient(app) as first, TestClient(app) as second:
        login(first, user, inst.slug)
        second.cookies.update(first.cookies)
        assert first.post('/api/v1/auth/refresh', headers=csrf_headers(first)).status_code == 200
        assert second.post('/api/v1/auth/refresh', headers=csrf_headers(second)).status_code == 200
        token = second.cookies.get('matgar_refresh')
        assert db.query(RefreshSession).filter_by(token_hash=hash_token(token)).first() is not None
        assert second.post('/api/v1/auth/refresh', headers=csrf_headers(second)).status_code == 200


@pytest.mark.parametrize('valid_bearer', [False, True])
def test_logout_always_requires_csrf_for_cookie_session(db, valid_bearer):
    inst = make_institution(db, 'csrf-audit')
    user = make_user(db, inst.id, UserRole.STUDENT, 'cookie')
    with TestClient(app) as client:
        login(client, user, inst.slug)
        token = client.cookies.get('matgar_session') if valid_bearer else 'not-a-valid-token'
        authorization = f'Bearer {token}'
        status = client.post('/api/v1/auth/logout', headers={'Authorization': authorization}).status_code
        assert status == 403


def test_all_paid_assignment_content_paths_reject_unentitled_student(db):
    inst, teacher, student, course, lesson, _ = paid_content(db)
    assignment = Assignment(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
                            lesson_id=lesson.id, title='Protected assignment', prompt='Private prompt',
                            status=AssignmentStatus.PUBLISHED)
    db.add(assignment); db.commit()
    with TestClient(app) as client:
        login(client, student, inst.slug)
        statuses = []
        for path in ('solve', 'sheet.pdf'):
            statuses.append(client.get(f'/api/v1/assignments/{assignment.id}/{path}').status_code)
        statuses.append(client.post(f'/api/v1/assignments/{assignment.id}/attempts', headers=csrf_headers(client)).status_code)
        statuses.append(client.post(f'/api/v1/assignments/{assignment.id}/submissions', headers=csrf_headers(client),
                                    json={'answer_text': 'Attempt bypass', 'idempotency_key': uuid.uuid4().hex}).status_code)
        statuses.append(client.post(f'/api/v1/assignments/{assignment.id}/submissions/file', headers=csrf_headers(client),
                                    files={'file': ('test.pdf', b'%PDF-1.4\nsynthetic', 'application/pdf')}).status_code)
        assert statuses == [403] * 5


def test_manual_essay_is_pending_until_authorized_bounded_grading(db):
    inst, teacher, student, _, lesson, quiz = paid_content(db)
    lesson.price_egp = 0
    link = db.query(QuizQuestion).filter_by(quiz_id=quiz.id).one()
    question = db.get(Question, link.question_id)
    question.question_type = 'essay'; question.options = None; link.points = 5
    other = make_user(db, inst.id, UserRole.TEACHER, 'unrelated')
    db.commit()
    with TestClient(app) as client:
        login(client, student, inst.slug)
        started = client.post(f'/api/v1/quizzes/{quiz.id}/attempts', headers=csrf_headers(client))
        assert started.status_code == 200
        attempt_id = started.json()['id']
        payload = {'answers': [{'question_id': str(question.id), 'answer': 'Original student essay'}], 'submission_key': uuid.uuid4().hex}
        assert client.post(f'/api/v1/quiz-attempts/{attempt_id}/submit', headers=csrf_headers(client), json=payload).status_code == 200
        result = client.get(f'/api/v1/quizzes/{quiz.id}/result').json()
        assert result['grading_status'] == 'pending'
        assert result['summary'] is None and result['score'] is None
        path = f'/api/v1/quiz-attempts/{attempt_id}/answers/{question.id}/grade'
        assert client.post(path, json={'awarded_points': 3}, headers=csrf_headers(client)).status_code == 403
        login(client, other, inst.slug)
        assert client.get(f'/api/v1/students/{student.id}/quiz-solution').status_code == 404
        assert client.post(path, json={'awarded_points': 3}, headers=csrf_headers(client)).status_code == 404
        login(client, teacher, inst.slug)
        managed = client.get('/api/v1/users?role=student')
        assert managed.status_code == 200
        summary = next(item for item in managed.json() if item['id'] == str(student.id))
        assert summary['has_completed_exam'] is True
        assert summary['quiz_attempts_count'] == summary['pending_quiz_attempts'] == 1
        assert summary['average_quiz_score'] is None
        assert client.post(path, json={'awarded_points': 6}, headers=csrf_headers(client)).status_code == 422
        assert client.post(path, json={'awarded_points': -1}, headers=csrf_headers(client)).status_code == 422
        graded = client.post(path, json={'awarded_points': 3, 'feedback': 'Explain units next time'}, headers=csrf_headers(client))
        assert graded.status_code == 200, graded.text
        assert graded.json()['score'] == 3
        summary = next(item for item in client.get('/api/v1/users?role=student').json() if item['id'] == str(student.id))
        assert summary['pending_quiz_attempts'] == 0
        assert summary['average_quiz_score'] == 60
        approval = client.post(f'/api/v1/quiz-attempts/{attempt_id}/approve', headers=csrf_headers(client))
        assert approval.status_code == 200, approval.text
        login(client, student, inst.slug)
        result = client.get(f'/api/v1/quizzes/{quiz.id}/result').json()
        assert result['grading_status'] == 'complete'
        assert result['score'] == 3
        assert result['questions'][0]['feedback'] == 'Explain units next time'
        answer = db.query(QuizAttemptAnswer).filter_by(attempt_id=uuid.UUID(attempt_id)).one()
        assert answer.answer == 'Original student essay'
        assert answer.graded_by == teacher.id


def test_refresh_grace_does_not_reactivate_disabled_user(db):
    inst = make_institution(db, 'disabled-grace')
    user = make_user(db, inst.id, UserRole.STUDENT, 'disabled')
    with TestClient(app) as first, TestClient(app) as second:
        login(first, user, inst.slug); second.cookies.update(first.cookies)
        assert first.post('/api/v1/auth/refresh', headers=csrf_headers(first)).status_code == 200
        user.is_active = False; db.commit()
        status = second.post('/api/v1/auth/refresh', headers=csrf_headers(second)).status_code
        assert status == 401


def test_production_video_session_admission_never_falls_back_to_local_counts(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.api.routes import platform
    monkeypatch.setattr(platform, 'get_settings', lambda: SimpleNamespace(
        video_max_concurrent_sessions=2, redis_required=True, app_env='production'))
    monkeypatch.setattr(platform, '_video_session_redis', lambda: None)
    with pytest.raises(HTTPException) as denied:
        platform._register_video_session(None, uuid.uuid4(), uuid.uuid4(), 'synthetic-session', 300)
    assert denied.value.status_code == 503
    assert denied.value.headers['Retry-After'] == '2'
