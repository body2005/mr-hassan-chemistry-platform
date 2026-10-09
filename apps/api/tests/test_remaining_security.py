"""Regressions for the 4298486 review, through real routes where applicable."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from app.main import app
from app.core import config, rate_limit
from app.core.security import create_session_token
from app.core.storage import LocalStorageProvider
from app.models.course import Enrollment, EnrollmentStatus, CourseModule, Lesson, LessonKind
from app.models.extended import LearningObjective
from app.models.user import UserRole, PasswordResetToken
from app.models.platform import RefreshSession, RevokedSession, Quiz, QuizStatus, QuizQuestion, QuizAttempt, AttemptStatus, QuizAttemptAnswer, Question, Assignment, AssignmentStatus, AssignmentSubmission, Notification, AuditLog
from app.models.progress import LessonProgress
from app.schemas import PasswordResetConfirm, ChangePasswordRequest, QuestionCreateRequest
from app.services import auth_service
from app.services import session_maintenance as maintenance
from tests.test_security_and_tenancy import make_institution, make_user, make_course, login, csrf_headers
from tests.test_production_config import production_settings


def account(db):
    institution = make_institution(db, 'remaining')
    user = make_user(db, institution.id, UserRole.STUDENT, 'remaining')
    client = TestClient(app)
    login(client, user, institution.slug)
    return institution, user, client


def test_login_short_pair_budget_precedes_hash_and_expires_without_account_lockout(db, monkeypatch):
    inst = make_institution(db, 'login-short-backoff')
    user = make_user(db, inst.id, UserRole.STUDENT, 'short')
    other = make_user(db, inst.id, UserRole.STUDENT, 'other')
    client = TestClient(app)
    monkeypatch.setattr(rate_limit, '_get_redis_client', lambda: None)
    seen = []
    original = auth_service.authenticate
    def count(*args):
        seen.append(True)
        return original(*args)
    monkeypatch.setattr(auth_service, 'authenticate', count)
    wrong = {'email': user.email, 'password': 'Incorrect-synthetic-2026!', 'institution_slug': inst.slug}
    assert [client.post('/api/v1/auth/login', json=wrong).status_code for _ in range(4)] == [401] * 4
    blocked = client.post('/api/v1/auth/login', json=wrong)
    assert blocked.status_code == 429 and len(seen) == 4
    assert 1 <= int(blocked.headers['Retry-After']) <= 10
    assert all(user.email not in key and inst.slug not in key for key in rate_limit._windows)
    account_budgets = [values for key, values in rate_limit._windows.items() if key.startswith('rate-limit:login_account:')]
    assert len(account_budgets) == 1 and len(account_budgets[0]) == 4
    # Same-IP different account is not locked by the short pair budget.
    login(client, other, inst.slug)
    time.sleep(10.1)
    login(client, user, inst.slug)
    assert len(seen) == 6


def test_summary_scope_students_teachers_admins_and_other_tenant(db):
    inst = make_institution(db, 'summary-scope')
    other = make_institution(db, 'summary-other')
    t1 = make_user(db, inst.id, UserRole.TEACHER, 'one')
    t2 = make_user(db, inst.id, UserRole.TEACHER, 'two')
    outsider = make_user(db, other.id, UserRole.TEACHER, 'other')
    admin = make_user(db, inst.id, UserRole.INSTITUTION_ADMIN, 'admin')
    students = [make_user(db, inst.id, UserRole.STUDENT, str(i)) for i in range(3)]
    c1, c2 = make_course(db, inst, t1), make_course(db, inst, t2)
    make_course(db, other, outsider)
    for student, course in zip(students, [c1, c2, c2]):
        db.add(Enrollment(student_id=student.id, course_id=course.id, status=EnrollmentStatus.ACTIVE))
    db.commit()
    quizzes_by_course = []
    for course, teacher, student, score in [(c1, t1, students[0], 10), (c2, t2, students[1], 90)]:
        module = CourseModule(course_id=course.id, title='Summary unit', position=1)
        db.add(module); db.flush()
        lesson = Lesson(module_id=module.id, title='Summary lesson', kind=LessonKind.ARTICLE, position=1)
        quiz = Quiz(institution_id=inst.id, course_id=course.id, creator_id=teacher.id, title='Summary quiz', status=QuizStatus.PUBLISHED)
        question = Question(institution_id=inst.id, author_id=teacher.id, course_id=course.id,
                            question_type='essay', prompt='Synthetic answer', points=100)
        assignment = Assignment(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
                                title='Summary assignment', prompt='Synthetic prompt', status=AssignmentStatus.PUBLISHED)
        db.add_all([lesson, quiz, question, assignment]); db.flush()
        quizzes_by_course.append(str(quiz.id))
        for number, practice, pending in [(1, False, False), (2, True, False), (3, False, True)]:
            attempt = QuizAttempt(institution_id=inst.id, quiz_id=quiz.id, student_id=student.id,
                attempt_number=number, started_at=datetime.now(timezone.utc), score=score if number == 1 else 999,
                is_practice=practice, total_points=100,
                status=AttemptStatus.IN_PROGRESS if pending else AttemptStatus.SUBMITTED,
                submitted_at=None if pending else datetime.now(timezone.utc))
            db.add(attempt); db.flush()
            db.add(QuizAttemptAnswer(attempt_id=attempt.id, question_id=question.id,
                awarded_points=score, graded_at=None if pending else datetime.now(timezone.utc)))
        db.add(AssignmentSubmission(institution_id=inst.id, assignment_id=assignment.id, student_id=student.id,
            version=1, answer_text='Synthetic', idempotency_key=uuid.uuid4().hex, submitted_at=datetime.now(timezone.utc)))
        db.add(LessonProgress(institution_id=inst.id, lesson_id=lesson.id, student_id=student.id,
            completion_percent=100 if teacher == t1 else 0))
    db.commit()
    for viewer, count, quizzes, avg, completion, top in [
        (t1, 1, 1, 10, 100, [quizzes_by_course[0]]), (t2, 2, 1, 90, 0, [quizzes_by_course[1]]),
        (admin, 3, 2, 50, 33.33, list(reversed(quizzes_by_course)))]:
        client = TestClient(app); login(client, viewer, inst.slug)
        response = client.get('/api/v1/reports/summary')
        assert response.status_code == 200, response.text
        assert response.json()['students_count'] == count
        assert response.json()['quizzes_count'] == quizzes
        assert response.json()['lessons_count'] == quizzes
        assert response.json()['assignments_count'] == quizzes
        assert response.json()['quiz_avg_score'] == avg
        assert response.json()['quiz_completion_rate'] == round(quizzes / count * 100, 2)
        assert response.json()['assignment_submission_rate'] == round(quizzes / count * 100, 2)
        assert response.json()['lesson_completion_rate'] == completion
        assert [q['quiz_id'] for q in response.json()['top_quizzes']] == top
    client = TestClient(app); login(client, students[0], inst.slug)
    assert client.get('/api/v1/reports/summary').status_code == 403


@pytest.mark.parametrize('access', ['missing', 'invalid', 'valid'])
def test_logout_refresh_fallback_revokes_only_current_device(db, access):
    inst, user, client = account(db)
    second = TestClient(app); login(second, user, inst.slug)
    copied = TestClient(app); copied.cookies.update(client.cookies)
    if access != 'valid':
        client.cookies.delete('matgar_session')
        if access == 'invalid':
            client.cookies.set('matgar_session', 'expired-or-invalid')
    response = client.post('/api/v1/auth/logout', headers=csrf_headers(client))
    assert response.status_code == 204, response.text
    assert copied.post('/api/v1/auth/refresh', headers=csrf_headers(copied)).status_code == 401
    assert second.get('/api/v1/auth/me').status_code == 200
    assert not client.cookies.get('matgar_refresh')


@pytest.mark.parametrize('operation', ['reset', 'change'])
def test_password_change_invalidates_all_outstanding_reset_links(db, operation):
    inst, user, _client = account(db)
    first = auth_service.request_password_reset(db, user.email, inst.slug)
    second = auth_service.request_password_reset(db, user.email, inst.slug)
    if operation == 'reset':
        auth_service.reset_password(db, PasswordResetConfirm(token=first, new_password='Replacement-QA-2026!'))
    else:
        auth_service.change_password(db, user, ChangePasswordRequest(current_password='password-123456', new_password='Replacement-QA-2026!'))
        db.commit()
    with pytest.raises(ValueError, match='invalid or expired'):
        auth_service.reset_password(db, PasswordResetConfirm(token=second, new_password='Another-QA-2026!'))
    assert db.query(PasswordResetToken).filter(PasswordResetToken.used_at.is_(None)).count() == 0


def test_general_query_credentials_are_not_authentication(db):
    _inst, user, client = account(db)
    credential = client.cookies.get('matgar_session')
    anonymous = TestClient(app)
    assert anonymous.get('/api/v1/auth/me', params={'token': credential}).status_code == 401
    assert anonymous.get('/api/v1/reports/summary', params={'token': credential}).status_code == 401
    assert anonymous.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + credential}).status_code == 200


@pytest.mark.parametrize('environment', ['production', 'production_like', 'staging'])
def test_all_deployment_environments_reject_insecure_defaults(environment, monkeypatch):
    for values in [dict(secret_key='development-only-change-me'), dict(cookie_secure=False),
                   dict(frontend_origins='http://localhost:5173')]:
        with pytest.raises(ValidationError):
            production_settings(app_env=environment, **values)
    assert production_settings(app_env=environment).secure_cookies
    monkeypatch.setenv('DISABLE_RATE_LIMITING', 'true')
    with pytest.raises(ValidationError, match='cannot be disabled'):
        production_settings(app_env=environment)


@pytest.mark.parametrize('name', ['session_cookie_name', 'refresh_cookie_name', 'csrf_cookie_name'])
def test_cookie_names_are_an_explicit_fixed_browser_contract(name):
    with pytest.raises(ValidationError):
        config.Settings(_env_file=None, **{name: 'unsupported-custom-cookie'})


@pytest.mark.parametrize('key', ['../outside.txt', '..\\outside.txt', 'nested/../../outside.txt'])
def test_storage_rejects_traversal_for_every_operation(tmp_path, key):
    provider = LocalStorageProvider(str(tmp_path / 'root'))
    for operation in [provider.get_local_path, provider.get_size, provider.exists, provider.delete,
                      lambda path: provider.save_bytes(b'test', path), lambda path: list(provider.open_stream(path))]:
        with pytest.raises(ValueError):
            operation(key)


def test_storage_allows_only_contained_absolute_legacy_keys(tmp_path):
    provider = LocalStorageProvider(str(tmp_path / 'root'))
    inside = provider.save_bytes(b'protected', 'nested/valid')
    outside = tmp_path / 'outside'
    outside.write_bytes(b'untouched')
    assert provider.get_size(inside) == 9
    assert b''.join(provider.open_stream(inside)) == b'protected'
    for operation in [provider.get_local_path, provider.get_size, provider.exists, provider.delete]:
        with pytest.raises(ValueError):
            operation(str(outside))
    assert outside.read_bytes() == b'untouched'


def test_storage_symlink_escape_is_rejected(tmp_path):
    provider = LocalStorageProvider(str(tmp_path / 'root'))
    outside = tmp_path / 'outside'; outside.mkdir()
    try:
        (tmp_path / 'root' / 'escape').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Host needs symlink privilege; mandatory Linux Docker gate executes this test')
    with pytest.raises(ValueError):
        provider.save_bytes(b'test', 'escape/new')
    assert not (outside / 'new').exists()


def test_reset_sixth_request_is_rejected_after_middleware(monkeypatch):
    from app.api.routes import auth
    monkeypatch.setattr(auth, 'password_reset_mail_configured', lambda: True)
    client = TestClient(app)
    codes = [client.post('/api/v1/auth/password-reset/request', json={'email': 'unknown@example.com', 'institution_slug': 'missing'}).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]


def test_metadata_cannot_replace_csrf_and_cross_site_without_origin_is_rejected(db):
    _inst, _user, client = account(db)
    assert client.post('/api/v1/auth/logout', headers={'Sec-Fetch-Site': 'cross-site', **csrf_headers(client)}).status_code == 403
    assert client.post('/api/v1/auth/logout', headers={'Origin': 'http://localhost:5173', 'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert client.post('/api/v1/auth/logout', headers={'Origin': 'http://localhost:5173', 'Sec-Fetch-Site': 'cross-site', **csrf_headers(client)}).status_code == 204


def test_deployment_rate_limit_cannot_be_disabled_after_settings_are_cached(monkeypatch):
    from starlette.requests import Request
    monkeypatch.setattr(rate_limit, 'get_settings', lambda: SimpleNamespace(deployment_environment=True))
    monkeypatch.setenv('DISABLE_RATE_LIMITING', 'true')
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        rate_limit.enforce_rate_limit(Request({'type': 'http', 'headers': []}))
    assert error.value.status_code == 503


@pytest.mark.parametrize('scope', ['global', 'course'])
def test_objective_duplicate_same_scope_is_rejected_but_other_scopes_allowed(db, scope):
    inst = make_institution(db, 'objective-scope')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'objective')
    course = make_course(db, inst, teacher)
    target = course.id if scope == 'course' else None
    db.add(LearningObjective(institution_id=inst.id, course_id=target, code='CHEM-1', title='One')); db.commit()
    db.add(LearningObjective(institution_id=inst.id, course_id=target, code='CHEM-1', title='Duplicate'))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(LearningObjective(institution_id=inst.id, course_id=None if target else course.id, code='CHEM-1', title='Other scope')); db.commit()
    assert db.query(LearningObjective).count() == 2


@pytest.mark.parametrize('kind', ['mcq', 'multiple_choice'])
def test_mcq_option_limit_matches_text_keys_without_rewriting_history(kind):
    from app.services.platform_service import _validate_quiz_question
    question = QuestionCreateRequest(question_type=kind, prompt='Select the last option',
        options=[f'Choice {n}' for n in range(26)], correct_answer='Z')
    _validate_quiz_question(question)
    with pytest.raises(ValidationError, match='at most 26'):
        QuestionCreateRequest(question_type=kind, prompt='Select option 27',
            options=[f'Choice {n}' for n in range(27)], correct_answer='[')


def test_mail_outbox_retries_without_request_delivery_and_erases_secret(monkeypatch, db):
    inst, user, _client = account(db)
    from app.models.mail_outbox import ResetMailOutbox
    raw = auth_service.request_password_reset(db, user.email, inst.slug, enqueue_mail=True)
    job = db.query(ResetMailOutbox).one()
    assert raw not in job.encrypted_token
    assert maintenance.token_cipher().decrypt(job.encrypted_token.encode()).decode() == raw
    monkeypatch.setattr(maintenance, 'send_password_reset_email', lambda *_args, **_kw: (_ for _ in ()).throw(ConnectionError('synthetic SMTP outage')))
    assert maintenance.deliver_reset_mail() == 0
    db.expire_all(); job = db.query(ResetMailOutbox).one()
    assert job.attempts == 1 and job.completed_at is None
    job.retry_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
    sent = []
    monkeypatch.setattr(maintenance, 'send_password_reset_email', lambda *args, **kwargs: sent.append((args, kwargs)))
    assert maintenance.deliver_reset_mail() == 1
    assert maintenance.deliver_reset_mail() == 0
    db.expire_all()
    assert db.query(ResetMailOutbox).one().encrypted_token is None
    assert len(sent) == 1


def test_cleanup_keeps_live_and_unexpired_replay_evidence(db):
    _inst, user, _client = account(db)
    now = datetime.now(timezone.utc)
    for days, revoked in [(-8, True), (-1, True), (1, True), (1, False)]:
        db.add(RefreshSession(token_hash=uuid.uuid4().hex, family_id=uuid.uuid4(), jti=uuid.uuid4().hex,
            user_id=user.id, expires_at=now + timedelta(days=days), revoked_at=now if revoked else None))
    db.commit()
    assert maintenance.cleanup_expired_sessions() == 1
    assert maintenance.cleanup_expired_sessions() == 0
    assert db.query(RefreshSession).count() == 4  # Login family plus three retained rows.


def test_registration_contact_details_persist_without_sms_or_teacher_privilege(db):
    from app.models.user import User
    inst = make_institution(db, 'new-registration'); db.commit()
    client = TestClient(app)
    payload = {
        'display_name':'طالب اختبار جديد', 'email':'new-wizard@example.com', 'password':'Registration-QA-2026!',
        'institution_slug':inst.slug, 'grade_level':'SECONDARY_3', 'gender':'MALE',
        'student_phone':'٠١٠١٢٣٤٥٦٧٨', 'guardian_phone':'01112345678', 'mother_phone':'01212345678',
        'governorate':'CAIRO', 'school_name':'مدرسة اختبار', 'city':'  البساتين  ',
        'education_division':'AZHAR', 'specialization':'MATH', 'role':'teacher'}
    assert client.post('/api/v1/auth/register', json=payload).status_code == 422
    del payload['role']
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 201, response.text
    assert 'token' not in response.json()
    user = db.query(User).filter(User.email == 'new-wizard@example.com').one()
    assert user.role == UserRole.STUDENT
    assert (user.student_phone, user.mother_phone, user.city, user.education_division, user.specialization) == (
        '01012345678', '01212345678', 'البساتين', 'AZHAR', 'MATH')


@pytest.mark.parametrize('explicit', [False, True])
@pytest.mark.parametrize('kind', ['mcq', 'multiple_choice'])
def test_http_mcq_boundary_and_legacy_publication_reject_27_without_500(db, explicit, kind):
    inst = make_institution(db, 'choice-policy')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'choice-policy')
    course = make_course(db, inst, teacher)
    client = TestClient(app); login(client, teacher, inst.slug)
    def choices(count):
        return [{'key':chr(65+n), 'text':f'Choice {n}'} for n in range(count)] if explicit else [f'Choice {n}' for n in range(count)]
    question = dict(course_id=str(course.id), prompt='Select the last choice', question_type=kind,
                    options=choices(26), correct_answer='Z', points=1)
    response = client.post('/api/v1/questions', json=question, headers=csrf_headers(client))
    assert response.status_code == 201, response.text
    stored_id = uuid.UUID(response.json()['id'])
    question['options'] = choices(27); question['correct_answer'] = '['
    oversized = client.post('/api/v1/questions', json=question, headers=csrf_headers(client))
    assert oversized.status_code == 422, oversized.text
    draft = {'course_id':str(course.id), 'title':'Boundary QA', 'idempotency_key':uuid.uuid4().hex, 'questions':[question]}
    oversized_draft = client.post('/api/v1/quizzes/publish-draft', json=draft, headers=csrf_headers(client))
    assert oversized_draft.status_code == 422, oversized_draft.text
    stored = db.get(Question, stored_id)
    stored.options = choices(27); stored.correct_answer = '['
    legacy = Quiz(institution_id=inst.id, course_id=course.id, creator_id=teacher.id, title='Legacy invalid choices')
    db.add(legacy); db.flush()
    db.add(QuizQuestion(quiz_id=legacy.id, question_id=stored.id, position=1, points=1)); db.commit()
    rejected = client.post(f'/api/v1/quizzes/{legacy.id}/publish', headers=csrf_headers(client))
    assert rejected.status_code == 400, rejected.text
    assert '26' in rejected.json()['detail']


def test_refresh_replay_does_not_extend_grace_and_sends_one_security_notice(db):
    from app.core.security import hash_token
    _inst, user, client = account(db)
    replay = TestClient(app); replay.cookies.update(client.cookies)
    original_hash = hash_token(client.cookies.get('matgar_refresh'))
    assert client.post('/api/v1/auth/refresh', headers=csrf_headers(client)).status_code == 200
    row = db.query(RefreshSession).filter(RefreshSession.token_hash == original_hash).one()
    assert row.replaced_by
    row.revoked_at = datetime.now(timezone.utc) - timedelta(seconds=config.get_settings().refresh_replay_grace_seconds + 1)
    db.commit()
    saved_cookies = dict(replay.cookies)
    for _ in range(3):
        replay.cookies.clear(); replay.cookies.update(saved_cookies)
        assert replay.post('/api/v1/auth/refresh', headers=csrf_headers(replay)).status_code == 401
    assert client.get('/api/v1/auth/me').status_code == 401
    assert db.query(Notification).filter(Notification.recipient_id == user.id, Notification.kind == 'security').count() == 1
    assert db.query(AuditLog).filter(AuditLog.actor_id == user.id, AuditLog.action == 'refresh_reuse_detected').count() == 1


def test_readiness_does_not_queue_new_work_while_a_probe_is_slow(monkeypatch):
    from app.api.routes import health
    from concurrent.futures import TimeoutError
    from fastapi import HTTPException
    class SlowProbe:
        def result(self, timeout):
            assert timeout == 2
            raise TimeoutError()
        def done(self):
            return False
    scheduled = []
    monkeypatch.setattr(health, 'get_settings', lambda: SimpleNamespace(app_env='production'))
    monkeypatch.setattr(health, '_probe_future', None)
    monkeypatch.setattr(health, '_probe_cache', None)
    monkeypatch.setattr(health, '_probe_executor', SimpleNamespace(submit=lambda _fn: scheduled.append(1) or SlowProbe()))
    for _ in range(5):
        with pytest.raises(HTTPException) as error:
            health._cached_readiness()
        assert error.value.status_code == 503
    assert scheduled == [1]


def test_failed_readiness_is_cached_without_disclosing_dependency_details(monkeypatch):
    from app.api.routes import health
    from concurrent.futures import Future
    from fastapi import HTTPException
    scheduled = []
    def submit(_fn):
        scheduled.append(1)
        future = Future(); future.set_exception(HTTPException(503, 'private dependency detail'))
        return future
    monkeypatch.setattr(health, 'get_settings', lambda: SimpleNamespace(app_env='production'))
    monkeypatch.setattr(health, '_probe_future', None)
    monkeypatch.setattr(health, '_probe_cache', None)
    monkeypatch.setattr(health, '_probe_executor', SimpleNamespace(submit=submit))
    for _ in range(5):
        with pytest.raises(HTTPException) as error:
            health.readiness_check()
        assert error.value.status_code == 503 and error.value.detail == 'Service is not ready'
    assert scheduled == [1]
