"""Published, eligible assessment points; independent of content release time.

Manager-only summaries. A missing/unmarked result contributes no earned points
without writing a zero grade. Each assessment contributes its maximum once.
"""
import math
from collections import defaultdict

from sqlalchemy import func, select

from app.models.course import Course, Enrollment, EnrollmentStatus, Lesson
from app.models.payment import StudentEntitlement, EntitlementType
from app.models.platform import (Assignment, AssignmentSubmission, AttemptStatus,
    Quiz, QuizAttempt, QuizAttemptAnswer, QuizQuestion, SubmissionStatus)
from app.models.user import User, UserRole
from app.models.extended import Grade
from app.services.content_access import as_utc
from app.services.payment_service import is_entitlement_active


def group_grade_summary(summaries):
    summaries = list(summaries)
    earned = sum(row["earned_points"] for row in summaries)
    possible = sum(row["possible_points"] for row in summaries)
    def category_rate(kind):
        maximum = sum(row[kind + "_possible"] for row in summaries)
        return round(sum(row[kind + "_earned"] for row in summaries) / maximum * 100, 2) if maximum else None
    return {"quiz_success_rate": category_rate("quiz"), "homework_success_rate": category_rate("homework"),
            "earned_points": earned, "possible_points": possible,
            "total_overall_grade": round(earned / possible * 100, 2) if possible else None,
            "pending_assessments_count": sum(row["pending_assessments_count"] for row in summaries)}


def published_grade_summaries(db, actor, student_ids, *, course_ids=None):
    if actor.role not in {UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN}:
        raise PermissionError("Gradebook summaries are restricted to managers")
    query = select(Course).where(Course.institution_id == actor.institution_id)
    if actor.role == UserRole.TEACHER:
        query = query.where(Course.teacher_id == actor.id)
    if course_ids is not None:
        query = query.where(Course.id.in_(course_ids))
    courses = {row.id: row for row in db.scalars(query)}
    audience = defaultdict(set)
    for student_id, course_id in db.execute(select(Enrollment.student_id, Enrollment.course_id)
            .join(User, User.id == Enrollment.student_id).where(
                Enrollment.student_id.in_(student_ids), Enrollment.course_id.in_(courses),
                Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
                User.institution_id == actor.institution_id, User.role == UserRole.STUDENT,
                User.deleted_at.is_(None))):
        audience[course_id].add(student_id)
    lessons = {row.id: row for row in db.scalars(select(Lesson).where(Lesson.course_id.in_(courses)))}
    entitlements = defaultdict(set)
    for row in db.scalars(select(StudentEntitlement).where(
            StudentEntitlement.institution_id == actor.institution_id,
            StudentEntitlement.student_id.in_(student_ids), StudentEntitlement.revoked_at.is_(None))):
        if is_entitlement_active(row):
            entitlements[row.student_id].add((row.entitlement_type, row.resource_id))
    quizzes = list(db.scalars(select(Quiz).where(Quiz.institution_id == actor.institution_id,
        Quiz.course_id.in_(courses), Quiz.status.in_(["published", "closed"]))))
    assignments = list(db.scalars(select(Assignment).where(Assignment.institution_id == actor.institution_id,
        Assignment.course_id.in_(courses), Assignment.status.in_(["published", "closed"]))))
    maxima = dict(db.execute(select(QuizQuestion.quiz_id, func.sum(QuizQuestion.points)).where(
        QuizQuestion.quiz_id.in_([row.id for row in quizzes])).group_by(QuizQuestion.quiz_id)).all())
    pending = select(QuizAttemptAnswer.id).where(QuizAttemptAnswer.attempt_id == QuizAttempt.id,
        QuizAttemptAnswer.graded_at.is_(None)).exists()
    last_mark = select(func.max(QuizAttemptAnswer.graded_at)).where(
        QuizAttemptAnswer.attempt_id == QuizAttempt.id).scalar_subquery()
    attempts = {}
    for attempt, unmarked, marked_at in db.execute(select(QuizAttempt, pending, last_mark).where(
            QuizAttempt.institution_id == actor.institution_id, QuizAttempt.student_id.in_(student_ids),
            QuizAttempt.quiz_id.in_([row.id for row in quizzes]), QuizAttempt.is_practice.is_(False),
            QuizAttempt.status == AttemptStatus.SUBMITTED, QuizAttempt.submitted_at.is_not(None))
            .order_by(QuizAttempt.attempt_number.desc(), QuizAttempt.submitted_at.desc(), QuizAttempt.id)):
        # Same legacy selection as reports: latest submitted official attempt.
        # Current attempts after number one are marked practice and excluded.
        attempts.setdefault((attempt.student_id, attempt.quiz_id), (attempt, unmarked, marked_at))
    submissions = {}
    for row in db.scalars(select(AssignmentSubmission).where(
            AssignmentSubmission.institution_id == actor.institution_id,
            AssignmentSubmission.student_id.in_(student_ids),
            AssignmentSubmission.assignment_id.in_([row.id for row in assignments]))
            .order_by(AssignmentSubmission.version.desc(), AssignmentSubmission.id)):
        submissions.setdefault((row.student_id, row.assignment_id), row)

    ledger = {(row.student_id, row.item_type, row.item_id): row for row in db.scalars(select(Grade).where(
        Grade.institution_id == actor.institution_id, Grade.student_id.in_(student_ids),
        Grade.course_id.in_(courses), Grade.item_type.in_(["quiz", "assignment"]), Grade.is_current.is_(True)))}
    modules = defaultdict(set)
    for lesson in lessons.values():
        modules[(lesson.course_id, lesson.module_id)].add(lesson.id)
    totals = {student_id: dict(quiz_earned=0.0, quiz_possible=0.0, homework_earned=0.0,
        homework_possible=0.0, published_assessments_count=0, pending_quiz_attempts=0,
        pending_homework_count=0, quiz_attempts_count=0, unattempted_assessments_count=0,
        invalid_assessments_count=0, quiz_assessments_count=0, homework_assessments_count=0, homework_submissions_count=0) for student_id in student_ids}
    for assessment in [*quizzes, *assignments]:
        course = courses[assessment.course_id]
        required = set(assessment.lesson_ids)
        for module_id in assessment.module_ids:
            required.update(modules[(course.id, module_id)])
        is_quiz = isinstance(assessment, Quiz)
        maximum = maxima.get(assessment.id) if is_quiz else assessment.max_score
        for student_id in audience[course.id]:
            access = entitlements[student_id]
            # Assignment eligibility follows enrollment/payment scope, not the
            # scheduled opening or processing state of the linked lesson.
            if any(lid not in lessons or lessons[lid].course_id != course.id or not (
                    (EntitlementType.COURSE, course.id) in access or
                    (EntitlementType.LESSON, lid) in access or
                    (float(course.price_egp or 0) == 0 and float(lessons[lid].price_egp or 0) == 0))
                    for lid in required):
                continue
            data = totals[student_id]
            if maximum is None or not math.isfinite(maximum) or maximum <= 0:
                data["invalid_assessments_count"] += 1
                continue
            kind = "quiz" if is_quiz else "homework"
            data[kind + "_assessments_count"] += 1
            data[kind + "_possible"] += maximum
            data["published_assessments_count"] += 1
            score = None
            graded_at = None
            if is_quiz:
                result = attempts.get((student_id, assessment.id))
                if result:
                    attempt, unmarked, marked_at = result
                    graded_at = max(as_utc(value) for value in
                        (attempt.results_approved_at, marked_at, attempt.submitted_at) if value)
                    data["quiz_attempts_count"] += 1
                    data["pending_quiz_attempts"] += int(bool(unmarked or not attempt.results_approved_at))
                    # Managers may see the current calculated contribution;
                    # this function is never a student disclosure endpoint.
                    if attempt.total_points and math.isfinite(attempt.total_points) and attempt.total_points > 0:
                        score = (attempt.score / attempt.total_points * maximum) if attempt.score is not None else None
                else:
                    data["unattempted_assessments_count"] += 1
            else:
                row = submissions.get((student_id, assessment.id))
                if row:
                    data["homework_submissions_count"] += 1
                    graded_at = row.graded_at or row.submitted_at
                    graded = row.graded_at is not None and row.status in (SubmissionStatus.GRADED, SubmissionStatus.APPROVED)
                    data["pending_homework_count"] += int(not graded or row.final_score is None)
                    score = row.final_score if graded else None
                else:
                    data["unattempted_assessments_count"] += 1
            override = ledger.get((student_id, "quiz" if is_quiz else "assignment", assessment.id))
            if override and (graded_at is None or as_utc(override.updated_at) >= as_utc(graded_at)):
                # Explicit teacher ledger corrections use the same published
                # maximum; duplicate history rows never add another weight.
                if (override.max_score and math.isfinite(override.max_score) and override.max_score > 0
                        and override.score is not None and math.isfinite(override.score)
                        and 0 <= override.score <= override.max_score):
                    score = override.score / override.max_score * maximum
            if score is not None and math.isfinite(score) and 0 <= score <= maximum:
                data[kind + "_earned"] += score
    result = {}
    for student_id, data in totals.items():
        possible = data["quiz_possible"] + data["homework_possible"]
        earned = data["quiz_earned"] + data["homework_earned"]
        def percentage(kind):
            return round(data[kind + "_earned"] / data[kind + "_possible"] * 100, 2) if data[kind + "_possible"] else None
        result[student_id] = {**data, "earned_points": earned, "possible_points": possible,
            "total_overall_grade": round(earned / possible * 100, 2) if possible else None,
            "quiz_success_rate": percentage("quiz"), "average_quiz_score": percentage("quiz"),
            "homework_success_rate": percentage("homework"),
            "pending_assessments_count": data["pending_quiz_attempts"] + data["pending_homework_count"],
            "has_completed_exam": bool(data["quiz_attempts_count"])}
    return result
