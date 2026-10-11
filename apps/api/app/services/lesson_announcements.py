"""Durable publication notices: ready and due, with no extra SSE connection."""
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs

from sqlalchemy import or_, select
from app.core.database import SessionLocal
from app.core.events import event_broker
from app.models.course import Course, Enrollment, EnrollmentStatus, Lesson
from app.models.platform import DeliveryStatus, Notification
from app.models.user import User, UserRole
from app.services.lesson_release import available_lesson_ids
from app.services.payment_service import accessible_course_lesson_ids

logger = logging.getLogger(__name__)


def visible_lesson_notifications(db, user, notifications):
    """Withdraw a lesson notice if content is withdrawn or access is revoked."""
    links = {}
    for item in notifications:
        query = parse_qs(urlsplit(item.action_url or '').fragment.partition('?')[2])
        raw = query.get('lesson', [None])[0]
        if raw:
            try:
                links[item.id] = uuid.UUID(raw)
            except ValueError:
                links[item.id] = None
    if not links:
        return notifications
    lessons = list(db.scalars(select(Lesson).where(Lesson.id.in_([value for value in links.values() if value]))))
    courses = list(db.scalars(select(Course).where(Course.id.in_({lesson.course_id for lesson in lessons}))))
    enrolled = set(db.scalars(select(Enrollment.course_id).where(Enrollment.student_id == user.id,
        Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]))))
    accessible = set()
    for course in courses:
        accessible.update(accessible_course_lesson_ids(db, user, course,
            [lesson for lesson in lessons if lesson.course_id == course.id], enrolled=course.id in enrolled))
    return [item for item in notifications if item.id not in links or links[item.id] in accessible]


def announce_available_lessons(batch_size=25):
    now = datetime.now(timezone.utc)
    hints = []
    with SessionLocal() as db:
        candidates = list(db.scalars(select(Lesson).where(Lesson.publication_status == 'published',
            Lesson.release_announced_at.is_(None), or_(Lesson.publish_at.is_(None), Lesson.publish_at <= now))
            .order_by(Lesson.release_checked_at.asc().nullsfirst(), Lesson.id)
            .with_for_update(skip_locked=True).limit(min(batch_size, 25))))
        courses = {course.id: course for course in db.scalars(select(Course).where(Course.id.in_({lesson.course_id for lesson in candidates})))}
        ready = available_lesson_ids(db, candidates, courses)
        for lesson in candidates:
            # Round-robin checks prevent unfinished uploads starving later rows.
            lesson.release_checked_at = now
            if lesson.id not in ready:
                continue
            course = courses[lesson.course_id]
            students = list(db.scalars(select(User).join(Enrollment, Enrollment.student_id == User.id).where(
                Enrollment.course_id == course.id, Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
                User.role == UserRole.STUDENT, User.institution_id == course.institution_id,
                User.is_active.is_(True), User.deleted_at.is_(None))))
            recipients = {course.teacher_id}
            for student in students:
                if lesson.id not in accessible_course_lesson_ids(db, student, course, [lesson], enrolled=True):
                    continue
                recipients.add(student.id)
                db.add(Notification(institution_id=course.institution_id, recipient_id=student.id,
                    kind='lesson', title='درس جديد متاح', message=lesson.title,
                    action_url=f'#mycourses?course={course.id}&lesson={lesson.id}',
                    dedup_key=f'lesson-published:{lesson.id}', scheduled_for=now,
                    delivered_at=now, delivery_status=DeliveryStatus.DELIVERED))
            lesson.release_announced_at = now
            hints.append((course.institution_id, lesson.id, course.id, recipients))
        db.commit()
    for institution_id, lesson_id, course_id, recipients in hints:
        try:
            event_broker.publish_event(institution_id, 'lesson_published',
                {'lesson_id': str(lesson_id), 'course_id': str(course_id)}, target_user_ids=recipients)
        except Exception:
            # Saved notices survive a broker outage and are fetched on reconnect.
            logger.warning('Lesson publication hint deferred; database notice retained')
