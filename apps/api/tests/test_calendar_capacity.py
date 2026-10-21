import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.course import Enrollment, EnrollmentStatus
from app.models.platform import CalendarEvent
from app.models.user import UserRole
from tests.test_security_and_tenancy import make_institution, make_user, make_course, login


def payload(index=0, grade='1st_secondary', **changes):
    return dict(title=f'Independent event {index}', event_type=['lesson', 'quiz', 'assignment', 'review'][index % 4],
        description=json.dumps({'academicYear': grade}), starts_at=f'2035-05-13T{index + 7:02}:30:00Z', **changes)


def post(client, body):
    return client.post('/api/v1/calendar', json=body, headers={'X-CSRF-Token': client.cookies.get('matgar_csrf')})


def setup(db):
    institution = make_institution(db, 'calendar-capacity')
    teacher = make_user(db, institution.id, UserRole.TEACHER, 'capacity-teacher')
    return institution, teacher


def test_four_independent_events_persist_and_fifth_preserves_all_after_reload(db):
    institution, teacher = setup(db)
    learner = make_user(db, institution.id, UserRole.STUDENT, 'capacity-student')
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        ids = []
        for i in [3, 1, 0, 2]:
            r = post(client, payload(i))
            assert r.status_code == 201, r.text
            ids.append(r.json()['id'])
        refused = post(client, payload(4))
        assert refused.status_code == 409 and 'خامس' in refused.text
        events = client.get('/api/v1/calendar').json()
        assert len(events) == 4 and {e['id'] for e in events} == set(ids)
        assert [e['title'] for e in events] == [f'Independent event {i}' for i in range(4)]
        assert all(e['creator_id'] == str(teacher.id) and e['academic_year'] == '1st_secondary' for e in events)
    with TestClient(app) as client:
        login(client, learner, institution.slug)
        assert len(client.get('/api/v1/calendar').json()) == 4
        assert post(client, payload(5)).status_code == 403


def test_cairo_day_spans_utc_midnight_and_edit_does_not_count_itself(db):
    institution, teacher = setup(db)
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        ids = []
        for i, instant in enumerate(['2035-05-12T21:30:00Z', '2035-05-12T23:00:00Z',
                                     '2035-05-13T01:00:00Z', '2035-05-13T15:00:00Z']):
            body = payload(i); body['starts_at'] = instant
            r = post(client, body); assert r.status_code == 201, r.text
            ids.append(r.json()['id'])
        assert post(client, payload(4)).status_code == 409
        body = payload(0); body['title'] = 'Edited independently'
        edited = client.put(f'/api/v1/calendar/{ids[0]}', json=body,
            headers={'X-CSRF-Token': client.cookies.get('matgar_csrf')})
        assert edited.status_code == 200, edited.text
        assert len(client.get('/api/v1/calendar').json()) == 4
        # Next Cairo day starts at21UTC in summer and has its own allowance.
        body['starts_at'] = '2035-05-13T21:00:00Z'
        assert post(client, body).status_code == 201


def test_limits_are_per_teacher_and_grade_even_across_courses(db):
    institution, teacher = setup(db)
    other = make_user(db, institution.id, UserRole.TEACHER, 'capacity-other')
    first = make_course(db, institution, teacher)
    first.grade_level = 'SECONDARY_1'; db.commit()
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        for i in range(4):
            assert post(client, payload(i)).status_code == 201
        # A different course does not create another allowance in this teacher/grade table.
        assert post(client, payload(4, course_id=str(first.id))).status_code == 409
        assert post(client, payload(4, grade='2nd_secondary')).status_code == 201
        # A global entry would overfill the first-year table and must be refused.
        assert post(client, payload(5, grade='all')).status_code == 409
    with TestClient(app) as client:
        login(client, other, institution.slug)
        assert post(client, payload(0)).status_code == 201


def test_cancelling_one_event_frees_one_slot_and_retry_is_idempotent(db):
    institution, teacher = setup(db)
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        body = payload(0, idempotency_key='calendar-unique-0001')
        first = post(client, body).json()
        for i in range(1, 4):
            assert post(client, payload(i)).status_code == 201
        assert post(client, body).json()['id'] == first['id']
        assert len(client.get('/api/v1/calendar').json()) == 4
        r = client.post(f"/api/v1/calendar/{first['id']}/cancel",
            headers={'X-CSRF-Token': client.cookies.get('matgar_csrf')})
        assert r.status_code == 200
        assert post(client, payload(4)).status_code == 201
        events = client.get('/api/v1/calendar').json()
        assert len([e for e in events if not e['cancelled_at']]) == 4
        assert len([e for e in events if e['cancelled_at']]) == 1


def test_hidden_course_events_remain_hidden_without_enrollment(db):
    institution, teacher = setup(db)
    student = make_user(db, institution.id, UserRole.STUDENT, 'hidden-capacity-student')
    course = make_course(db, institution, teacher)
    course.grade_level = 'SECONDARY_2'; db.commit()
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        assert post(client, payload(0, course_id=str(course.id))).status_code == 201
        assert post(client, payload(1, is_published=False)).status_code == 201
    with TestClient(app) as client:
        login(client, student, institution.slug)
        assert client.get('/api/v1/calendar').json() == []
    db.add(Enrollment(course_id=course.id, student_id=student.id, status=EnrollmentStatus.ACTIVE)); db.commit()
    with TestClient(app) as client:
        login(client, student, institution.slug)
        events = client.get('/api/v1/calendar').json()
        assert len(events) == 1 and events[0]['academic_year'] == '2nd_secondary'


def test_automatic_lesson_calendar_cannot_bypass_four_slot_limit(db):
    from app.models.course import Lesson, LessonKind
    from app.services.lesson_announcements import sync_lesson_calendar
    from fastapi import HTTPException
    institution, teacher = setup(db)
    course = make_course(db, institution, teacher)
    course.grade_level = 'SECONDARY_1'; db.commit()
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        for i in range(4):
            assert post(client, payload(i)).status_code == 201
    lesson = Lesson(course_id=course.id, title='Scheduled lesson', kind=LessonKind.ARTICLE,
        position=1, publication_status='published', publish_at=datetime(2035, 5, 13, 13, tzinfo=timezone.utc))
    db.add(lesson); db.flush()
    with pytest.raises(HTTPException) as error:
        sync_lesson_calendar(db, lesson, course)
    assert error.value.status_code == 409
    assert len(db.query(CalendarEvent).all()) == 4


def test_move_into_a_full_day_keeps_the_original_event_unchanged(db):
    institution, teacher = setup(db)
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        for i in range(4):
            assert post(client, payload(i)).status_code == 201
        body = payload(0); body['starts_at'] = '2035-05-14T10:00:00Z'
        original = post(client, body).json()
        body['starts_at'] = '2035-05-13T10:00:00Z'
        rejected = client.put(f"/api/v1/calendar/{original['id']}", json=body,
            headers={'X-CSRF-Token': client.cookies.get('matgar_csrf')})
        assert rejected.status_code == 409
        saved = next(e for e in client.get('/api/v1/calendar').json() if e['id'] == original['id'])
        assert saved['starts_at'] == original['starts_at']


def test_cairo_fall_back_day_includes_both_occurrences_of_the_repeated_hour(db):
    institution, teacher = setup(db)
    zone = ZoneInfo('Africa/Cairo')
    day = date(2035, 10, 31)
    while day.weekday() != 3:
        day -= timedelta(days=1)
    def instant(hour, fold=0):
        return datetime(day.year, day.month, day.day, hour, 30, tzinfo=zone, fold=fold).astimezone(timezone.utc).isoformat()
    assert instant(23, 0) != instant(23, 1)
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        for i, start in enumerate([instant(1), instant(12), instant(23, 0), instant(23, 1)]):
            body = payload(i); body['starts_at'] = start
            assert post(client, body).status_code == 201
        body['starts_at'] = instant(22)
        assert post(client, body).status_code == 409
        next_day = day + timedelta(days=1)
        body['starts_at'] = datetime(next_day.year, next_day.month, next_day.day, 0, 15, tzinfo=zone).astimezone(timezone.utc).isoformat()
        assert post(client, body).status_code == 201
