"""New inverse/security boundaries for the seven concrete repairs."""
from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.config import get_settings
from app.core.question_policy import validate_question_content
from app.core.mcq_answers import option_index
from app.core import rate_limit
from app.models.course import CourseModule, Lesson, LessonKind
from app.models.payment import StudentEntitlement, EntitlementType
from app.models.progress import LessonProgress, VideoEvent
from tests.test_security_and_tenancy import login, csrf_headers
from tests.test_seven_user_regressions import domain, exam, asgi_request_without_body


@pytest.mark.parametrize('correct', ['أ', 'ا', 'A', 'الهيدروجين'])
def test_new_publication_policy_accepts_equivalent_valid_mcq_keys(correct):
    validate_question_content(SimpleNamespace(prompt='اختر الغاز الصحيح', points=10,
        question_type='mcq', options=['الهيدروجين', 'الأكسجين'], correct_answer=correct))


def test_explicit_shuffled_keys_and_unknown_or_ambiguous_choices():
    options = [{'key': 'B', 'text': 'Oxygen'}, {'key': 'A', 'text': 'Hydrogen'}]
    assert option_index('A', options) == option_index('Hydrogen', options) == 1
    assert option_index('Z', options) is None
    assert option_index('', options) is None
    assert option_index({'answer': 'A'}, options) is None
    assert option_index('Same', ['Same', 'Same']) is None


def test_result_and_teacher_solution_show_canonical_choice_letters(db):
    inst, teacher, student, course = domain(db)
    quiz, question, _ = exam(db, inst, teacher, student, course)
    with login(TestClient(app), student, inst.slug) as learner:
        opened = learner.get(f'/api/v1/quizzes/{quiz.id}/solve').json()
        response = learner.post(f'/api/v1/quiz-attempts/{opened["attempt"]["id"]}/submit',
            headers=csrf_headers(learner), json={'submission_key': uuid.uuid4().hex,
                'answers': [{'question_id': str(question.id), 'answer': 'الهيدروجين'}]})
        assert response.status_code == 200
        result = learner.get(f'/api/v1/quizzes/{quiz.id}/result')
        assert result.status_code == 200, result.text
        assert result.json()['questions'][0]['correct_answer_letter'] == 0
        assert result.json()['questions'][0]['student_answer_letter'] == 0
    with login(TestClient(app), teacher, inst.slug) as owner:
        result = owner.get(f'/api/v1/students/{student.id}/quiz-solution?quiz_id={quiz.id}')
        assert result.status_code == 200, result.text
        assert result.json()['questions'][0]['correct_answer_letter'] == 'A'
        assert result.json()['questions'][0]['student_answer_letter'] == 'A'


@pytest.mark.parametrize('mode', ['valid', 'wrong-role', 'revoked', 'bearer-precedence'])
def test_upload_preflight_validates_real_role_revocation_and_bearer_precedence(db, mode):
    inst, teacher, student, _ = domain(db)
    with login(TestClient(app), student if mode == 'wrong-role' else teacher, inst.slug) as client:
        cookie = '; '.join(f'{key}={value}' for key, value in client.cookies.items()).encode()
        headers = [(b'cookie', cookie), (b'x-csrf-token', client.cookies.get('matgar_csrf').encode())]
        if mode == 'revoked':
            assert client.post('/api/v1/auth/logout', headers=csrf_headers(client)).status_code == 204
        elif mode == 'bearer-precedence':
            headers.append((b'authorization', b'Bearer invalid-session'))
        received, status = asgi_request_without_body('/api/v1/quiz/extract-from-file', headers)
        if mode == 'valid':
            assert status == 400  # Auth passed; only then is the malformed body parsed.
            assert received
        else:
            assert status == (403 if mode == 'wrong-role' else 401)
            assert received == []


def test_anonymous_upload_still_consumes_real_rate_limit_budget(db, monkeypatch):
    monkeypatch.setattr(rate_limit, '_get_redis_client', lambda: None)
    monkeypatch.setattr(get_settings(), 'rate_limit_quiz_extraction', 1)
    assert asgi_request_without_body('/api/v1/quiz/extract-from-file') == ([], 401)
    assert asgi_request_without_body('/api/v1/quiz/extract-from-file') == ([], 429)


def test_auth_database_outage_fails_closed_without_reading_upload(db, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from app.core import upload_auth
    def unavailable():
        raise SQLAlchemyError('synthetic database outage')
    monkeypatch.setattr(upload_auth, 'SessionLocal', unavailable)
    assert asgi_request_without_body('/api/v1/quiz/extract-from-file') == ([], 503)


def test_paid_progress_is_allowed_after_entitlement_and_denied_atomically_before_it(db):
    inst, teacher, student, course = domain(db)
    module = CourseModule(course_id=course.id, title='Unit', position=1)
    db.add(module); db.flush()
    lessons = [Lesson(module_id=module.id, title=title, kind=LessonKind.VIDEO,
                position=index, price_egp=price) for index, (title, price) in enumerate([('Free', 0), ('Paid', 50)], 1)]
    db.add_all(lessons); db.commit()
    def events():
        return {'events': [{'lesson_id': str(row.id), 'client_event_id': uuid.uuid4().hex,
                'event_type': 'ended', 'position_seconds': 100, 'duration_seconds': 100} for row in lessons]}
    with login(TestClient(app), student, inst.slug) as client:
        response = client.post('/api/v1/telemetry/video-events', headers=csrf_headers(client), json=events())
        assert response.status_code == 403
        assert db.scalar(select(VideoEvent.id)) is None
        assert db.scalar(select(LessonProgress.id)) is None
        db.add(StudentEntitlement(institution_id=inst.id, student_id=student.id,
            entitlement_type=EntitlementType.LESSON, resource_id=lessons[1].id,
            starts_at=datetime(2020, 1, 1, tzinfo=timezone.utc)))
        db.commit()
        response = client.post('/api/v1/telemetry/video-events', headers=csrf_headers(client), json=events())
        assert response.status_code == 202, response.text
        assert response.json()['accepted'] == 2
        assert client.post(f'/api/v1/progress/lessons/{lessons[1].id}/complete', headers=csrf_headers(client)).status_code == 200
