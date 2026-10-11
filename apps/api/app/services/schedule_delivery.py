"""Schedule hints; request-time policy remains authoritative."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_, select, union_all
from app.core.database import SessionLocal
from app.core.events import event_broker
from app.core.rate_limit import _get_redis_client
from app.models.platform import Assignment, Quiz, Notification, DeliveryStatus
from app.services.assessment_events import assessment_changed


def deliver_due_notifications():
    now = datetime.now(timezone.utc)
    delivered = []
    with SessionLocal() as db:
        rows = db.scalars(select(Notification).where(Notification.delivery_status == DeliveryStatus.PENDING,
            or_(Notification.scheduled_for.is_(None), Notification.scheduled_for <= now))
            .order_by(Notification.scheduled_for.asc().nullsfirst(), Notification.id)
            .with_for_update(skip_locked=True).limit(100)).all()
        for row in rows:
            row.delivery_status = DeliveryStatus.DELIVERED
            row.delivered_at = now
            delivered.append((row.institution_id, row.recipient_id))
        db.commit()
    for institution_id, recipient_id in set(delivered):
        event_broker.publish_event(institution_id, "notification_created", {}, target_user_ids=[recipient_id])


def announce_assessment_boundaries():
    now = datetime.now(timezone.utc)
    since = now - timedelta(seconds=75)
    redis = _get_redis_client()
    if redis is None:
        return
    with SessionLocal() as db:
        from types import SimpleNamespace
        for model, end_column in ((Quiz, Quiz.ends_at), (Assignment, Assignment.due_at)):
            # One hint per course/boundary, streamed in batches. A LIMIT on the
            # first 100 assessments would repeatedly select already-deduped
            # rows and silently starve the remaining courses.
            boundaries = union_all(
                select(model.course_id.label("course_id"), model.starts_at.label("boundary")).where(
                    model.status == "published", model.starts_at > since, model.starts_at <= now),
                select(model.course_id.label("course_id"), end_column.label("boundary")).where(
                    model.status == "published", end_column > since, end_column <= now),
            ).subquery()
            rows = db.execute(select(boundaries.c.course_id, func.max(boundaries.c.boundary))
                .group_by(boundaries.c.course_id).execution_options(yield_per=100))
            for course_id, boundary in rows:
                if redis.set(f"schedule-hint:{model.__tablename__}:{course_id}:{boundary.isoformat()}",
                             "1", nx=True, ex=180):
                    assessment_changed(db, SimpleNamespace(course_id=course_id))
