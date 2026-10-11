"""Assignment creation and legacy publication must validate meaningful content."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.course import CourseModule, Lesson, LessonKind
from app.models.institution import Institution
from app.models.platform import Assignment, AssignmentStatus
from app.models.user import UserRole
from app.schemas import AssignmentCreateRequest
from app.services import platform_service
from test_security_and_tenancy import make_institution, make_user, make_course, login, csrf_headers


def domain(db):
    institution = make_institution(db, 'assignment-publication')
    teacher = make_user(db, institution.id, UserRole.TEACHER, 'owner')
    course = make_course(db, institution, teacher)
    client = login(TestClient(app, raise_server_exceptions=False), teacher, institution.slug)
    return teacher, course, client


@pytest.mark.parametrize('prompt', ['  ', '\t\n', ' a '])
def test_create_rejects_blank_or_too_short_trimmed_prompt_without_insert(db, prompt):
    _, course, client = domain(db)
    response = client.post('/api/v1/assignments', headers=csrf_headers(client), json={
        'course_id': str(course.id), 'title': 'Valid homework', 'prompt': prompt,
    })
    assert response.status_code == 422
    assert db.query(Assignment).count() == 0


@pytest.mark.parametrize('changes', [
    {'prompt': '  '}, {'prompt': 'a'}, {'title': '  '},
    {'max_score': 0}, {'max_score': -1}, {'max_score': float('inf')},
    {'starts_at': datetime.now(timezone.utc) + timedelta(days=2),
     'due_at': datetime.now(timezone.utc) + timedelta(days=1)},
])
def test_legacy_publish_rejects_invalid_stored_content_without_mutation(db, changes):
    teacher, course, client = domain(db)
    values = dict(institution_id=teacher.institution_id, course_id=course.id,
                  creator_id=teacher.id, title='Legacy homework', prompt='Explain the answer',
                  max_score=10, status=AssignmentStatus.DRAFT)
    assignment = Assignment(**{**values, **changes})
    db.add(assignment)
    db.commit()
    # Compare persisted values; SQLite reloads timezone columns as naive UTC.
    db.refresh(assignment)
    before = (assignment.title, assignment.prompt, assignment.max_score,
              assignment.starts_at, assignment.due_at)
    response = client.post(f'/api/v1/assignments/{assignment.id}/publish',
                           headers=csrf_headers(client))
    assert response.status_code == 400
    db.expire_all()
    assert assignment.status == AssignmentStatus.DRAFT
    assert (assignment.title, assignment.prompt, assignment.max_score,
            assignment.starts_at, assignment.due_at) == before


def test_legacy_publish_rechecks_lesson_course_scope(db):
    teacher, course, client = domain(db)
    unrelated = make_course(db, db.get(Institution, teacher.institution_id), teacher)
    module = CourseModule(course_id=unrelated.id, title='Other unit', position=1)
    db.add(module)
    db.flush()
    lesson = Lesson(module_id=module.id, title='Other lesson', kind=LessonKind.ARTICLE, position=1)
    db.add(lesson)
    db.flush()
    assignment = Assignment(institution_id=teacher.institution_id, course_id=course.id,
        creator_id=teacher.id, title='Wrong lesson', prompt='Explain the answer', lesson_id=lesson.id)
    db.add(assignment)
    db.commit()
    response = client.post(f'/api/v1/assignments/{assignment.id}/publish', headers=csrf_headers(client))
    assert response.status_code == 400
    db.expire_all()
    assert assignment.status == AssignmentStatus.DRAFT


def test_service_create_rejects_invalid_constructed_payload_without_insert(db):
    teacher, course, _ = domain(db)
    payload = AssignmentCreateRequest.model_construct(course_id=course.id, title='Valid title',
        prompt='  ', starts_at=None, due_at=None, max_score=10, module_id=None, lesson_id=None)
    with pytest.raises(ValueError):
        platform_service.create_assignment(db, teacher, payload)
    assert db.query(Assignment).count() == 0


def test_valid_create_normalizes_content_and_legacy_publish_preserves_it(db):
    _, course, client = domain(db)
    response = client.post('/api/v1/assignments', headers=csrf_headers(client), json={
        'course_id': str(course.id), 'title': '  واجب الكيمياء  ',
        'prompt': '  اشرح قانون حفظ الكتلة  ', 'max_score': 5,
    })
    assert response.status_code == 201
    body = response.json()
    assert body['title'] == 'واجب الكيمياء'
    assert body['prompt'] == 'اشرح قانون حفظ الكتلة'
    published = client.post(f'/api/v1/assignments/{body["id"]}/publish', headers=csrf_headers(client))
    assert published.status_code == 200
    assert published.json()['prompt'] == body['prompt']
