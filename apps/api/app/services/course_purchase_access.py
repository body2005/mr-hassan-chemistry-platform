"""Purchase-scoped course metadata admission, independent of browser flags."""
import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.course import Course, CourseStatus, Enrollment, EnrollmentStatus, Lesson
from app.models.payment import EntitlementType, StudentEntitlement
from app.models.user import User, UserRole
from app.services.payment_service import is_entitlement_active


def require_purchased_course_access(db: Session, user: User, course: Course | None) -> set[uuid.UUID] | None:
    """Return purchased lesson IDs; None is an authorized whole-course scope."""
    if course is None or (user.role != UserRole.PLATFORM_ADMIN
                         and course.institution_id != user.institution_id):
        raise HTTPException(404, 'Course not found')
    if user.role in {UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN}:
        return None
    if user.role == UserRole.TEACHER:
        if course.teacher_id == user.id:
            return None
        raise HTTPException(404, 'Course not found')
    if user.role != UserRole.STUDENT or course.status != CourseStatus.PUBLISHED:
        raise HTTPException(404, 'Course not found')
    enrolled = db.scalar(select(Enrollment.id).where(
        Enrollment.course_id == course.id, Enrollment.student_id == user.id,
        Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
    ))
    if enrolled is None:
        raise HTTPException(403, 'An active lesson purchase is required')
    # Approval creates entitlements on the server. Pending orders, free
    # enrollment, and purchases in another course never satisfy this gate.
    rows = db.scalars(select(StudentEntitlement).where(
        StudentEntitlement.student_id == user.id,
        StudentEntitlement.institution_id == course.institution_id,
        StudentEntitlement.revoked_at.is_(None),
        or_(
            (StudentEntitlement.entitlement_type == EntitlementType.COURSE)
            & (StudentEntitlement.resource_id == course.id),
            (StudentEntitlement.entitlement_type == EntitlementType.LESSON)
            & StudentEntitlement.resource_id.in_(select(Lesson.id).where(Lesson.course_id == course.id)),
        ),
    ))
    purchased = set()
    for row in rows:
        if not is_entitlement_active(row):
            continue
        if row.entitlement_type == EntitlementType.COURSE:
            return None
        purchased.add(row.resource_id)
    if not purchased:
        raise HTTPException(403, 'An active lesson purchase is required')
    return purchased
