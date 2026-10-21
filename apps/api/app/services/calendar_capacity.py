"""Calendar-only capacity, in Cairo civil days and teacher/grade scope."""
import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.models.course import Course
from app.models.platform import CalendarEvent
from app.models.user import User

CAIRO = ZoneInfo('Africa/Cairo')
GRADES = ('1st_secondary', '2nd_secondary', '3rd_secondary')


def calendar_grade(description, course_grade=None):
    course_grade = dict(zip(('SECONDARY_1', 'SECONDARY_2', 'SECONDARY_3'), GRADES)).get(course_grade, course_grade)
    if course_grade in GRADES:
        return course_grade
    try:
        metadata = json.loads(description or '{}')
    except (ValueError, TypeError):
        metadata = {}
    if isinstance(metadata, dict) and metadata.get('academicYear') in (*GRADES, 'all'):
        return metadata['academicYear']
    for grade, label in zip(GRADES, ('الأول الثانوي', 'الثاني الثانوي', 'الثالث الثانوي')):
        if grade in (description or '') or label in (description or ''):
            return grade
    return '1st_secondary'


def require_calendar_capacity(db, *, institution_id, creator_id, course_id,
                              starts_at, description=None, exclude_id=None,
                              check_time_conflict=False, confirm_time_conflict=False):
    # One creator lock serializes count+write across instances and all calendar writers.
    db.execute(select(User.id).where(User.id == creator_id,
        User.institution_id == institution_id).with_for_update())
    course_grade = db.scalar(select(Course.grade_level).where(
        Course.id == course_id, Course.institution_id == institution_id)) if course_id else None
    grade = calendar_grade(description, course_grade)
    instant = starts_at.replace(tzinfo=timezone.utc) if starts_at.tzinfo is None else starts_at
    day = instant.astimezone(CAIRO).date()
    # Convert each midnight separately: Cairo DST days need not last24hours.
    begin = datetime.combine(day, time.min, CAIRO).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, CAIRO).astimezone(timezone.utc)
    query = select(CalendarEvent, Course.grade_level).outerjoin(Course, Course.id == CalendarEvent.course_id).where(
        CalendarEvent.institution_id == institution_id, CalendarEvent.creator_id == creator_id,
        CalendarEvent.cancelled_at.is_(None), CalendarEvent.starts_at >= begin, CalendarEvent.starts_at < end)
    if exclude_id is not None:
        query = query.where(CalendarEvent.id != exclude_id)
    counts = dict.fromkeys(GRADES, 0)
    same_time = False
    for event, linked_grade in db.execute(query):
        existing_grade = calendar_grade(event.description, linked_grade)
        if check_time_conflict and (grade == 'all' or existing_grade in (grade, 'all')):
            existing_time = event.starts_at.replace(tzinfo=timezone.utc) if event.starts_at.tzinfo is None else event.starts_at
            same_time |= existing_time.astimezone(CAIRO).strftime('%H:%M') == instant.astimezone(CAIRO).strftime('%H:%M')
        for candidate in GRADES:
            if existing_grade in (candidate, 'all'):
                counts[candidate] += 1
    if any(counts[candidate] >= 4 for candidate in (GRADES if grade == 'all' else (grade,))):
        raise HTTPException(409, 'لا يمكن إضافة موعد خامس لنفس المدرس والصف في هذا اليوم بتوقيت القاهرة. المواعيد الأربعة محفوظة؛ عدّل موعدًا أو اختر يومًا آخر.')
    if check_time_conflict and same_time and not confirm_time_conflict:
        raise HTTPException(409, {'code': 'CALENDAR_TIME_CONFLICT',
            'message': 'يوجد موعد آخر لنفس المدرس والصف في نفس اليوم ونفس وقت البداية بتوقيت القاهرة. هل تريد حفظ الموعد رغم التعارض؟'})
