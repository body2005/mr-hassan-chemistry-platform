"""One durable lesson notice per student, sent immediately or when ready and due."""
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs

from sqlalchemy import or_, select
from app.core.database import SessionLocal
from app.core.events import event_broker
from app.models.course import Course, CourseStatus, Enrollment, EnrollmentStatus, Lesson
from app.models.platform import Assignment, Quiz, CalendarEvent, DeliveryStatus, Notification
from app.models.user import User, UserRole
from app.services.lesson_release import available_lesson_ids
from app.services.payment_service import accessible_course_lesson_ids, has_course_entitlement, has_lesson_entitlement
from app.services.content_access import as_utc

logger = logging.getLogger(__name__)


def sync_lesson_calendar(db, lesson, course):
    """One course-scoped planning entry, updated without duplicate notices."""
    key = f'lesson-release:{lesson.id}'
    event = db.scalar(select(CalendarEvent).where(CalendarEvent.creator_id == course.teacher_id,
                                                CalendarEvent.request_key == key))
    enabled = lesson.publication_status == 'published'
    if not enabled and not event:
        return
    if enabled and (event is None or event.cancelled_at is None):
        from app.services.calendar_capacity import require_calendar_capacity
        require_calendar_capacity(db, institution_id=course.institution_id, creator_id=course.teacher_id,
            course_id=course.id, starts_at=lesson.publish_at or lesson.created_at or datetime.now(timezone.utc),
            exclude_id=event.id if event else None)
    if not event:
        event = CalendarEvent(institution_id=course.institution_id, creator_id=course.teacher_id,
                              course_id=course.id, request_key=key, event_type='lesson')
        db.add(event)
    event.title = lesson.title
    event.description = 'موعد إتاحة الدرس'
    event.starts_at = lesson.publish_at or lesson.created_at or datetime.now(timezone.utc)
    event.ends_at = lesson.available_until
    event.is_published = bool(enabled)


def _announcement_access(db, user, lesson, course, *, enrolled):
    """Planning notices can precede release, but never bypass enrollment or payment."""
    return bool(enrolled and user.role == UserRole.STUDENT and user.is_active and not user.deleted_at
        and course.institution_id == user.institution_id and course.status == CourseStatus.PUBLISHED
        and lesson.publication_status == 'published'
        and (not lesson.available_until or as_utc(lesson.available_until) > datetime.now(timezone.utc))
        and ((float(course.price_egp or 0) == 0 and float(lesson.price_egp or 0) == 0)
             or has_course_entitlement(db, user, course.id) or has_lesson_entitlement(db, user, lesson.id)))


def _enrolled_students(db, course):
    return list(db.scalars(select(User).join(Enrollment, Enrollment.student_id == User.id).where(
        Enrollment.course_id == course.id, Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        User.role == UserRole.STUDENT, User.institution_id == course.institution_id,
        User.is_active.is_(True), User.deleted_at.is_(None))))


def _notified_students(db, lesson, course):
    return set(db.scalars(select(Notification.recipient_id).where(
        Notification.institution_id == course.institution_id,
        Notification.dedup_key == f'lesson-published:{lesson.id}')))


def announce_lesson_immediately(db, lesson, course):
    # The legacy wire field now selects timing: True = now, False = at release.
    # Share the lesson row lock with the release worker to serialize dedup checks.
    if not lesson.announce_to_students:
        return set()
    db.execute(select(Lesson.id).where(Lesson.id == lesson.id).with_for_update())
    notified = _notified_students(db, lesson, course)
    now = datetime.now(timezone.utc)
    recipients = set()
    for student in _enrolled_students(db, course):
        if student.id in notified or not _announcement_access(db, student, lesson, course, enrolled=True):
            continue
        db.add(Notification(institution_id=course.institution_id, recipient_id=student.id,
            kind='lesson_announcement', title='تمت إضافة درس جديد',
            message=f'{lesson.title} — يُفتح الدرس عند موعد الإتاحة وبعد اكتمال الرفع.',
            action_url=f'#mycourses?course={course.id}&announcement={lesson.id}',
            dedup_key=f'lesson-published:{lesson.id}', scheduled_for=now,
            delivered_at=now, delivery_status=DeliveryStatus.DELIVERED))
        recipients.add(student.id)
    return recipients


def publish_lesson_notice_hint(course, recipients):
    if recipients:
        try:
            event_broker.publish_event(course.institution_id, 'notification_created', {}, target_user_ids=recipients)
        except Exception:
            logger.warning('Lesson notification hint deferred; database notice retained')


def visible_lesson_notifications(db, user, notifications):
    """Withdraw a lesson notice if content is withdrawn or access is revoked."""
    now = datetime.now(timezone.utc)
    notifications = [item for item in notifications if not item.scheduled_for or
        (item.scheduled_for.replace(tzinfo=timezone.utc) if item.scheduled_for.tzinfo is None
         else item.scheduled_for) <= now]
    from app.services.content_access import filter_student_assessments
    assessment_links = {}
    for item in notifications:
        query = parse_qs(urlsplit(item.action_url or '').fragment.partition('?')[2])
        raw, kind = query.get('assessment', [None])[0], query.get('kind', [None])[0]
        if raw:
            try:
                assessment_links[item.id] = (kind, uuid.UUID(raw))
            except ValueError:
                assessment_links[item.id] = (kind, None)
    visible = set()
    for kind, model in (('quiz', Quiz), ('assignment', Assignment)):
        ids = [value for k, value in assessment_links.values() if k == kind and value]
        rows = list(db.scalars(select(model).where(model.id.in_(ids), model.institution_id == user.institution_id)))
        visible.update((kind, row.id) for row in filter_student_assessments(db, user, rows))
    notifications = [item for item in notifications if item.id not in assessment_links or assessment_links[item.id] in visible]
    links = {}
    planning = set()
    for item in notifications:
        query = parse_qs(urlsplit(item.action_url or '').fragment.partition('?')[2])
        raw = query.get('lesson', [None])[0]
        if item.kind == 'lesson_announcement':
            raw = query.get('announcement', [None])[0]
            planning.add(item.id)
            links[item.id] = None  # Malformed planning notices fail closed.
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
    announced = set()
    for course in courses:
        accessible.update(accessible_course_lesson_ids(db, user, course,
            [lesson for lesson in lessons if lesson.course_id == course.id], enrolled=course.id in enrolled))
        announced.update(lesson.id for lesson in lessons if lesson.course_id == course.id
            and _announcement_access(db, user, lesson, course, enrolled=course.id in enrolled))
    return [item for item in notifications if item.id not in links
            or links[item.id] in (announced if item.id in planning else accessible)]


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
            students = _enrolled_students(db, course)
            notified = _notified_students(db, lesson, course)
            recipients = {course.teacher_id}
            for student in students:
                if lesson.id not in accessible_course_lesson_ids(db, student, course, [lesson], enrolled=True):
                    continue
                recipients.add(student.id)
                if student.id in notified:
                    continue
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
