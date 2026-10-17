"""Registrar capability never grants enrollment, paid content or cross-tenant access."""
import pytest

from app.core.config import get_settings
from app.models import Course, Enrollment
from app.models.user import UserRole
from app.services.student_management import manages_registered_students
from tests.test_teacher_tracking import seed as tracking_seed, client, column


def seed(db):
    users = tracking_seed(db)
    # Public user responses validate email addresses; .test is a reserved suffix.
    for user in users:
        user.email = user.email.replace('@example.test', '@example.com')
    db.commit()
    return users


def enable(monkeypatch, teacher):
    monkeypatch.setattr(get_settings(), 'registered_student_manager_ids', [teacher.id])


def test_explicit_registrar_lists_registered_students_but_not_other_institutions(db, monkeypatch):
    teacher, other, enrolled, unregistered, _, foreign = seed(db)
    api = client(teacher)
    assert {row['id'] for row in api.get('/api/v1/users?role=student').json()} == {str(enrolled.id)}
    enable(monkeypatch, teacher)
    rows = api.get('/api/v1/users?role=student').json()
    assert {row['id'] for row in rows} == {str(enrolled.id), str(unregistered.id)}
    assert str(foreign.id) not in {row['id'] for row in rows}
    assert {row['id'] for row in client(other).get('/api/v1/users?role=student').json()} == {str(enrolled.id)}
    assert client(unregistered).get('/api/v1/users?role=student').status_code == 403
    assert str(other.id) not in {row['id'] for row in api.get('/api/v1/users').json()}
    assert api.get('/api/v1/auth/profile-summary').json()['registered_students_count'] == 2
    assert client(other).get('/api/v1/auth/profile-summary').json().get('registered_students_count') is None
    # Listing does not enroll students or invent assessment grades.
    assert db.query(Enrollment).filter_by(student_id=unregistered.id).count() == 0
    unregistered_row = next(row for row in rows if row['id'] == str(unregistered.id))
    assert unregistered_row['total_overall_grade'] is None
    course = db.query(Course).filter_by(teacher_id=teacher.id).one()
    course.status = 'published'
    db.commit()
    student_api = client(unregistered)
    assert student_api.get(f'/api/v1/courses/{course.id}').status_code == 403
    assert student_api.get(f'/api/v1/courses/{course.id}/assessments').status_code == 403


def test_registrar_tracking_accepts_unenrolled_account_but_keeps_column_and_tenant_isolation(db, monkeypatch):
    teacher, other, _, unregistered, _, foreign = seed(db)
    enable(monkeypatch, teacher)
    api = client(teacher)
    definition = column(api)
    path = f"/api/v1/teacher-tracking/columns/{definition['id']}/students/"
    assert api.put(path + str(unregistered.id), json={'value': 'Registered, not subscribed'}).status_code == 200
    assert api.get('/api/v1/teacher-tracking').json()['values'][str(unregistered.id)][definition['id']] == 'Registered, not subscribed'
    assert api.put(path + str(foreign.id), json={'value': 'foreign'}).status_code == 404
    assert client(other).put(path + str(unregistered.id), json={'value': 'other teacher'}).status_code == 404
    assert client(other).get('/api/v1/teacher-tracking').json()['values'] == {}


@pytest.mark.parametrize('action', ['block', 'delete'])
def test_registrar_can_manage_unenrolled_account_only_within_own_institution(db, monkeypatch, action):
    teacher, other, _, unregistered, _, foreign = seed(db)
    enable(monkeypatch, teacher)
    def mutate(api, student):
        path = f'/api/v1/users/{student.id}'
        return api.post(path + '/block') if action == 'block' else api.delete(path)
    assert mutate(client(other), unregistered).status_code == 403
    assert mutate(client(teacher), foreign).status_code == 404
    assert mutate(client(teacher), unregistered).status_code == (200 if action == 'block' else 204)
    db.refresh(unregistered)
    assert not unregistered.is_active
    if action == 'delete':
        assert unregistered.deleted_at is not None
        assert str(unregistered.id) not in {row['id'] for row in client(teacher).get('/api/v1/users?role=student').json()}


def test_allowlisting_a_student_never_grants_manager_permissions(db, monkeypatch):
    _, _, student, *_ = seed(db)
    enable(monkeypatch, student)
    assert student.role == UserRole.STUDENT
    assert not manages_registered_students(student)
    assert client(student).get('/api/v1/users?role=student').status_code == 403
