"""Same-start warnings are optional confirmations, scoped like calendar capacity."""
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import UserRole
from tests.test_calendar_capacity import payload, post, setup
from tests.test_security_and_tenancy import login, make_user, make_course


def draft(index=0, **changes):
    body = payload(index)
    body.update(starts_at='2035-05-12T22:30:00Z', check_time_conflict=True)
    body.update(changes)
    return body


def test_warning_writes_nothing_then_confirmation_and_retry_keep_two_events(db):
    institution, teacher = setup(db)
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        first = post(client, draft()).json()
        body = draft(1, idempotency_key='conflict-confirm-0001')
        warning = post(client, body)
        assert warning.status_code == 409, warning.text
        assert warning.json()['error']['code'] == 'CALENDAR_TIME_CONFLICT'
        assert [e['id'] for e in client.get('/api/v1/calendar').json()] == [first['id']]
        saved = post(client, {**body, 'confirm_time_conflict': True})
        assert saved.status_code == 201, saved.text
        # A retry after network loss can reuse the pre-confirmation request key.
        assert post(client, body).json()['id'] == saved.json()['id']
        assert len(client.get('/api/v1/calendar').json()) == 2


def test_edit_excludes_itself_and_refused_move_keeps_original(db):
    institution, teacher = setup(db)
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        body = draft()
        first = post(client, body).json()
        headers = {'X-CSRF-Token': client.cookies.get('matgar_csrf')}
        assert client.put(f"/api/v1/calendar/{first['id']}", json=body, headers=headers).status_code == 200
        second = post(client, draft(1, starts_at='2035-05-12T23:30:00Z')).json()
        move = client.put(f"/api/v1/calendar/{second['id']}", json=draft(1), headers=headers)
        assert move.status_code == 409, move.text
        original = next(e for e in client.get('/api/v1/calendar').json() if e['id'] == second['id'])
        assert original['starts_at'] == second['starts_at']
        assert client.put(f"/api/v1/calendar/{second['id']}", json=draft(1, confirm_time_conflict=True), headers=headers).status_code == 200


def test_warning_scope_includes_courses_and_global_events_but_not_other_teachers_grades_or_minutes(db):
    institution, teacher = setup(db)
    other = make_user(db, institution.id, UserRole.TEACHER, 'conflict-other')
    course = make_course(db, institution, teacher)
    course.grade_level = 'SECONDARY_1'; db.commit()
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        assert post(client, draft()).status_code == 201
        assert post(client, draft(1, course_id=str(course.id))).status_code == 409
        assert post(client, draft(1, description='{"academicYear":"all"}')).status_code == 409
        assert post(client, draft(1, description='{"academicYear":"2nd_secondary"}')).status_code == 201
        assert post(client, draft(2, starts_at='2035-05-12T22:31:00Z')).status_code == 201
        assert post(client, draft(3, starts_at='2035-05-13T22:30:00Z')).status_code == 201
    with TestClient(app) as client:
        login(client, other, institution.slug)
        assert post(client, draft()).status_code == 201


def test_cancelled_event_is_not_a_conflict_and_confirmation_cannot_bypass_four_limit(db):
    institution, teacher = setup(db)
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        first = post(client, draft()).json()
        assert client.post(f"/api/v1/calendar/{first['id']}/cancel", headers={
            'X-CSRF-Token': client.cookies.get('matgar_csrf')}).status_code == 200
        assert post(client, draft(1)).status_code == 201
        for index in range(2, 5):
            assert post(client, draft(index, confirm_time_conflict=True)).status_code == 201
        rejected = post(client, draft(5, confirm_time_conflict=True))
        assert rejected.status_code == 409 and 'خامس' in rejected.text
        assert len([e for e in client.get('/api/v1/calendar').json() if not e['cancelled_at']]) == 4
