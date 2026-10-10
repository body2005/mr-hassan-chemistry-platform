import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.course import CourseModule, Lesson, Enrollment
from app.models.platform import Quiz
from app.models.user import UserRole
from app.schemas import QuizPublishRequest, AssignmentCreateRequest
from app.services.platform_service import publish_quiz_atomic, start_quiz, create_assignment, publish_assignment
from tests.test_security_and_tenancy import make_institution, make_user, make_course, login


def world(db):
    inst = make_institution(db, 'scope-schedule')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    student = make_user(db, inst.id, UserRole.STUDENT, 'learner')
    course = make_course(db, inst, teacher)
    course.price_egp = 0
    modules = [CourseModule(course_id=course.id, title=f'Unit {i}', position=i) for i in [1, 2]]
    db.add_all(modules); db.flush()
    lessons = [Lesson(module_id=m.id, title=f'Lesson {i}', kind='video', price_egp=0, position=1) for i, m in enumerate(modules)]
    db.add_all(lessons)
    db.add(Enrollment(course_id=course.id, student_id=student.id)); db.commit()
    return inst, teacher, student, course, modules, lessons


def payload(course, **changes):
    return QuizPublishRequest(course_id=course.id, title='Scope quiz', idempotency_key=uuid.uuid4().hex,
        questions=[{'question_type': 'essay', 'prompt': 'Explain the experiment', 'points': 1}], **changes)


def test_multiple_scope_roundtrip_and_paid_lesson_is_not_bypassed(db):
    inst, teacher, student, course, modules, lessons = world(db)
    quiz = publish_quiz_atomic(db, teacher, payload(course, lesson_ids=[l.id for l in lessons], module_ids=[m.id for m in modules]))
    db.expire_all()
    stored = db.get(Quiz, quiz.id)
    assert set(stored.lesson_ids) == {l.id for l in lessons}
    assert set(stored.module_ids) == {m.id for m in modules}
    learner = login(TestClient(app), student, inst.slug)
    listing = learner.get(f'/api/v1/courses/{course.id}/assessments').json()['quizzes'][0]
    assert len(listing['lesson_ids']) == 2 and len(listing['module_ids']) == 2
    assert listing['accessible'] is True
    lessons[1].price_egp = 50; db.commit()
    assert learner.get(f'/api/v1/quizzes/{quiz.id}/solve').status_code == 403
    assert learner.get(f'/api/v1/courses/{course.id}/assessments').json()['quizzes'][0]['accessible'] is False


def test_another_courses_scope_rejected_before_any_quiz_is_written(db):
    inst, teacher, _, course, _, lessons = world(db)
    other = make_course(db, inst, teacher)
    module = CourseModule(course_id=other.id, title='Other course', position=1)
    db.add(module); db.flush()
    with pytest.raises(ValueError):
        publish_quiz_atomic(db, teacher, payload(course, lesson_ids=[lessons[0].id], module_ids=[module.id]))
    assert db.query(Quiz).count() == 0


def test_open_and_close_boundaries_and_attempt_clock_are_enforced(db):
    inst, teacher, student, course, _, lessons = world(db)
    now = datetime.now(timezone.utc)
    quiz = publish_quiz_atomic(db, teacher, payload(course, lesson_ids=[lessons[0].id], duration_seconds=3600,
        starts_at=now + timedelta(minutes=1), ends_at=now + timedelta(minutes=2)))
    learner = login(TestClient(app), student, inst.slug)
    assert learner.get(f'/api/v1/quizzes/{quiz.id}/solve').status_code == 403
    quiz.starts_at = now - timedelta(minutes=1); db.commit()
    attempt = start_quiz(db, student, quiz.id)
    assert abs((attempt.expires_at.replace(tzinfo=timezone.utc) - (now + timedelta(minutes=2))).total_seconds()) < 1
    quiz.ends_at = now - timedelta(seconds=1); db.commit()
    assert learner.get(f'/api/v1/quizzes/{quiz.id}/solve').status_code == 403


def test_assignment_supports_multiple_units_and_lessons(db):
    _, teacher, _, course, modules, lessons = world(db)
    assignment = create_assignment(db, teacher, AssignmentCreateRequest(course_id=course.id, title='Homework', prompt='Explain both lessons',
        lesson_ids=[l.id for l in lessons], module_ids=[m.id for m in modules]))
    assignment = publish_assignment(db, teacher, assignment.id)
    assert len(assignment.lesson_ids) == len(assignment.module_ids) == 2


def test_legacy_lesson_parent_does_not_require_other_paid_lessons(db):
    inst, teacher, student, course, modules, lessons = world(db)
    extra = Lesson(module_id=modules[0].id, title='Paid sibling', kind='video', price_egp=50, position=2)
    db.add(extra); db.commit()
    quiz = publish_quiz_atomic(db, teacher, payload(course, lesson_id=lessons[0].id, module_id=modules[0].id))
    assert quiz.lesson_ids == [lessons[0].id]
    assert quiz.module_ids == []
    learner = login(TestClient(app), student, inst.slug)
    assert learner.get(f'/api/v1/quizzes/{quiz.id}/solve').status_code == 200
