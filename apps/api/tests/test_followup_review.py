"""Six-point follow-up: real HTTP permissions, publication and query budgets."""
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event
from app.main import app
from app.models.course import CourseModule, Enrollment, Lesson, LessonKind
from app.models.extended import Grade, LearningObjective
from app.models.platform import Question, Quiz, QuizQuestion, QuizStatus, QuizAttempt, QuizAttemptAnswer, AttemptStatus
from app.models.user import UserRole
from test_security_and_tenancy import make_institution, make_user, make_course, login, csrf_headers


def domain(db):
    inst = make_institution(db, 'followup')
    owner = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    colleague = make_user(db, inst.id, UserRole.TEACHER, 'colleague')
    student = make_user(db, inst.id, UserRole.STUDENT, 'student')
    course = make_course(db, inst, owner)
    db.add(Enrollment(course_id=course.id, student_id=student.id)); db.commit()
    return inst, owner, colleague, student, course


def test_auth_never_serializes_session_credentials(db):
    inst, owner, _, _, _ = domain(db)
    c = TestClient(app, base_url='https://testserver')
    response = c.post('/api/v1/auth/login', json=dict(email=owner.email,
        password='password-123456', institution_slug=inst.slug))
    assert response.status_code == 200
    assert not {'token', 'access_token', 'refresh_token'} & response.json().keys()
    for name in ('matgar_session', 'matgar_refresh'):
        cookie = next(v for v in response.headers.get_list('set-cookie') if v.startswith(name+'='))
        assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie
    assert c.get('/api/v1/auth/me').status_code == 200
    refresh = c.post('/api/v1/auth/refresh', headers=csrf_headers(c))
    assert refresh.status_code == 200
    assert not {'token', 'access_token', 'refresh_token'} & refresh.json().keys()


@pytest.mark.parametrize('resource', ['grades/students/{id}', 'analytics/students/{id}/mastery'])
def test_teacher_cannot_read_unrelated_student(db, resource):
    inst, _, colleague, student, _ = domain(db)
    c = login(TestClient(app), colleague, inst.slug)
    assert c.get('/api/v1/' + resource.format(id=student.id)).status_code == 404


@pytest.mark.parametrize('access_state', ['invalid', 'absent'])
def test_bootstrap_requests_cookie_renewal_instead_of_racing_to_guest(db, access_state):
    inst, owner, _, _, _ = domain(db)
    c = login(TestClient(app, base_url='https://testserver'), owner, inst.slug)
    if access_state == 'invalid':
        c.cookies.set('matgar_session', 'expired-qa-cookie', domain='testserver.local', path='/')
    else:
        c.cookies.delete('matgar_session')
    assert c.get('/api/v1/bootstrap').status_code == 401
    assert c.post('/api/v1/auth/refresh', headers=csrf_headers(c)).status_code == 200
    bootstrap = c.get('/api/v1/bootstrap')
    assert bootstrap.status_code == 200 and bootstrap.json()['authenticated'] is True
    assert c.post('/api/v1/auth/logout', headers=csrf_headers(c)).status_code == 204
    guest = c.get('/api/v1/bootstrap')
    assert guest.status_code == 200 and guest.json()['authenticated'] is False


def test_cookie_bootstrap_db_outage_is_not_invalid_authentication(db, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session
    inst, owner, _, _, _ = domain(db)
    c = login(TestClient(app, base_url='https://testserver', raise_server_exceptions=False), owner, inst.slug)
    def unavailable(*args, **kwargs):
        raise OperationalError('QA database unavailable', {}, RuntimeError('synthetic outage'))
    # HTTP dependencies create their own Session; patch the class, not the
    # seed session, so the fault really reaches authentication SQL.
    monkeypatch.setattr(Session, 'scalar', unavailable)
    response = c.get('/api/v1/bootstrap')
    assert response.status_code == 503
    assert not response.headers.get('set-cookie')
    assert c.cookies.get('matgar_session')


def test_shared_student_grades_and_mastery_are_course_scoped(db):
    inst, owner, colleague, student, course = domain(db)
    other = make_course(db, inst, colleague)
    db.add(Enrollment(course_id=other.id, student_id=student.id))
    now = datetime.now(timezone.utc)
    for c, teacher, score in [(course, owner, 1), (other, colleague, 0)]:
        db.add(Grade(institution_id=inst.id, student_id=student.id, course_id=c.id,
            item_type='course', score=score, max_score=1, graded_by=teacher.id))
        objective = LearningObjective(institution_id=inst.id, course_id=c.id, code='shared-code', title=c.code)
        quiz = Quiz(institution_id=inst.id, creator_id=teacher.id, course_id=c.id, title='QA', status=QuizStatus.PUBLISHED)
        question = Question(institution_id=inst.id, author_id=teacher.id, course_id=c.id,
            question_type='essay', prompt='Explain chemistry', points=1, learning_objective='shared-code')
        db.add_all([objective, quiz, question]); db.flush()
        from app.services.quiz_snapshot import capture_questions
        link = QuizQuestion(quiz_id=quiz.id, question_id=question.id, points=1, position=1)
        db.add(link); db.flush()
        snapshot = capture_questions(db, quiz, [(link, question)])[0]
        attempt = QuizAttempt(institution_id=inst.id, quiz_id=quiz.id, student_id=student.id, status=AttemptStatus.SUBMITTED,
            attempt_number=1, started_at=now, submitted_at=now, total_points=1, question_snapshot=[snapshot])
        db.add(attempt); db.flush()
        db.add(QuizAttemptAnswer(attempt_id=attempt.id, question_id=question.id,
            answer='Synthetic', awarded_points=score, graded_at=now, question_snapshot=snapshot))
    db.commit()
    c = login(TestClient(app), owner, inst.slug)
    grades = c.get(f'/api/v1/grades/students/{student.id}')
    assert grades.status_code == 200
    assert [g['course_id'] for g in grades.json()] == [str(course.id)]
    mastery = c.get(f'/api/v1/analytics/students/{student.id}/mastery')
    assert mastery.status_code == 200
    assert [(m['title'], m['mastery'], m['evidence_count']) for m in mastery.json()['items']] == [(course.code, 1, 1)]
    own = login(TestClient(app), student, inst.slug)
    assert len(own.get(f'/api/v1/grades/students/{student.id}').json()) == 2


@pytest.mark.parametrize('invalid', ['empty', 'prompt', 'inactive', 'type', 'options', 'answer', 'points'])
def test_legacy_quiz_rejects_invalid_publication_without_mutation(db, invalid):
    inst, owner, _, _, course = domain(db)
    quiz = Quiz(institution_id=inst.id, creator_id=owner.id, course_id=course.id, title='QA draft')
    db.add(quiz); db.flush()
    if invalid != 'empty':
        q = Question(institution_id=inst.id, author_id=owner.id, course_id=course.id,
            question_type='mcq', prompt='Valid question', options=['A','B'], correct_answer='A', points=1)
        if invalid == 'prompt': q.prompt = ' '
        if invalid == 'inactive': q.is_active = False
        if invalid == 'type': q.question_type = 'unknown'
        if invalid == 'options': q.options = ['A']
        if invalid == 'answer': q.correct_answer = 'not-an-option'
        if invalid == 'points': q.points = 0
        db.add(q); db.flush()
        db.add(QuizQuestion(quiz_id=quiz.id, question_id=q.id, points=q.points, position=1))
    db.commit()
    c = login(TestClient(app), owner, inst.slug)
    response = c.post(f'/api/v1/quizzes/{quiz.id}/publish', headers=csrf_headers(c))
    assert response.status_code == 400, response.text
    db.refresh(quiz)
    assert quiz.status == QuizStatus.DRAFT and quiz.published_at is None


@pytest.mark.parametrize('answer', ['A', 'kg'])
def test_legacy_quiz_accepts_a_real_dict_option_key_or_text(db, answer):
    inst, owner, _, student, course = domain(db)
    q = Question(institution_id=inst.id, author_id=owner.id, course_id=course.id,
        question_type='mcq', prompt='Choose the mass unit',
        options=[{'key':'A', 'text':'kg'}, {'key':'B', 'text':'s'}], correct_answer=answer, points=2)
    quiz = Quiz(institution_id=inst.id, creator_id=owner.id, course_id=course.id, title='Valid options')
    db.add_all([q, quiz]); db.flush()
    db.add(QuizQuestion(quiz_id=quiz.id, question_id=q.id, points=2, position=1)); db.commit()
    c = login(TestClient(app), owner, inst.slug)
    assert c.post(f'/api/v1/quizzes/{quiz.id}/publish', headers=csrf_headers(c)).status_code == 200
    learner = login(TestClient(app), student, inst.slug)
    attempt = learner.post(f'/api/v1/quizzes/{quiz.id}/attempts', headers=csrf_headers(learner)).json()
    result = learner.post(f"/api/v1/quiz-attempts/{attempt['id']}/submit", headers=csrf_headers(learner),
        json={'submission_key':'valid-dict-option', 'answers':[{'question_id':str(q.id), 'answer':answer}]})
    assert result.status_code == 200 and result.json()['score'] is None
    assert db.query(QuizAttempt).filter_by(quiz_id=quiz.id).one().score == 2


def test_assessment_query_count_does_not_grow_with_content(db):
    inst, owner, _, student, course = domain(db)
    c = login(TestClient(app), student, inst.slug)
    statements = []
    def observe(*args):
        if args[2].lstrip().upper().startswith('SELECT'): statements.append(args[2])
    def read():
        db.expire_all(); statements.clear()
        event.listen(db.bind, 'before_cursor_execute', observe)
        try:
            response = c.get(f'/api/v1/courses/{course.id}/assessments')
            assert response.status_code == 200
            return len(statements), response.json()
        finally: event.remove(db.bind, 'before_cursor_execute', observe)
    small, _ = read()
    for i in range(12):
        module = CourseModule(course_id=course.id, title=f'M{i}', position=i)
        db.add(module); db.flush()
        for j in range(3):
            lesson = Lesson(module_id=module.id, title=f'L{i}-{j}', kind=LessonKind.VIDEO, position=j,
                price_egp=0 if j < 2 else 10)
            db.add(lesson); db.flush()
            db.add(Quiz(institution_id=inst.id, creator_id=owner.id, course_id=course.id,
                title=f'Q{i}-{j}', lesson_id=lesson.id, module_id=module.id, status=QuizStatus.PUBLISHED))
    db.commit()
    large, payload = read()
    print(f'assessment SELECT count: empty={small}, 12 modules/36 lessons/36 quizzes={large}')
    assert large <= small + 2, f'SELECT budget grew from {small} to {large}'
    assert len(payload['lessons']) == 36 and len(payload['quizzes']) == 36
    assert sum(l['accessible'] for l in payload['lessons']) == 24
