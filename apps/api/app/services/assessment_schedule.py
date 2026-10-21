"""Keep generated, explicitly linked calendar/notice records on one schedule."""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.models.platform import Quiz, CalendarEvent, Notification, DeliveryStatus
from app.services.content_access import as_utc


def sync_assessment_schedule(db, assessment):
    kind = 'quiz' if isinstance(assessment, Quiz) else 'assignment'
    end = assessment.ends_at if kind == 'quiz' else assessment.due_at
    published = assessment.status == 'published'
    now = datetime.now(timezone.utc)
    key = f'evt_assessment_{kind}_{assessment.id}'
    for event in db.scalars(select(CalendarEvent).where(
            CalendarEvent.institution_id == assessment.institution_id,
            CalendarEvent.course_id == assessment.course_id, CalendarEvent.request_key == key)):
        if published:
            from app.services.calendar_capacity import require_calendar_capacity
            require_calendar_capacity(db, institution_id=event.institution_id, creator_id=event.creator_id,
                course_id=event.course_id, starts_at=as_utc(assessment.starts_at) or now,
                description=event.description, exclude_id=event.id)
        event.starts_at = as_utc(assessment.starts_at) or now
        event.ends_at = as_utc(end)
        event.cancelled_at = None if published else now
        # Description contains display-only dates from the original form.
        # The authoritative fields drive subsequent display/editing.
        try:
            metadata = json.loads(event.description or '{}')
        except (ValueError, TypeError):
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        local = event.starts_at.astimezone(ZoneInfo('Africa/Cairo'))
        metadata.update(publishStartDate=local.strftime('%Y-%m-%d'), publishStartTime=local.strftime('%H:%M'))
        close = as_utc(end).astimezone(ZoneInfo('Africa/Cairo')) if end else None
        metadata.update(closeDeadlineDate=close.strftime('%Y-%m-%d') if close else '',
                        closeDeadlineTime=close.strftime('%H:%M') if close else '')
        event.description = json.dumps(metadata, ensure_ascii=False)
    prefix = f'#MyCourses?assessment={assessment.id}&kind={kind}'
    for notice in db.scalars(select(Notification).where(
            Notification.institution_id == assessment.institution_id,
            Notification.action_url.startswith(prefix))):
        # Delivered notices are history. Editing/re-publishing an assessment
        # must not re-arm them or announce the same message a second time.
        if notice.delivered_at is not None:
            continue
        notice.scheduled_for = as_utc(assessment.starts_at)
        notice.delivery_status = DeliveryStatus.PENDING if published else DeliveryStatus.FAILED
        notice.delivered_at = None
        label = 'اختبار' if kind == 'quiz' else 'واجب'
        deadline = as_utc(end).astimezone(ZoneInfo('Africa/Cairo')).strftime('%Y-%m-%d %H:%M') if end else 'بدون موعد إغلاق'
        notice.message = f'{label} «{assessment.title}». آخر موعد بتوقيت القاهرة: {deadline}.'
