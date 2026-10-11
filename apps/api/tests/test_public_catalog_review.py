"""Public catalog filters/pagination must never hydrate cookie-private data."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.course import CourseModule, Lesson, LessonKind, Enrollment, EnrollmentStatus
from app.models.user import UserRole
from test_security_and_tenancy import make_institution, make_user, make_course, login


@pytest.mark.parametrize('authenticated', [False, True])
@pytest.mark.parametrize('asset_key', ['private/key.mp4', None, 'https://legacy.example.test/private.mp4'])
def test_public_only_catalog_filters_before_pagination_and_redacts_lesson(db, authenticated, asset_key):
    inst = make_institution(db, 'public-catalog')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    first = make_course(db, inst, teacher)
    third = make_course(db, inst, teacher)
    private = make_course(db, inst, teacher, published=False)
    first.title = 'Atomic basics'
    first.grade_level = 'SECONDARY_1'
    third.title = 'Atomic advanced'
    third.description = 'Unique searchable description'
    third.grade_level = 'SECONDARY_3'
    private.title = 'Atomic PRIVATE DRAFT'
    private.grade_level = 'SECONDARY_3'
    module = CourseModule(course_id=third.id, title='Public title', position=1)
    db.add(module)
    db.flush()
    lesson = Lesson(module_id=module.id, title='Public lesson title', kind=LessonKind.ARTICLE,
                    content='PRIVATE LESSON CONTENT', position=1, video_asset_key=asset_key, price_egp=125)
    db.add(lesson)
    db.commit()
    client = TestClient(app)
    if authenticated:
        login(client, teacher, inst.slug)
    response = client.get('/api/v1/courses', params=dict(public_only=True, grade_level='SECONDARY_3',
                                                       search='searchable description', page_size=1))
    assert response.status_code == 200
    body = response.json()
    assert body['pagination']['total'] == 1 and body['pagination']['pages'] == 1
    assert [item['id'] for item in body['items']] == [str(third.id)]
    assert 'PRIVATE' not in response.text and 'private/key' not in response.text
    stored_lesson = body['items'][0]['modules'][0]['lessons'][0]
    assert stored_lesson['content'] is None and not stored_lesson['has_video']
    assert stored_lesson['has_uploaded_video'] == (asset_key == 'private/key.mp4')
    assert stored_lesson['price_egp'] == 125
    assert stored_lesson['video_url'] is None and stored_lesson['materials'] == []
    assert client.get('/api/v1/courses?public_only=true&grade_level=unknown').status_code == 422


def test_public_catalog_search_treats_wildcards_as_literal_and_keeps_private_scope(db):
    inst = make_institution(db, 'public-literal')
    owner = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    other = make_user(db, inst.id, UserRole.TEACHER, 'other')
    literal = make_course(db, inst, owner)
    ordinary = make_course(db, inst, other)
    literal.title = '100% mass_unit'
    ordinary.title = '1000 mass unit'
    db.commit()
    client = TestClient(app)
    for search in ['%', '_', '１００％']:
        response = client.get('/api/v1/courses', params=dict(public_only=True, search=search))
        assert response.status_code == 200
        assert [item['id'] for item in response.json()['items']] == [str(literal.id)]
    login(client, owner, inst.slug)
    response = client.get('/api/v1/courses')
    assert [item['id'] for item in response.json()['items']] == [str(literal.id)]


def test_public_catalog_pages_have_stable_nonoverlapping_order(db):
    inst = make_institution(db, 'public-pages')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    courses = [make_course(db, inst, teacher) for _ in range(5)]
    for course in courses:
        course.title = 'Shared title'
        course.created_at = courses[0].created_at
    db.commit()
    client = TestClient(app)
    ids = []
    for page in [1, 2, 3]:
        response = client.get('/api/v1/courses', params=dict(public_only=True, search='Shared', sort='title',
                                                           page_size=2, page=page))
        assert response.status_code == 200
        body = response.json()
        assert body['pagination']['total'] == 5 and body['pagination']['pages'] == 3
        ids.extend(item['id'] for item in body['items'])
    assert len(ids) == len(set(ids)) == 5


def test_enrolled_catalog_filters_before_pagination_and_keeps_identity_scope(db):
    inst = make_institution(db, 'enrolled-catalog')
    owner = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    student = make_user(db, inst.id, UserRole.STUDENT, 'student')
    other = make_user(db, inst.id, UserRole.STUDENT, 'other')
    courses = [make_course(db, inst, owner) for _ in range(5)]
    for course, learner in [(courses[0], student), (courses[1], student), (courses[2], other)]:
        db.add(Enrollment(course_id=course.id, student_id=learner.id,
                          status=EnrollmentStatus.COMPLETED if course == courses[1] else EnrollmentStatus.ACTIVE))
    db.add(Enrollment(course_id=courses[3].id, student_id=student.id, status=EnrollmentStatus.WITHDRAWN))
    foreign_inst = make_institution(db, 'enrolled-foreign')
    foreign_owner = make_user(db, foreign_inst.id, UserRole.TEACHER, 'owner')
    foreign_course = make_course(db, foreign_inst, foreign_owner)
    db.add(Enrollment(course_id=foreign_course.id, student_id=student.id, status=EnrollmentStatus.ACTIVE))
    db.commit()
    client = TestClient(app)
    login(client, student, inst.slug)
    ids = []
    for page in [1, 2]:
        response = client.get('/api/v1/courses', params=dict(enrolled_only=True, page_size=1, page=page))
        assert response.status_code == 200
        body = response.json()
        assert body['pagination']['total'] == 2 and body['pagination']['pages'] == 2
        ids.extend(item['id'] for item in body['items'])
    assert set(ids) == {str(courses[0].id), str(courses[1].id)}
    assert client.get('/api/v1/courses?enrolled_only=true&public_only=true').status_code == 400


def test_enrolled_catalog_requires_student_identity(db):
    inst = make_institution(db, 'enrolled-auth')
    owner = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    make_course(db, inst, owner)
    client = TestClient(app)
    assert client.get('/api/v1/courses?enrolled_only=true').status_code == 401
    login(client, owner, inst.slug)
    assert client.get('/api/v1/courses?enrolled_only=true').status_code == 403
