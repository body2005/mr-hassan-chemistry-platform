"""Invalidation hints only; clients re-read authorized server state."""
import logging
from sqlalchemy import select
from app.core.events import event_broker
from app.models.course import Course, Enrollment, EnrollmentStatus
from app.models.user import User, UserRole


def assessment_changed(db, assessment, *, student_id=None):
    course = db.get(Course, assessment.course_id)
    if not course:
        return
    recipients = {student_id} if student_id is not None else set(db.scalars(select(Enrollment.student_id).where(
        Enrollment.course_id == course.id,
        Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]))))
    recipients.update(db.scalars(select(User.id).where(User.institution_id == course.institution_id,
        User.role.in_([UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN]))))
    if course.teacher_id:
        recipients.add(course.teacher_id)
    try:
        event_broker.publish_event(course.institution_id, "assessment_updated",
            {"course_id": str(course.id)}, target_user_ids=recipients)
    except Exception:
        logging.getLogger(__name__).warning("Assessment invalidation deferred; durable state retained")
