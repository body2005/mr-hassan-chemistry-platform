import uuid
from datetime import datetime, timezone, timedelta
import pytest
from app.models.course import Enrollment
from app.models.extended import Grade
from app.models.platform import Assignment, AssignmentSubmission, SubmissionStatus, QuizAttempt, AttemptStatus, Quiz
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


def test_combined_total_uses_published_possible_points(db, world):
    inst, teacher, _, course = world
    quiz(db, world, 5, 100)
    db.add(Assignment(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
                      title='Homework', prompt='Explain', max_score=38, status='published'))
    db.commit()
    row = summary(db, world)
    assert row['quiz_success_rate'] == 100
    assert row['homework_success_rate'] == 0
    assert row['earned_points'] == 5 and row['possible_points'] == 43
    assert row['total_overall_grade'] == 11.63


def test_items_use_point_weights_and_absent_category_is_excluded(db, world):
    quiz(db, world, 1, 100)
    quiz(db, world, 100, 0)
    row = summary(db, world)
    assert row['quiz_success_rate'] == 0.99
    assert row['homework_success_rate'] is None
    assert row['total_overall_grade'] == 0.99


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


def test_group_uses_combined_points_without_duplicate_category_weights():
    rows = [dict(earned_points=1, possible_points=1, quiz_success_rate=100,
                 homework_success_rate=None, total_overall_grade=100, pending_assessments_count=0,
                 quiz_earned=1, quiz_possible=1, homework_earned=0, homework_possible=0),
            dict(earned_points=0, possible_points=100, quiz_success_rate=0,
                 homework_success_rate=None, total_overall_grade=0, pending_assessments_count=0,
                 quiz_earned=0, quiz_possible=100, homework_earned=0, homework_possible=0)]
    assert group_grade_summary(rows)['total_overall_grade'] == 0.99


def test_future_publication_counts_but_withdrawal_excludes_it(db, world):
    quiz(db, world, 10, 100)
    row = db.query(Quiz).one()
    row.starts_at = datetime.now(timezone.utc) + timedelta(days=1)
    db.commit()
    assert summary(db, world)['possible_points'] == 10
    row.status = 'draft'; db.commit()
    assert summary(db, world)['possible_points'] == 0
    row.status = 'published'; db.commit()
    assert summary(db, world)['possible_points'] == 10


def test_student_total_never_discloses_unapproved_assignment_score(db, world):
    inst, teacher, student, course = world
    item = Assignment(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
        title='Homework', prompt='Explain', max_score=100, status='published')
    db.add(item); db.flush()
    now = datetime.now(timezone.utc)
    result = AssignmentSubmission(institution_id=inst.id, assignment_id=item.id,
        student_id=student.id, version=1, answer_text='My answer', idempotency_key='answer-1',
        submitted_at=now, graded_at=now, final_score=80, status=SubmissionStatus.GRADED)
    db.add(result); db.commit()
    own = lambda: published_grade_summaries(db, student, [student.id])[student.id]
    assert summary(db, world)['total_overall_grade'] == 80
    assert own()['total_overall_grade'] == 0 and own()['pending_assessments_count'] == 1
    result.status = SubmissionStatus.APPROVED; result.approved_at = now; db.commit()
    assert own()['total_overall_grade'] == 80 and own()['pending_assessments_count'] == 0
    result.final_score = 0; db.commit()
    assert own()['total_overall_grade'] == 0 and own()['pending_assessments_count'] == 0
    assert own()['unattempted_assessments_count'] == 0
