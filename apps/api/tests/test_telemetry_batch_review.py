"""Regressions for the multi-event browser batch found by reading QA."""
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models.course import CourseModule, Enrollment, Lesson, LessonKind
from app.models.progress import LessonProgress, VideoEvent
from app.models.user import UserRole
from tests.test_security_and_tenancy import (
    csrf_headers, login, make_course, make_institution, make_user,
)


def setup(db):
    institution = make_institution(db, 'telemetry-batch-review')
    teacher = make_user(db, institution.id, UserRole.TEACHER, 'teacher')
    student = make_user(db, institution.id, UserRole.STUDENT, 'student')
    course = make_course(db, institution, teacher)
    module = CourseModule(course_id=course.id, title='Batch module', position=1)
    db.add(module)
    db.flush()
    lessons = [Lesson(module_id=module.id, title=f'Batch lesson {n}', kind=LessonKind.VIDEO, position=n) for n in (1, 2)]
    db.add_all(lessons)
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()
    client = TestClient(app)
    login(client, student, institution.slug)
    return client, lessons


def event(lesson, key, delta=2):
    return {'lesson_id': str(lesson.id), 'client_event_id': 'review-' + key, 'event_type': 'play',
            'position_seconds': 10, 'watched_delta_seconds': delta, 'duration_seconds': 100}


def send(client, events):
    return client.post('/api/v1/telemetry/video-events', headers=csrf_headers(client), json={'events': events})


def test_three_events_same_lesson_create_one_progress_and_sum_once(db):
    client, lessons = setup(db)
    events = [event(lessons[0], f'batch-{n}', n) for n in (2, 3, 4)]
    response = send(client, events + [events[0]])
    assert response.status_code == 202
    assert response.json() == {'accepted': 3, 'duplicates': 1}
    assert db.scalar(select(func.count()).select_from(VideoEvent)) == 3
    progress = db.scalars(select(LessonProgress)).one()
    assert progress.watched_duration_seconds == 9
    assert progress.completion_percent == 10


def test_replayed_batch_does_not_double_count_and_new_event_is_retained(db):
    client, lessons = setup(db)
    first = [event(lessons[0], 'batch-a'), event(lessons[0], 'batch-b')]
    assert send(client, first).json() == {'accepted': 2, 'duplicates': 0}
    replay = send(client, first + [event(lessons[0], 'batch-c')])
    assert replay.status_code == 202
    assert replay.json() == {'accepted': 1, 'duplicates': 2}
    assert db.scalars(select(LessonProgress)).one().watched_duration_seconds == 6
    assert db.scalar(select(func.count()).select_from(VideoEvent)) == 3


def test_batch_keeps_distinct_lesson_progress_separate(db):
    client, lessons = setup(db)
    response = send(client, [event(lessons[0], 'first-a'), event(lessons[1], 'second-a'), event(lessons[0], 'first-b')])
    assert response.status_code == 202
    progress = {row.lesson_id: row.watched_duration_seconds for row in db.scalars(select(LessonProgress))}
    assert progress == {lessons[0].id: 4, lessons[1].id: 2}


def test_unauthorized_event_rolls_back_whole_batch(db):
    client, lessons = setup(db)
    import uuid
    invalid = event(lessons[0], 'forbidden')
    invalid['lesson_id'] = str(uuid.uuid4())
    assert send(client, [event(lessons[0], 'allowed'), invalid]).status_code == 404
    assert db.scalar(select(func.count()).select_from(VideoEvent)) == 0
    assert db.scalar(select(func.count()).select_from(LessonProgress)) == 0


def test_first_browser_event_before_metadata_has_zero_completion(db):
    client, lessons = setup(db)
    first = event(lessons[0], 'before-metadata', 0)
    first['position_seconds'] = 0
    first['duration_seconds'] = None
    response = send(client, [first])
    assert response.status_code == 202
    progress = db.scalars(select(LessonProgress)).one()
    assert progress.completion_percent == 0
    assert progress.completed_at is None
    later = event(lessons[0], 'after-metadata', 2)
    assert send(client, [later]).status_code == 202
    db.expire_all()
    assert db.scalars(select(LessonProgress)).one().completion_percent == 10
