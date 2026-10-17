"""Authorization regressions for course metadata projection."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models.course import CourseModule, Enrollment, EnrollmentStatus, Lesson
from app.models.platform import Assignment, AssignmentAttempt, AssignmentSubmission, Quiz, QuizAttempt
from app.models.user import UserRole
from tests.test_security_and_tenancy import csrf_headers, login, make_course, make_institution, make_user


def domain(db):
    inst = make_institution(db, 'metadata-boundary')
    owner = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    student = make_user(db, inst.id, UserRole.STUDENT, 'student')
    other = make_user(db, inst.id, UserRole.STUDENT, 'other')
    course = make_course(db, inst, owner)
    course.price_egp = 0
    module = CourseModule(course_id=course.id, title='Private module title', position=1)
    db.add(module); db.flush()
    free = Lesson(course_id=course.id, module_id=module.id, title='Free lesson product',
        kind='article', position=1, price_egp=0, content='Authorized lesson body')
    now = datetime.now(timezone.utc)
    paid = Lesson(course_id=course.id, module_id=module.id, title='Paid lesson product',
        kind='article', position=2, price_egp=50, content='SEALED LESSON BODY',
        publish_at=now - timedelta(days=1), available_until=now + timedelta(days=1),
        video_duration_seconds=180, materialization_status='failed',
        materialization_error='PRIVATE WORKER DIAGNOSTIC')
    db.add_all([free, paid]); db.flush()
    public_quiz = Quiz(institution_id=inst.id, course_id=course.id, creator_id=owner.id,
        lesson_id=free.id, title='Authorized quiz', status='published')
    paid_quiz = Quiz(institution_id=inst.id, course_id=course.id, creator_id=owner.id,
        lesson_id=paid.id, title='SEALED QUIZ TITLE', status='published',
        starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=2))
    assignment = Assignment(institution_id=inst.id, course_id=course.id, creator_id=owner.id,
        lesson_id=paid.id, title='SEALED ASSIGNMENT TITLE', prompt='SEALED ASSIGNMENT BODY',
        status='published', due_at=now + timedelta(hours=3))
    db.add_all([public_quiz, paid_quiz, assignment]); db.commit()
    return inst, owner, student, other, course, free, paid, public_quiz, paid_quiz, assignment


def test_anonymous_list_is_public_but_detail_requires_authentication(db):
    inst, owner, _, _, course, *_ = domain(db)
    draft = make_course(db, inst, owner, published=False)
    visitor = TestClient(app)
    detail = visitor.get(f'/api/v1/courses/{course.id}')
    assert detail.status_code == 401
    allowed = {'id', 'code', 'title', 'description', 'status', 'price_egp', 'grade_level'}
    listing = visitor.get('/api/v1/courses')
    assert listing.status_code == 200
    assert [row['id'] for row in listing.json()['items']] == [str(course.id)]
    assert all(set(row) == allowed for row in listing.json()['items'])
    assert visitor.get(f'/api/v1/courses/{draft.id}').status_code == 401
    assert visitor.get(f'/api/v1/courses/{course.id}/assessments').status_code == 401
    assert listing.headers['cache-control'] == 'private, no-store'
    assert 'Cookie' in listing.headers['vary']


def test_public_only_uses_same_allowlist_even_with_owner_cookie(db):
    inst, owner, _, _, course, *_ = domain(db)
    teacher = login(TestClient(app), owner, inst.slug)
    public = teacher.get('/api/v1/courses?public_only=true').json()['items'][0]
    assert public['id'] == str(course.id)
    assert not {'modules', 'teacher_id', 'institution_id', 'created_at', 'updated_at'} & public.keys()
    private = teacher.get(f'/api/v1/courses/{course.id}').json()
    assert private['modules'][0]['lessons'][1]['content'] == 'SEALED LESSON BODY'


def test_reuploaded_lesson_uses_latest_ready_upload_date_for_both_roles(db):
    from app.models.video_upload import VideoUpload

    inst, owner, student, _, course, free, *_ = domain(db)
    now = datetime.now(timezone.utc)
    free.created_at = now - timedelta(days=2)
    old_at, newest_at = now - timedelta(hours=2), now - timedelta(hours=1)
    for state, created in [('superseded', old_at), ('ready', newest_at)]:
        db.add(VideoUpload(lesson_id=free.id, owner_id=owner.id, request_key=state,
            filename='synthetic.mp4', content_type='video/mp4', size_bytes=100,
            fingerprint='0' * 64, object_key=f'quarantine/{state}', status=state,
            created_at=created, expires_at=now + timedelta(days=1), outputs=[]))
    db.add(Enrollment(course_id=course.id, student_id=student.id, status=EnrollmentStatus.ACTIVE))
    db.commit()
    teacher = login(TestClient(app), owner, inst.slug)
    own = teacher.get(f'/api/v1/courses/{course.id}').json()['modules'][0]['lessons'][0]
    assert datetime.fromisoformat(own['uploaded_at']).replace(tzinfo=timezone.utc) == newest_at
    learner = login(TestClient(app), student, inst.slug)
    visible = learner.get('/api/v1/courses?enrolled_only=true').json()['items'][0]['modules'][0]['lessons'][0]
    assert datetime.fromisoformat(visible['uploaded_at']).replace(tzinfo=timezone.utc) == newest_at
    assert visible['video_upload'] is None


@pytest.mark.parametrize('account', ['student', 'other'])
def test_unenrolled_students_receive_no_assessment_metadata(db, account):
    inst, _, student, other, course, *_ = domain(db)
    client = login(TestClient(app), student if account == 'student' else other, inst.slug)
    response = client.get(f'/api/v1/courses/{course.id}/assessments')
    assert response.status_code == 403
    assert 'SEALED' not in response.text
    assert not {'lessons', 'quizzes', 'assignments', 'next_availability_at'} & response.json().keys()


@pytest.mark.parametrize('state', [EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED])
def test_free_enrollment_reads_only_free_activities_and_sales_entries_stay_redacted(db, state):
    inst, _, student, _, course, free, paid, quiz, *_ = domain(db)
    db.add(Enrollment(course_id=course.id, student_id=student.id, status=state)); db.commit()
    client = login(TestClient(app), student, inst.slug)
    response = client.get(f'/api/v1/courses/{course.id}/assessments')
    assert response.status_code == 200
    assert [row['id'] for row in response.json()['quizzes']] == [str(quiz.id)]
    assert response.json()['assignments'] == []
    assert str(paid.id) not in response.text
    assert 'SEALED' not in response.text
    assert client.get(f'/api/v1/courses/{course.id}').status_code == 403
    sale = client.get('/api/v1/courses').json()['items'][0]
    details = sale['modules'][0]['lessons']
    assert details[0]['content'] == 'Authorized lesson body'
    # Logged-in sales entries retain title/id/price to support lesson purchase,
    # without granting access to content or private playback/schedule details.
    assert details[1]['title'] == paid.title and details[1]['price_egp'] == 50
    for key in ['content', 'video_url', 'video_upload', 'video_duration_seconds',
                'publish_at', 'available_until', 'materialization_error', 'uploaded_at']:
        assert details[1][key] is None
    assert details[1]['materials'] == []


def test_draft_and_cross_tenant_assessment_metadata_are_not_found(db):
    inst, owner, student, _, course, *_ = domain(db)
    draft = make_course(db, inst, owner, published=False)
    foreign = make_institution(db, 'metadata-foreign')
    foreign_owner = make_user(db, foreign.id, UserRole.TEACHER, 'foreign-owner')
    foreign_course = make_course(db, foreign, foreign_owner)
    db.add(Enrollment(course_id=draft.id, student_id=student.id)); db.commit()
    client = login(TestClient(app), student, inst.slug)
    assert client.get(f'/api/v1/courses/{draft.id}/assessments').status_code == 404
    assert client.get(f'/api/v1/courses/{foreign_course.id}/assessments').status_code == 404
    peer = make_user(db, inst.id, UserRole.TEACHER, 'peer')
    assert login(TestClient(app), peer, inst.slug).get(
        f'/api/v1/courses/{course.id}/assessments').status_code == 404


def test_withdrawn_enrollment_does_not_authorize_metadata(db):
    inst, _, student, _, course, *_ = domain(db)
    db.add(Enrollment(course_id=course.id, student_id=student.id, status=EnrollmentStatus.WITHDRAWN))
    db.commit()
    client = login(TestClient(app), student, inst.slug)
    assert client.get(f'/api/v1/courses/{course.id}/assessments').status_code == 403


def test_action_endpoints_deny_unenrolled_student_independently(db):
    inst, _, student, _, _, _, paid, quiz, _, assignment = domain(db)
    client = login(TestClient(app), student, inst.slug)
    csrf = csrf_headers(client)
    assert client.get(f'/api/v1/quizzes/{quiz.id}/solve').status_code == 403
    assert client.post(f'/api/v1/quizzes/{quiz.id}/attempts', headers=csrf).status_code == 403
    assert client.get(f'/api/v1/assignments/{assignment.id}/solve').status_code == 403
    assert client.post(f'/api/v1/assignments/{assignment.id}/attempts', headers=csrf).status_code == 403
    assert client.post(f'/api/v1/assignments/{assignment.id}/submissions', headers=csrf,
        json={'answer_text': 'Unauthorized attempt', 'idempotency_key': 'metadata-denied-submit'}).status_code == 403
    assert client.post(f'/api/v1/lessons/{paid.id}/video-token', headers=csrf).status_code == 403
    for model in [QuizAttempt, AssignmentAttempt, AssignmentSubmission]:
        assert db.scalar(select(func.count()).select_from(model)) == 0
