"""Real overlapping HTTP requests, two API workers and isolated PostgreSQL."""
import concurrent.futures
import threading
import uuid

import pytest
import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.course import Enrollment
from app.models.payment import PaymentOrder, StudentEntitlement
from app.models.platform import AssignmentAttempt, QuizAttempt, QuizAttemptAnswer
from app.models.user import User, UserRole
from app.services.auth_service import request_password_reset
from .live_helpers import BASE, clear_auth, lesson, pg_engine, session


def overlap(source, requests_to_send):
    """Independent TCP/cookie jars released by a barrier, not sequential calls."""
    barrier = threading.Barrier(len(requests_to_send))
    def send(spec):
        client = requests.Session()
        client.verify = source.verify
        client.headers.update(source.headers)
        client.cookies.update(source.cookies)
        barrier.wait(timeout=10)
        response = client.request(spec[0], BASE + spec[1], json=spec[2], timeout=30)
        return client, response
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(requests_to_send)) as pool:
        return list(pool.map(send, requests_to_send))


def assessment(teacher, course, item, kind='quizzes', essay=False):
    payload = {'course_id': course['id'], 'lesson_id': item['id'], 'title': 'Concurrency assessment'}
    question_id = None
    if kind == 'quizzes':
        question = teacher.post(BASE + '/questions', json={'course_id': course['id'], 'prompt': 'Explain conservation of mass',
                                  'question_type': 'essay' if essay else 'mcq', 'points': 5,
                                  'options': None if essay else ['A', 'B'], 'correct_answer': None if essay else 'A'}, timeout=15)
        assert question.status_code == 201, question.text
        question_id = question.json()['id']; payload['question_ids'] = [question_id]
    else:
        payload['prompt'] = 'Explain the steps and units'; payload['max_score'] = 5
    created = teacher.post(BASE + '/' + kind, json=payload, timeout=15)
    assert created.status_code == 201, created.text
    item_id = created.json()['id']
    assert teacher.post(f'{BASE}/{kind}/{item_id}/publish', timeout=15).status_code == 200
    return item_id, question_id


@pytest.mark.parametrize('kind', ['quizzes', 'assignments'])
def test_concurrent_starts_return_one_active_attempt(kind):
    clear_auth()
    engine = pg_engine()
    with session() as teacher, session('student01@demo.com', 'qa-student-pass') as student:
        course, item = lesson(teacher)
        assert student.post(f"{BASE}/courses/{course['id']}/enroll", timeout=15).status_code == 200
        item_id, _ = assessment(teacher, course, item, kind)
        responses = overlap(student, [('POST', f'/{kind}/{item_id}/attempts', None)] * 2)
        statuses = [response.status_code for _, response in responses]
        assert statuses == [200, 200], statuses
        ids = [response.json()['id'] for _, response in responses]
        assert len(set(ids)) == 1
        with Session(engine) as db:
            model = QuizAttempt if kind == 'quizzes' else AssignmentAttempt
            assert db.scalar(select(func.count()).select_from(model).where(model.id == uuid.UUID(ids[0]))) == 1
        for client, _ in responses: client.close()
    engine.dispose()


def test_concurrent_quiz_submissions_no_duplicate_answers():
    clear_auth(); engine = pg_engine()
    with session() as teacher, session('student01@demo.com', 'qa-student-pass') as student:
        course, item = lesson(teacher)
        assert student.post(f"{BASE}/courses/{course['id']}/enroll", timeout=15).status_code == 200
        quiz_id, question_id = assessment(teacher, course, item)
        attempt = student.post(f'{BASE}/quizzes/{quiz_id}/attempts', timeout=15).json()['id']
        payload = {'submission_key': uuid.uuid4().hex, 'answers': [{'question_id': question_id, 'answer': 'A'}]}
        responses = overlap(student, [('POST', f'/quiz-attempts/{attempt}/submit', payload)] * 2)
        assert [r.status_code for _, r in responses] == [200, 200]
        assert [r.json()['score'] for _, r in responses] == [5, 5]
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(QuizAttemptAnswer).where(QuizAttemptAnswer.attempt_id == uuid.UUID(attempt))) == 1
        for client, _ in responses: client.close()
    engine.dispose()


def test_concurrent_refresh_issues_persisted_reusable_cookies():
    clear_auth()
    with session('student02@demo.com', 'qa-student-pass') as student:
        responses = overlap(student, [('POST', '/auth/refresh', None)] * 2)
        statuses = [response.status_code for _, response in responses]
        assert statuses == [200, 200], statuses
        for client, response in responses:
            client.headers['Authorization'] = 'Bearer ' + response.json()['token']
            client.headers['X-CSRF-Token'] = client.cookies.get('matgar_csrf')
            refreshed = client.post(BASE + '/auth/refresh', timeout=15)
            status = refreshed.status_code
            assert status == 200, status
            client.headers['Authorization'] = 'Bearer ' + refreshed.json()['token']
            assert client.get(BASE + '/auth/me', timeout=15).status_code == 200
            client.close()


@pytest.mark.parametrize('path', ['access', 'payments'])
def test_concurrent_creation_and_opposing_reviews_have_one_outcome(path):
    clear_auth(); engine = pg_engine()
    with session() as teacher, session('student03@demo.com', 'qa-student-pass') as student:
        course, item = lesson(teacher, price=25)
        if path == 'access':
            create_path = f"/lessons/{item['id']}/access-requests"; payload = {'student_note': 'Private synthetic request'}
            review_prefix = '/lessons/access-requests/'
        else:
            create_path = '/payments/orders'; payload = {'product_type': 'lesson', 'product_id': item['id'], 'payment_method': 'instapay'}
            review_prefix = '/payments/orders/'
        responses = overlap(student, [('POST', create_path, payload)] * 2)
        assert all(r.status_code == 201 for _, r in responses), [r.status_code for _, r in responses]
        ids = [r.json()['id'] for _, r in responses]; assert len(set(ids)) == 1
        reviews = overlap(teacher, [('POST', review_prefix + ids[0] + '/approve', {'note': 'Approved'}),
                                    ('POST', review_prefix + ids[0] + '/reject', {'note': 'Rejected'})])
        statuses = sorted(r.status_code for _, r in reviews)
        assert statuses == [200, 409], statuses
        with Session(engine) as db:
            order = db.get(PaymentOrder, uuid.UUID(ids[0]))
            rows = db.scalar(select(func.count()).select_from(StudentEntitlement).where(StudentEntitlement.source_order_id == order.id))
            assert rows == (1 if str(order.status) == 'paid' else 0)
            assert db.scalar(select(func.count()).select_from(PaymentOrder).where(PaymentOrder.product_id == uuid.UUID(item['id']))) == 1
            enrollment_count = db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.student_id == order.student_id,
                                                                                           Enrollment.course_id == uuid.UUID(course['id'])))
            assert enrollment_count == rows
        for client, _ in responses + reviews: client.close()
    engine.dispose()


def test_concurrent_reset_token_can_be_consumed_only_once():
    clear_auth(); engine = pg_engine(); stamp = uuid.uuid4().hex
    with session() as teacher:
        tenant = teacher.get(BASE + '/auth/me', timeout=15).json()['institution_id']
    with Session(engine) as db:
        user = User(institution_id=uuid.UUID(tenant), email=f'reset-{stamp}@example.com', username=f'reset-{stamp}',
                    display_name='Synthetic reset race', role=UserRole.STUDENT, password_hash=hash_password('old-password-123'))
        db.add(user); db.commit()
        token = request_password_reset(db, user.email, 'demo')
    source = requests.Session(); source.verify = __import__('os').environ['QA_CA_FILE']
    responses = overlap(source, [('POST', '/auth/password-reset/confirm', {'token': token, 'new_password': 'new-password-123'})] * 2)
    assert sorted(r.status_code for _, r in responses) == [204, 400]
    for client, _ in responses: client.close()
    source.close(); engine.dispose()
