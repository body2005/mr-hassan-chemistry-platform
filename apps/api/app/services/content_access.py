"""One server-side policy for assessment content and attempts.

Results remain readable after the deadline, but never after entitlement is
removed. Unscoped assessments retain the project's enrollment-only policy.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import CourseStatus, Course, CourseModule, Lesson, Enrollment, EnrollmentStatus
from app.models.platform import Assignment, AssignmentStatus, Quiz, QuizStatus
from app.models.user import User, UserRole
from app.services.payment_service import can_access_lesson_content


def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def assessment_started(assessment, now=None):
    now = now or datetime.now(timezone.utc)
    return not assessment.starts_at or as_utc(assessment.starts_at) <= now


def assessment_open(assessment, now=None):
    now = now or datetime.now(timezone.utc)
    end = assessment.ends_at if isinstance(assessment, Quiz) else assessment.due_at
    return assessment.status == "published" and assessment_started(assessment, now) and (not end or now < as_utc(end))


def assessment_window_filter(model, now=None):
    """Apply the same inclusive start boundary to student list queries."""
    from sqlalchemy import or_
    return or_(model.starts_at.is_(None), model.starts_at <= (now or datetime.now(timezone.utc)))


def filter_student_assessments(db, user, items):
    """Batch the central scope/start policy; never one lookup per assessment."""
    if user.role != UserRole.STUDENT or not items:
        return items
    from collections import defaultdict
    from app.services.payment_service import accessible_course_lesson_ids
    course_ids = {item.course_id for item in items}
    courses = {row.id: row for row in db.scalars(select(Course).where(
        Course.id.in_(course_ids), Course.institution_id == user.institution_id,
        Course.status == CourseStatus.PUBLISHED))}
    enrolled = set(db.scalars(select(Enrollment.course_id).where(
        Enrollment.course_id.in_(courses), Enrollment.student_id == user.id,
        Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]))))
    lessons = defaultdict(list)
    for row in db.scalars(select(Lesson).where(Lesson.course_id.in_(courses))):
        lessons[row.course_id].append(row)
    access = {cid: accessible_course_lesson_ids(db, user, course, lessons[cid], enrolled=cid in enrolled)
              for cid, course in courses.items()}
    now = datetime.now(timezone.utc)
    return [item for item in items if item.institution_id == user.institution_id
            and item.course_id in enrolled and item.status == "published" and assessment_started(item, now)
            and (set(item.lesson_ids) | {lesson.id for lesson in lessons[item.course_id]
                 if lesson.module_id in item.module_ids}).issubset(access[item.course_id])]


def assessment_lesson_ids(db, assessment) -> set:
    result = set(assessment.lesson_ids)
    if assessment.module_ids:
        result.update(db.scalars(select(Lesson.id).join(CourseModule, Lesson.module_id == CourseModule.id).where(
            CourseModule.course_id == assessment.course_id, CourseModule.id.in_(assessment.module_ids))))
    return result


def require_assessment_access(
    db: Session, user: User, assessment: Quiz | Assignment | None, *, writing: bool = False, results: bool = False
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
    if assessment.status != published and not (results and assessment.status == "closed"):
        raise HTTPException(404, "Assessment not found")
    if user.role != UserRole.STUDENT:
        if user.role == UserRole.TEACHER and course.teacher_id == user.id:
            return
        if user.role in {UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN}:
            return
        raise HTTPException(404, "Assessment not found")
    if course.status != CourseStatus.PUBLISHED and not results:
        raise HTTPException(404, "Assessment not found")
    enrolled = db.scalar(select(Enrollment.id).where(
        Enrollment.course_id == course.id, Enrollment.student_id == user.id,
        Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
    ))
    if enrolled is None:
        raise HTTPException(403, "Not enrolled")
    required = assessment_lesson_ids(db, assessment)
    if results:
        # Results survive changes to lesson readiness or release time, but
        # remain protected by enrollment, tenant and payment authorization.
        from app.models.payment import StudentEntitlement, EntitlementType
        from app.services.payment_service import is_entitlement_active
        active = {(row.entitlement_type, row.resource_id) for row in db.scalars(select(StudentEntitlement).where(
            StudentEntitlement.student_id == user.id, StudentEntitlement.institution_id == user.institution_id,
            StudentEntitlement.revoked_at.is_(None))) if is_entitlement_active(row)}
        lessons = {row.id: row for row in db.scalars(select(Lesson).where(Lesson.id.in_(required), Lesson.course_id == course.id))}
        allowed = all(lid in lessons and ((EntitlementType.COURSE, course.id) in active
            or (EntitlementType.LESSON, lid) in active
            or (float(course.price_egp or 0) == 0 and float(lessons[lid].price_egp or 0) == 0)) for lid in required)
    else:
        allowed = all(can_access_lesson_content(db, user, lid) for lid in required)
    if not allowed:
        raise HTTPException(403, "Lesson not unlocked")
    # Question sheets are content, not results: a future assignment is sealed
    # even for reads. Legacy assignments without starts_at remain accessible.
    if not results and not assessment_started(assessment):
        raise HTTPException(403, "Assessment is not open yet")
    if writing:
        now = datetime.now(timezone.utc)
        start = assessment.starts_at
        end = assessment.ends_at if isinstance(assessment, Quiz) else assessment.due_at
        if start and as_utc(start) > now:
            raise HTTPException(403, "Assessment is not open yet")
        if end and as_utc(end) <= now:
            raise HTTPException(403, "Assessment is closed")
