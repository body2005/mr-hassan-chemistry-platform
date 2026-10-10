"""One server-side policy for assessment content and attempts.

Results remain readable after the deadline, but never after entitlement is
removed. Unscoped assessments retain the project's enrollment-only policy.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course, CourseModule, Lesson, Enrollment, EnrollmentStatus
from app.models.platform import Assignment, AssignmentStatus, Quiz, QuizStatus
from app.models.user import User, UserRole
from app.services.payment_service import can_access_lesson_content


def assessment_lesson_ids(db, assessment) -> set:
    result = set(assessment.lesson_ids)
    if assessment.module_ids:
        result.update(db.scalars(select(Lesson.id).join(CourseModule, Lesson.module_id == CourseModule.id).where(
            CourseModule.course_id == assessment.course_id, CourseModule.id.in_(assessment.module_ids))))
    return result


def require_assessment_access(
    db: Session, user: User, assessment: Quiz | Assignment | None, *, writing: bool = False
) -> None:
    if assessment is None:
        raise HTTPException(404, "Assessment not found")
    course = db.get(Course, assessment.course_id)
    if course is None or (
        user.role != UserRole.PLATFORM_ADMIN
        and (assessment.institution_id != user.institution_id or course.institution_id != user.institution_id)
    ):
        raise HTTPException(404, "Assessment not found")
    published = QuizStatus.PUBLISHED if isinstance(assessment, Quiz) else AssignmentStatus.PUBLISHED
    if assessment.status != published:
        raise HTTPException(404, "Assessment not found")
    if user.role != UserRole.STUDENT:
        if user.role == UserRole.TEACHER and course.teacher_id == user.id:
            return
        if user.role in {UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN}:
            return
        raise HTTPException(404, "Assessment not found")
    enrolled = db.scalar(select(Enrollment.id).where(
        Enrollment.course_id == course.id, Enrollment.student_id == user.id,
        Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
    ))
    if enrolled is None:
        raise HTTPException(403, "Not enrolled")
    if any(not can_access_lesson_content(db, user, lesson_id) for lesson_id in assessment_lesson_ids(db, assessment)):
        raise HTTPException(403, "Lesson not unlocked")
    # Question sheets are content, not results: a future assignment is sealed
    # even for reads. Legacy assignments without starts_at remain accessible.
    if isinstance(assessment, Assignment) and assessment.starts_at:
        start = assessment.starts_at
        if (start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start) > datetime.now(timezone.utc):
            raise HTTPException(403, "Assessment is not open yet")
    if writing:
        now = datetime.now(timezone.utc)
        start = assessment.starts_at
        end = assessment.ends_at if isinstance(assessment, Quiz) else assessment.due_at
        def utc(value):
            return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
        if start and utc(start) > now:
            raise HTTPException(403, "Assessment is not open yet")
        if end and utc(end) <= now:
            raise HTTPException(403, "Assessment is closed")
