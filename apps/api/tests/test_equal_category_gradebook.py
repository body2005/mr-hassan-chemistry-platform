import uuid
from datetime import datetime, timezone
import pytest
from app.models.course import Enrollment
from app.models.extended import Grade
from app.models.platform import Assignment, QuizAttempt, AttemptStatus
from app.models.user import UserRole
from app.schemas import QuizPublishRequest
from app.services.gradebook import published_grade_summaries, group_grade_summary
from app.services.platform_service import publish_quiz_atomic
from tests.test_security_and_tenancy import make_institution, make_user, make_course


@pytest.fixture
def world(db):
    inst = make_institution(db, 'equal-weight')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'teacher')
    student = make_user(db, inst.id, UserRole.STUDENT, 'student')
    course = make_course(db, inst, teacher)
    course.price_egp = 0
    db.add(Enrollment(course_id=course.id, student_id=student.id)); db.commit()
    return inst, teacher, student, course


def quiz(db, world, points, percentage):
    inst, teacher, student, course = world
    row = publish_quiz_atomic(db, teacher, QuizPublishRequest(course_id=course.id,
        title='Quiz', idempotency_key=uuid.uuid4().hex,
        questions=[dict(question_type='essay', prompt='Explain', points=points)]))
    now = datetime.now(timezone.utc)
    db.add(QuizAttempt(institution_id=inst.id, quiz_id=row.id, student_id=student.id,
        attempt_number=1, started_at=now, submitted_at=now, results_approved_at=now,
        status=AttemptStatus.SUBMITTED, score=points * percentage / 100, total_points=points))
    db.commit()


def summary(db, world):
    _, teacher, student, _ = world
    return published_grade_summaries(db, teacher, [student.id])[student.id]


def test_quiz_and_homework_each_have_half_weight_regardless_of_points(db, world):
    inst, teacher, _, course = world
    quiz(db, world, 5, 100)
    db.add(Assignment(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
                      title='Homework', prompt='Explain', max_score=38, status='published'))
    db.commit()
    row = summary(db, world)
    assert row['quiz_success_rate'] == 100
    assert row['homework_success_rate'] == 0
    assert row['total_overall_grade'] == 50


def test_items_have_equal_weight_and_absent_category_is_excluded(db, world):
    quiz(db, world, 1, 100)
    quiz(db, world, 100, 0)
    row = summary(db, world)
    assert row['quiz_success_rate'] == 50
    assert row['homework_success_rate'] is None
    assert row['total_overall_grade'] == 50


def test_homework_only_and_empty_gradebook(db, world):
    assert summary(db, world)['total_overall_grade'] is None
    inst, teacher, student, course = world
    row = Assignment(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
                     title='Homework', prompt='Explain', max_score=200, status='published')
    db.add(row); db.flush()
    db.add(Grade(institution_id=inst.id, student_id=student.id, course_id=course.id,
        item_type='assignment', item_id=row.id, score=8, max_score=10, graded_by=teacher.id))
    db.commit()
    result = summary(db, world)
    assert result['quiz_success_rate'] is None
    assert result['total_overall_grade'] == 80


def test_group_uses_student_percentages_instead_of_point_totals():
    rows = [dict(earned_points=1, possible_points=1, quiz_success_rate=100,
                 homework_success_rate=None, total_overall_grade=100, pending_assessments_count=0),
            dict(earned_points=0, possible_points=100, quiz_success_rate=0,
                 homework_success_rate=None, total_overall_grade=0, pending_assessments_count=0)]
    assert group_grade_summary(rows)['total_overall_grade'] == 50
