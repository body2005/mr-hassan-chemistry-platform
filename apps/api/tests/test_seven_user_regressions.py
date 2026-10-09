"""The seven reported defects: isolated new route/ASGI regressions only."""
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.course import CourseModule, Enrollment, Lesson, LessonKind
from app.models.platform import (AttemptStatus, Question, Quiz, QuizAttempt,
                                QuizAttemptAnswer, QuizQuestion, QuizStatus)
from app.models.progress import LessonProgress, VideoEvent
from app.models.user import UserRole
from tests.test_security_and_tenancy import (make_institution, make_user,
                                           make_course, login, csrf_headers)


def domain(db):
    inst = make_institution(db, 'seven-reported')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'teacher')
    student = make_user(db, inst.id, UserRole.STUDENT, 'student')
    course = make_course(db, inst, teacher)
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()
    return inst, teacher, student, course


def exam(db, inst, teacher, student, course, *, correct='أ', kind='mcq', options=None):
    options = options or ['الهيدروجين', 'الأكسجين']
    question = Question(institution_id=inst.id, author_id=teacher.id,
        course_id=course.id, prompt='اختر الغاز الصحيح', question_type=kind,
        correct_answer=correct, options=options, points=10)
    quiz = Quiz(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
                title='Reported regression', status=QuizStatus.PUBLISHED)
    db.add_all([question, quiz]); db.flush()
    # Existing frozen exams can carry Arabic keys. Do not silently rewrite
    # the student's historical evidence or reinterpret the mutable bank.
    snapshot = dict(question_id=str(question.id), question_version=1,
        question_type=kind, prompt=question.prompt, options=options,
        correct_answer=correct, points=10, learning_objective=None,
        course_id=str(course.id), origin='synthetic-existing-publication')
    db.add(QuizQuestion(quiz_id=quiz.id, question_id=question.id, position=1,
                        points=10, question_snapshot=snapshot))
    db.commit()
    return quiz, question, snapshot


@pytest.mark.parametrize('correct,answer,expected', [
    ('أ', 'الهيدروجين', 10), ('A', 'الهيدروجين', 10),
    ('الهيدروجين', 'A', 10), ('ب', 'الأكسجين', 10),
    ('أ', 'ب', 0), ('أ', 'غير موجود', 0),
])
def test_mcq_key_and_option_text_identify_same_frozen_choice(db, correct, answer, expected):
    inst, teacher, student, course = domain(db)
    quiz, question, _ = exam(db, inst, teacher, student, course, correct=correct)
    with login(TestClient(app), student, inst.slug) as client:
        opened = client.get(f'/api/v1/quizzes/{quiz.id}/solve')
        assert opened.status_code == 200, opened.text
        result = client.post(f'/api/v1/quiz-attempts/{opened.json()["attempt"]["id"]}/submit',
            headers=csrf_headers(client), json={'submission_key': uuid.uuid4().hex,
            'answers': [{'question_id': str(question.id), 'answer': answer}]})
        assert result.status_code == 200, result.text
        assert result.json()['score'] == expected


def add_attempt(db, inst, student, quiz, *, score, practice=False, number=1, snapshot=None):
    row = QuizAttempt(institution_id=inst.id, quiz_id=quiz.id, student_id=student.id,
        attempt_number=number, status=AttemptStatus.SUBMITTED, score=score,
        total_points=10, is_practice=practice, started_at=datetime.now(timezone.utc),
        submitted_at=datetime.now(timezone.utc),
        question_snapshot=[snapshot] if snapshot else None)
    db.add(row); db.flush()
    return row


def test_teacher_official_zero_not_averaged_with_perfect_practice(db):
    inst, teacher, student, course = domain(db)
    quiz, _, _ = exam(db, inst, teacher, student, course)
    add_attempt(db, inst, student, quiz, score=0)
    add_attempt(db, inst, student, quiz, score=10, practice=True, number=2)
    db.commit()
    with login(TestClient(app), teacher, inst.slug) as client:
        response = client.get('/api/v1/users')
        assert response.status_code == 200
        row = next(row for row in response.json() if row['id'] == str(student.id))
        assert row['average_quiz_score'] == 0
        assert row['quiz_attempts_count'] == 1


def test_pending_essay_survives_bank_type_change_and_can_be_graded(db):
    inst, teacher, student, course = domain(db)
    quiz, question, snapshot = exam(db, inst, teacher, student, course, kind='essay')
    attempt = add_attempt(db, inst, student, quiz, score=0, snapshot=snapshot)
    db.add(QuizAttemptAnswer(attempt_id=attempt.id, question_id=question.id,
        answer='Student explanation', question_snapshot=snapshot, awarded_points=0, graded_at=None))
    question.question_type = 'mcq'
    db.commit()
    with login(TestClient(app), teacher, inst.slug) as client:
        row = next(row for row in client.get('/api/v1/users').json() if row['id'] == str(student.id))
        assert row['pending_quiz_attempts'] == 1
        assert row['average_quiz_score'] is None
        grade = client.post(f'/api/v1/quiz-attempts/{attempt.id}/answers/{question.id}/grade',
            headers=csrf_headers(client), json={'awarded_points': 7})
        assert grade.status_code == 200, grade.text
        row = next(row for row in client.get('/api/v1/users').json() if row['id'] == str(student.id))
        assert row['pending_quiz_attempts'] == 0
        assert row['average_quiz_score'] == 70


def test_progress_does_not_leak_between_two_enrolled_courses(db):
    inst, teacher, student, course = domain(db)
    other = make_course(db, inst, teacher)
    db.add(Enrollment(course_id=other.id, student_id=student.id))
    modules = [CourseModule(course_id=row.id, title='Unit', position=1) for row in (course, other)]
    db.add_all(modules); db.flush()
    lessons = [Lesson(module_id=row.id, title='Lesson', kind=LessonKind.ARTICLE, position=1) for row in modules]
    db.add_all(lessons); db.flush()
    db.add(LessonProgress(institution_id=inst.id, student_id=student.id,
                           lesson_id=lessons[0].id, completion_percent=100))
    db.commit()
    with login(TestClient(app), teacher, inst.slug) as client:
        first = client.get(f'/api/v1/analytics/courses/{course.id}')
        second = client.get(f'/api/v1/analytics/courses/{other.id}')
        assert first.status_code == second.status_code == 200
        assert first.json()['average_completion_percent'] == 100
        assert second.json()['average_completion_percent'] == 0
        assert second.json()['completed_lessons'] == 0


UPLOAD_PATHS = ['/lessons/{id}/video', '/lessons/{id}/materials',
                '/assignments/{id}/submissions/file', '/payments/orders/{id}/receipt',
                '/quiz/extract-from-file']


def asgi_request_without_body(path, headers=()):
    received, messages = [], []
    async def receive():
        received.append(True)
        if len(received) > 1:
            return {'type': 'http.disconnect'}
        return {'type': 'http.request', 'body': b'not-a-multipart-file', 'more_body': False}
    async def send(message):
        messages.append(message)
    scope = dict(type='http', asgi={'version': '3.0', 'spec_version': '2.4'},
        http_version='1.1', method='POST', scheme='http', path=path, raw_path=path.encode(),
        query_string=b'', root_path='', server=('testserver', 80), client=('127.0.0.1', 1234),
        headers=[(b'content-type', b'multipart/form-data; boundary=qa'),
                 (b'content-length', b'23'), *headers])
    asyncio.run(app(scope, receive, send))
    return received, next(message['status'] for message in messages if message['type'] == 'http.response.start')


@pytest.mark.parametrize('path', UPLOAD_PATHS)
def test_anonymous_upload_rejected_without_receiving_any_body(db, path):
    received, status = asgi_request_without_body('/api/v1' + path.format(id=uuid.uuid4()))
    assert status == 401
    assert received == []


def test_invalid_token_upload_rejected_without_receiving_body(db):
    received, status = asgi_request_without_body('/api/v1/quiz/extract-from-file',
        [(b'authorization', b'Bearer invalid-session')])
    assert status == 401
    assert received == []


@pytest.mark.parametrize('telemetry', [False, True])
def test_unpaid_lesson_cannot_forge_completion_or_video_progress(db, telemetry):
    inst, teacher, student, course = domain(db)
    module = CourseModule(course_id=course.id, title='Paid', position=1)
    db.add(module); db.flush()
    lesson = Lesson(module_id=module.id, title='Paid lesson', kind=LessonKind.VIDEO,
                    position=1, price_egp=50)
    db.add(lesson); db.commit()
    with login(TestClient(app), student, inst.slug) as client:
        if telemetry:
            response = client.post('/api/v1/telemetry/video-events', headers=csrf_headers(client),
                json={'events': [{'lesson_id': str(lesson.id), 'client_event_id': uuid.uuid4().hex,
                    'event_type': 'ended', 'position_seconds': 100, 'duration_seconds': 100}]})
        else:
            response = client.post(f'/api/v1/progress/lessons/{lesson.id}/complete', headers=csrf_headers(client))
        assert response.status_code == 403, response.text
        assert db.scalar(select(LessonProgress.id).where(LessonProgress.student_id == student.id)) is None
        assert db.scalar(select(VideoEvent.id).where(VideoEvent.student_id == student.id)) is None


def test_production_compose_explicitly_enables_configured_recovery_mail():
    root = Path(os.environ.get('QA_REPO_ROOT', '/repo'))
    text = (root / 'infra/docker-compose.yml').read_text(encoding='utf-8')
    assert 'EMAIL_ENABLED: ${EMAIL_ENABLED:-true}' in text
