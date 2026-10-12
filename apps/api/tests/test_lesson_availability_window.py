from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from app.models.course import Lesson, CourseModule
from app.models.platform import CalendarEvent
from app.models.user import UserRole
from app.schemas import LessonPublicationRequest
from app.services.lesson_release import available_lesson_ids
from app.services.lesson_announcements import sync_lesson_calendar
from app.services.content_access import as_utc
from tests.test_security_and_tenancy import make_institution, make_user, make_course


def test_lesson_start_end_and_calendar_update_are_consistent(db):
    inst = make_institution(db, 'lesson-window')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'teacher')
    course = make_course(db, inst, teacher)
    module = CourseModule(course_id=course.id, title='Unit', position=1)
    db.add(module); db.flush()
    now = datetime.now(timezone.utc)
    lesson = Lesson(course_id=course.id, module_id=module.id, title='Video', kind='video', position=1,
        video_asset_key='private/video.mp4', publication_status='published',
        publish_at=now - timedelta(hours=1), available_until=now + timedelta(hours=1),
        announce_to_students=True)
    db.add(lesson); db.flush()
    check = lambda: available_lesson_ids(db, [lesson], {course.id: course})
    assert lesson.id in check()
    lesson.publish_at = now + timedelta(minutes=1)
    assert lesson.id not in check()
    lesson.publish_at = now - timedelta(hours=1)
    lesson.available_until = now - timedelta(seconds=1)
    assert lesson.id not in check()
    lesson.available_until = now + timedelta(hours=2)
    sync_lesson_calendar(db, lesson, course); db.flush()
    event = db.scalar(select(CalendarEvent))
    assert as_utc(event.ends_at) == lesson.available_until
    lesson.announce_to_students = False
    sync_lesson_calendar(db, lesson, course); db.flush()
    assert not event.is_published
    assert len(list(db.scalars(select(CalendarEvent)))) == 1


def test_schedule_rejects_reversed_window_and_timezone_less_dates():
    with pytest.raises(ValidationError):
        LessonPublicationRequest(publication_status='published', publish_at='2026-10-12T12:00:00Z',
                                 available_until='2026-10-12T11:00:00Z')
    with pytest.raises(ValidationError):
        LessonPublicationRequest(publication_status='published', available_until='2026-10-12T12:00:00')


def test_closing_time_blocks_student_playback_but_preserves_teacher_preview(db, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.test_video_protection import _setup_world, _login, _csrf
    inst, teacher, student, _, lesson = _setup_world(db, tmp_path, monkeypatch)
    staff = TestClient(app); _login(staff, teacher, inst.slug)
    learner = TestClient(app); _login(learner, student, inst.slug)
    assert learner.post(f'/api/v1/lessons/{lesson.id}/video-token', headers=_csrf(learner)).status_code == 200
    response = staff.patch(f'/api/v1/lessons/{lesson.id}/publication', headers=_csrf(staff), json={
        'publication_status': 'published', 'publish_at': None,
        'available_until': (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        'announce_to_students': False,
    })
    assert response.status_code == 200, response.text
    assert response.json()['announce_to_students'] is False
    assert learner.post(f'/api/v1/lessons/{lesson.id}/video-token', headers=_csrf(learner)).status_code == 403
    assert staff.post(f'/api/v1/lessons/{lesson.id}/video-token', headers=_csrf(staff)).status_code == 200


def test_migration_preserves_existing_lessons_with_open_ended_availability():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text
    path = Path(__file__).parents[1] / 'alembic/versions/f9e1b3d5a7c9_lesson_availability_window.py'
    spec = importlib.util.spec_from_file_location('lesson_window_migration', path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE lessons (id TEXT PRIMARY KEY, title TEXT NOT NULL)'))
        connection.execute(text("INSERT INTO lessons VALUES ('existing', 'Keep this lesson')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        row = connection.execute(text('SELECT title, available_until, announce_to_students FROM lessons')).one()
        assert row == ('Keep this lesson', None, 1)
