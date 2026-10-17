"""Purchase admission/isolation regression source; not run in this task."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.course import Enrollment
from app.models.payment import EntitlementType, StudentEntitlement
from app.models.platform import Quiz
from tests.test_course_metadata_authorization import domain
from tests.test_security_and_tenancy import login, make_course


def grant(db, inst, student, resource, kind=EntitlementType.LESSON, **changes):
    row = StudentEntitlement(institution_id=inst.id, student_id=student.id,
        entitlement_type=kind, resource_id=resource, starts_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    for key, value in changes.items():
        setattr(row, key, value)
    db.add(row); db.commit()
    return row


@pytest.mark.parametrize('suffix', ['', '/', '/assessments', '/assessments/'])
def test_both_paths_and_slash_variants_require_identity(db, suffix):
    _, _, _, _, course, *_ = domain(db)
    response = TestClient(app).get(f'/api/v1/courses/{course.id}{suffix}', follow_redirects=False)
    assert response.status_code == 401
    assert 'modules' not in response.json() and 'lessons' not in response.json()


@pytest.mark.parametrize('purchase', ['none', 'expired', 'revoked', 'future', 'other_course', 'other_student'])
def test_enrollment_or_an_unrelated_inactive_purchase_does_not_authorize_either_route(db, purchase):
    inst, owner, student, other, course, _, paid, *_ = domain(db)
    db.add(Enrollment(course_id=course.id, student_id=student.id)); db.commit()
    now = datetime.now(timezone.utc)
    if purchase == 'expired':
        grant(db, inst, student, paid.id, expires_at=now - timedelta(seconds=1))
    elif purchase == 'revoked':
        grant(db, inst, student, paid.id, revoked_at=now)
    elif purchase == 'future':
        grant(db, inst, student, paid.id, starts_at=now + timedelta(hours=1))
    elif purchase == 'other_course':
        foreign = make_course(db, inst, owner)
        grant(db, inst, student, foreign.id, EntitlementType.COURSE)
    elif purchase == 'other_student':
        grant(db, inst, other, paid.id)
    client = login(TestClient(app), student, inst.slug)
    for suffix in ['', '/', '/assessments', '/assessments/']:
        response = client.get(f'/api/v1/courses/{course.id}{suffix}', follow_redirects=False)
        assert response.status_code == (200 if 'assessments' in suffix else 403)
        assert 'SEALED' not in response.text and str(paid.id) not in response.text


def test_one_lesson_purchase_returns_only_that_lessons_detail_and_assessments(db):
    inst, owner, student, _, course, free, paid, free_quiz, paid_quiz, assignment = domain(db)
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    paid_quiz.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    general = Quiz(institution_id=inst.id, course_id=course.id, creator_id=owner.id,
        title='UNPURCHASED GENERAL QUIZ', status='published')
    unit = Quiz(institution_id=inst.id, course_id=course.id, creator_id=owner.id,
        module_id=paid.module_id, title='AUTHORIZED MIXED UNIT QUIZ', status='published')
    db.add_all([general, unit]); db.commit()
    grant(db, inst, student, paid.id)
    client = login(TestClient(app), student, inst.slug)
    for suffix in ['', '/']:
        response = client.get(f'/api/v1/courses/{course.id}{suffix}', follow_redirects=False)
        assert response.status_code == 200
        lessons = [row for module in response.json()['modules'] for row in module['lessons']]
        assert [row['id'] for row in lessons] == [str(paid.id)]
        assert lessons[0]['content'] == paid.content
        assert str(free.id) not in response.text and free.content not in response.text
        assert 'PRIVATE WORKER DIAGNOSTIC' not in response.text
    for suffix in ['/assessments', '/assessments/']:
        response = client.get(f'/api/v1/courses/{course.id}{suffix}', follow_redirects=False)
        assert response.status_code == 200
        data = response.json()
        assert {row['id'] for row in data['lessons']} == {str(free.id), str(paid.id)}
        assert {row['id'] for row in data['quizzes']} == {str(free_quiz.id), str(paid_quiz.id), str(unit.id)}
        assert [row['id'] for row in data['assignments']] == [str(assignment.id)]
        assert 'UNPURCHASED' not in response.text
        assert response.headers['cache-control'] == 'private, no-store'


def test_an_unbought_assessments_schedule_is_not_a_refresh_deadline(db):
    inst, _, student, _, course, free, paid, quiz, *_ = domain(db)
    db.add(Enrollment(course_id=course.id, student_id=student.id)); db.commit()
    grant(db, inst, student, free.id)
    client = login(TestClient(app), student, inst.slug)
    response = client.get(f'/api/v1/courses/{course.id}/assessments')
    assert response.status_code == 200
    data = response.json()
    assert [row['id'] for row in data['lessons']] == [str(free.id)]
    assert [row['id'] for row in data['quizzes']] == [str(quiz.id)]
    assert data['assignments'] == [] and data['next_availability_at'] is None
    assert str(paid.id) not in response.text


def test_legacy_whole_course_entitlement_keeps_all_authorized_lessons(db):
    inst, _, student, _, course, free, paid, *_ = domain(db)
    db.add(Enrollment(course_id=course.id, student_id=student.id)); db.commit()
    grant(db, inst, student, course.id, EntitlementType.COURSE)
    client = login(TestClient(app), student, inst.slug)
    response = client.get(f'/api/v1/courses/{course.id}')
    assert response.status_code == 200
    assert {row['id'] for module in response.json()['modules'] for row in module['lessons']} == {str(free.id), str(paid.id)}


def test_restoring_an_unpurchased_accounts_own_cookie_does_not_grant_access(db):
    inst, _, student, _, course, *_ = domain(db)
    db.add(Enrollment(course_id=course.id, student_id=student.id)); db.commit()
    client = login(TestClient(app), student, inst.slug)
    session = client.cookies.get('matgar_session')
    assert session
    path = f'/api/v1/courses/{course.id}'
    assert client.get(path).status_code == 403
    client.cookies.clear()
    assert client.get(path).status_code == 401
    client.cookies.set('matgar_session', session)
    assert client.get(path).status_code == 403
