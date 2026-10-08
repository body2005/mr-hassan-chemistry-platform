"""Server-side gates for the role discovery findings; no source-specific fixes."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
import pytest

from app.main import app
from app.models.platform import Question, Quiz, QuizQuestion, CalendarEvent, Notification
from app.models.course import Enrollment, EnrollmentStatus, CourseModule, Lesson, LessonKind
from app.models.progress import LessonProgress
from app.models.user import UserRole
from tests.test_security_and_tenancy import make_institution, make_user, make_course, login, csrf_headers


def setup(db, tag):
    inst = make_institution(db, tag)
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'publisher')
    course = make_course(db, inst, teacher)
    return inst, teacher, course


def test_profile_counts_and_history_are_persisted_and_owner_scoped(db):
    inst, teacher, course = setup(db, 'profile-scope')
    other = make_user(db, inst.id, UserRole.TEACHER, 'other')
    foreign_course = make_course(db, inst, other)
    second_course = make_course(db, inst, teacher)
    student = make_user(db, inst.id, UserRole.STUDENT, 'student')
    outsider = make_user(db, inst.id, UserRole.STUDENT, 'outsider')
    db.add_all([Enrollment(course_id=c.id, student_id=student.id, status=EnrollmentStatus.ACTIVE)
                for c in (course, second_course)])
    db.add(Enrollment(course_id=foreign_course.id, student_id=outsider.id, status=EnrollmentStatus.ACTIVE))
    module = CourseModule(course_id=course.id, title='Owned module', position=0)
    foreign_module = CourseModule(course_id=foreign_course.id, title='Other module', position=0)
    db.add_all([module, foreign_module]); db.flush()
    lesson = Lesson(module_id=module.id, title='Real progress lesson', kind=LessonKind.VIDEO, position=0,
                    video_asset_key='videos/owned.mp4')
    db.add_all([lesson, Lesson(module_id=module.id, title='Pending upload', kind=LessonKind.VIDEO, position=1),
                Lesson(module_id=foreign_module.id, title='Other video', kind=LessonKind.VIDEO, position=0,
                       video_asset_key='videos/other.mp4')]); db.flush()
    db.add(LessonProgress(institution_id=inst.id, student_id=student.id, lesson_id=lesson.id, completion_percent=37))
    db.commit()
    with TestClient(app) as author, TestClient(app) as learner, TestClient(app) as fresh:
        login(author, teacher, inst.slug); login(learner, student, inst.slug); login(fresh, outsider, inst.slug)
        summary = author.get('/api/v1/auth/profile-summary').json()
        assert summary == {'enrolled_students_count': 1, 'uploaded_videos_count': 1}
        me = author.get('/api/v1/auth/me').json()
        assert me['enrolled_students_count'] == me['uploaded_videos_count'] == 1
        assert learner.get('/api/v1/auth/profile-summary').json()['progress'] == [
            {'lesson_id': str(lesson.id), 'title': 'Real progress lesson', 'completion_percent': 37}]
        assert fresh.get('/api/v1/auth/profile-summary').json() == {'progress': []}


def test_atomic_publication_validation_order_and_retry(db):
    inst, teacher, course = setup(db, 'atomic-role')
    with TestClient(app) as client:
        login(client, teacher, inst.slug)
        data = {'course_id': str(course.id), 'title': 'Atomic quiz', 'idempotency_key': uuid.uuid4().hex,
                'questions': [{'prompt': 'First valid question', 'question_type': 'essay', 'points': 7},
                              {'prompt': 'x', 'question_type': 'essay', 'points': 3}]}
        for _ in range(2):
            assert client.post('/api/v1/quizzes/publish-draft', json=data, headers=csrf_headers(client)).status_code == 422
        assert not db.scalars(select(Question).where(Question.course_id == course.id)).all()
        assert not db.scalars(select(Quiz).where(Quiz.course_id == course.id)).all()
        data['questions'][1]['prompt'] = 'Second valid question'
        first = client.post('/api/v1/quizzes/publish-draft', json=data, headers=csrf_headers(client))
        assert first.status_code == 201, first.text
        retry = client.post('/api/v1/quizzes/publish-draft', json=data, headers=csrf_headers(client))
        assert retry.status_code == 201 and retry.json()['id'] == first.json()['id']
        questions = db.scalars(select(Question).where(Question.course_id == course.id)).all()
        assert len(questions) == 2
        links = db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == uuid.UUID(first.json()['id'])).order_by(QuizQuestion.position)).all()
        assert [db.get(Question, link.question_id).prompt for link in links] == ['First valid question', 'Second valid question']
        data['title'] = 'Changed content'
        # Existing domain validation errors use 400; schema failures above
        # remain 422. Both must reject without any extra writes.
        assert client.post('/api/v1/quizzes/publish-draft', json=data, headers=csrf_headers(client)).status_code == 400


def test_future_assignment_blocks_content_start_and_direct_submission(db):
    inst, teacher, course = setup(db, 'future-role')
    student = make_user(db, inst.id, UserRole.STUDENT, 'learner')
    db.add(Enrollment(course_id=course.id, student_id=student.id, status=EnrollmentStatus.ACTIVE)); db.commit()
    with TestClient(app) as author, TestClient(app) as learner:
        login(author, teacher, inst.slug); login(learner, student, inst.slug)
        data = {'course_id': str(course.id), 'title': 'Future homework', 'prompt': 'Choose a unit: A) kg B) s',
                'max_score': 7, 'starts_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
        record = author.post('/api/v1/assignments', json=data, headers=csrf_headers(author))
        assert record.status_code == 201, record.text
        homework = record.json()
        assert homework['max_score'] == 7 and homework['starts_at'] is not None
        assert author.post(f"/api/v1/assignments/{homework['id']}/publish", headers=csrf_headers(author)).status_code == 200
        for path in ['attempts', 'submissions']:
            response = learner.post(f"/api/v1/assignments/{homework['id']}/{path}", headers=csrf_headers(learner),
                                    json={'answer_text': 'Before opening', 'idempotency_key': uuid.uuid4().hex} if path == 'submissions' else None)
            assert response.status_code == 403
        assert learner.get(f"/api/v1/assignments/{homework['id']}/sheet.pdf").status_code == 403
        assert author.get(f"/api/v1/assignments/{homework['id']}/sheet.pdf").status_code == 200


def test_calendar_retries_are_idempotent_and_sender_owned(db):
    inst, teacher, _ = setup(db, 'calendar-role')
    with TestClient(app) as client:
        login(client, teacher, inst.slug)
        data = {'title': 'Physics class', 'event_type': 'lesson', 'starts_at': datetime.now(timezone.utc).isoformat(),
                'idempotency_key': uuid.uuid4().hex}
        first = client.post('/api/v1/calendar', headers=csrf_headers(client), json=data)
        retry = client.post('/api/v1/calendar', headers=csrf_headers(client), json=data)
        assert first.status_code == retry.status_code == 201, (first.text, retry.text)
        assert first.json()['id'] == retry.json()['id']
        assert len(db.scalars(select(CalendarEvent).where(CalendarEvent.creator_id == teacher.id)).all()) == 1


def test_broadcast_enforces_grade_and_owned_enrollment(db):
    inst, teacher, course = setup(db, 'audience-role')
    enrolled = make_user(db, inst.id, UserRole.STUDENT, 'owned')
    wrong_grade = make_user(db, inst.id, UserRole.STUDENT, 'wrong-grade')
    unrelated = make_user(db, inst.id, UserRole.STUDENT, 'unrelated')
    enrolled.grade_level = unrelated.grade_level = 'SECONDARY_1'
    wrong_grade.grade_level = 'SECONDARY_2'
    for student in [enrolled, wrong_grade]:
        db.add(Enrollment(course_id=course.id, student_id=student.id, status=EnrollmentStatus.ACTIVE))
    db.commit()
    with TestClient(app) as client:
        login(client, teacher, inst.slug)
        data = {'kind': 'system', 'title': 'Grade one class', 'message': 'Class information',
                'target_grade': 'SECONDARY_1', 'dedup_key': uuid.uuid4().hex}
        first = client.post('/api/v1/notifications/broadcast', headers=csrf_headers(client), json=data)
        assert first.status_code == 201, first.text
        # API intentionally omits other recipients' identities. Verify actual
        # persisted recipients rather than weakening that privacy boundary.
        ids = {str(item.recipient_id) for item in db.scalars(select(Notification).where(Notification.title == data['title'])).all()}
        assert str(enrolled.id) in ids and str(wrong_grade.id) not in ids and str(unrelated.id) not in ids
        retry = client.post('/api/v1/notifications/broadcast', headers=csrf_headers(client), json=data)
        assert [item['id'] for item in retry.json()] == [item['id'] for item in first.json()]


@pytest.mark.parametrize('role', [UserRole.TEACHER, UserRole.STUDENT])
def test_personal_photo_feature_is_closed_without_touching_existing_objects(db, monkeypatch, role):
    inst, teacher, _ = setup(db, 'avatar-role')
    user = teacher if role == UserRole.TEACHER else make_user(db, inst.id, role, 'no-photo-student')
    retained_key = f'avatars/{user.id}/retained-private-object.png'
    user.avatar_key = retained_key
    db.commit()
    def forbidden_storage():
        raise AssertionError('Removed photo endpoints must not access storage')
    monkeypatch.setattr('app.core.storage.get_storage_provider', forbidden_storage)
    with TestClient(app) as client:
        login(client, user, inst.slug)
        assert 'avatar_url' not in client.get('/api/v1/auth/me').json()
        assert client.get('/api/v1/auth/avatar').status_code == 410
        assert client.post('/api/v1/auth/avatar', headers=csrf_headers(client), json={}).status_code == 410
        assert client.post('/api/v1/auth/avatar', json={}).status_code == 403
        db.refresh(user)
        assert user.avatar_key == retained_key
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/v1/auth/avatar').status_code == 401


@pytest.mark.parametrize('dependency_failure', [True, False])
def test_video_storage_failure_is_classified_without_leaking_credentials(db, monkeypatch, caplog, dependency_failure):
    from boto3.exceptions import S3UploadFailedError
    from app.api.routes import platform
    from app.services import storage_cleanup
    inst, teacher, course = setup(db, 'upload-fault')
    module = CourseModule(course_id=course.id, title='Upload module', position=0)
    db.add(module); db.flush()
    lesson = Lesson(module_id=module.id, title='Upload lesson', kind=LessonKind.VIDEO, position=0)
    db.add(lesson); db.commit()
    compensated = []
    class FailingStorage:
        def save_file(self, *args):
            error = S3UploadFailedError if dependency_failure else RuntimeError
            raise error('signed-token-must-never-appear')
    monkeypatch.setattr(platform, 'get_storage_provider', lambda: FailingStorage())
    monkeypatch.setattr(storage_cleanup, 'compensate_upload', lambda db, key: compensated.append(key))
    with TestClient(app) as client:
        login(client, teacher, inst.slug)
        result = client.post(f'/api/v1/lessons/{lesson.id}/video', headers=csrf_headers(client),
                             files={'file': ('source.webm', b'\x1a\x45\xdf\xa3' + b'\0'*20, 'video/webm')})
        assert result.status_code == (503 if dependency_failure else 500)
        assert 'signed-token-must-never-appear' not in result.text + caplog.text
        assert 'Video storage upload failed:' in caplog.text
        assert len(compensated) == 1
        db.refresh(lesson)
        assert lesson.video_asset_key is None
