from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.course import Enrollment, EnrollmentStatus
from app.models.platform import CalendarEvent, Notification
from app.models.user import UserRole
from app.schemas import LessonCreateRequest
from app.services import lesson_announcements as notices, lesson_release, platform_service
from app.services.content_access import as_utc
from tests.test_security_and_tenancy import make_course, make_institution, make_user


@pytest.fixture
def world(db, monkeypatch):
    inst = make_institution(db, 'notice-timing')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'teacher')
    student = make_user(db, inst.id, UserRole.STUDENT, 'student')
    course = make_course(db, inst, teacher)
    enrollment = Enrollment(course_id=course.id, student_id=student.id, status=EnrollmentStatus.ACTIVE)
    db.add(enrollment); db.commit()
    hints = []
    monkeypatch.setattr(notices.event_broker, 'publish_event', lambda *args, **kwargs: hints.append((args, kwargs)))
    return teacher, student, course, enrollment, hints


def create_lesson(db, world, *, immediate, start=None):
    teacher, _, course, _, _ = world
    return platform_service.add_lesson(db, teacher, None, LessonCreateRequest(
        title='Scheduled video', kind='video', position=1, publication_status='published',
        announce_to_students=immediate, publish_at=start), course_id=course.id)


def rows(db):
    db.expire_all()
    return list(db.scalars(select(Notification)))


def test_checked_sends_now_before_upload_and_release_without_unlocking_content(db, world):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    lesson = create_lesson(db, world, immediate=True, start=start)
    _, student, course, _, hints = world
    notification, = rows(db)
    assert notification.recipient_id == student.id
    assert notification.delivery_status == 'delivered'
    assert 'announcement=' in notification.action_url
    assert 'lesson=' not in notification.action_url
    assert notices.visible_lesson_notifications(db, student, [notification]) == [notification]
    assert lesson_release.available_lesson_ids(db, [lesson], {course.id: course}) == set()
    assert hints[0][0][1] == 'notification_created'
    assert db.scalar(select(CalendarEvent)).is_published
    assert lesson.release_announced_at is None  # Readiness SSE must still happen later.


def test_unchecked_waits_for_due_time_and_ready_media_then_sends_once(db, world, monkeypatch):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    lesson = create_lesson(db, world, immediate=False, start=start)
    assert rows(db) == []
    notices.announce_available_lessons()
    assert rows(db) == []

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return start.astimezone(tz) if tz else start.replace(tzinfo=None)

    monkeypatch.setattr(notices, 'datetime', Clock)
    monkeypatch.setattr(lesson_release, 'datetime', Clock)
    notices.announce_available_lessons()  # Due, but upload has not finished.
    assert rows(db) == []
    lesson.video_asset_key = 'private/video.mp4'
    db.commit()
    notices.announce_available_lessons()  # Inclusive start boundary, no extra minute.
    notification, = rows(db)
    assert notification.title == 'درس جديد متاح'
    assert notification.recipient_id == world[1].id
    notices.announce_available_lessons()
    assert len(rows(db)) == 1
    assert db.scalar(select(CalendarEvent)).is_published


def test_immediate_notice_is_not_duplicated_on_edit_or_when_video_becomes_ready(db, world):
    lesson = create_lesson(db, world, immediate=True)
    assert notices.announce_lesson_immediately(db, lesson, world[2]) == set()
    lesson.video_asset_key = 'private/video.mp4'
    db.commit()
    notices.announce_available_lessons()
    assert len(rows(db)) == 1
    assert lesson.release_announced_at is not None
    assert any(args[1] == 'lesson_published' for args, _ in world[4])


@pytest.mark.parametrize('restriction', ['withdrawn', 'payment', 'inactive', 'course_draft'])
def test_ineligible_students_receive_no_immediate_notice(db, world, restriction):
    _, student, course, enrollment, _ = world
    if restriction == 'withdrawn':
        enrollment.status = EnrollmentStatus.WITHDRAWN
    elif restriction == 'payment':
        course.price_egp = 100
    elif restriction == 'inactive':
        student.is_active = False
    else:
        course.status = 'draft'
    db.commit()
    create_lesson(db, world, immediate=True)
    assert rows(db) == []


@pytest.mark.parametrize('restriction', ['withdrawn', 'draft', 'expired', 'payment', 'course_draft', 'deleted'])
def test_immediate_notices_are_withdrawn_when_access_changes(db, world, restriction):
    lesson = create_lesson(db, world, immediate=True)
    notification, = rows(db)
    _, student, course, enrollment, _ = world
    if restriction == 'withdrawn':
        enrollment.status = EnrollmentStatus.WITHDRAWN
    elif restriction == 'draft':
        lesson.publication_status = 'draft'
    elif restriction == 'expired':
        lesson.available_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif restriction == 'payment':
        lesson.price_egp = 100
    elif restriction == 'course_draft':
        course.status = 'draft'
    else:
        db.delete(lesson)
    db.commit()
    assert notices.visible_lesson_notifications(db, student, [notification]) == []


def test_enabling_immediate_notification_on_publication_edit_sends_only_once(db, world):
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.test_security_and_tenancy import login, csrf_headers

    lesson = create_lesson(db, world, immediate=False,
                           start=datetime.now(timezone.utc) + timedelta(days=1))
    client = login(TestClient(app), world[0], 'notice-timing')
    payload = {'publication_status': 'published', 'publish_at': as_utc(lesson.publish_at).isoformat(),
               'announce_to_students': True}
    for _ in range(2):
        response = client.patch(f'/api/v1/lessons/{lesson.id}/publication', json=payload, headers=csrf_headers(client))
        assert response.status_code == 200, response.text
    assert len(rows(db)) == 1
