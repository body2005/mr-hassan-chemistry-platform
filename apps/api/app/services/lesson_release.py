"""Publication policy shared by catalog and every student content entry point."""
from datetime import datetime, timezone
from sqlalchemy import select, func
from app.models.course import CourseStatus, LessonKind
from app.models.extended import LessonAsset
from app.models.video_upload import VideoUpload

def available_lesson_ids(db, lessons, courses):
    if not lessons:
        return set()
    ids = [lesson.id for lesson in lessons]
    latest = {}
    for row in db.scalars(select(VideoUpload).where(VideoUpload.lesson_id.in_(ids)).order_by(VideoUpload.created_at.desc(), VideoUpload.id.desc())):
        latest.setdefault(row.lesson_id, row)
    materials = dict(db.execute(select(LessonAsset.lesson_id, func.count(LessonAsset.id)).where(
        LessonAsset.lesson_id.in_(ids), LessonAsset.object_key.is_not(None),
        LessonAsset.asset_kind.in_(["pdf", "document", "attachment"])).group_by(LessonAsset.lesson_id)).all())
    now = datetime.now(timezone.utc)
    result = set()
    for lesson in lessons:
        course = courses.get(lesson.course_id)
        if not course or course.status != CourseStatus.PUBLISHED or lesson.publication_status != "published":
            continue
        due = lesson.publish_at
        if due and (due.replace(tzinfo=timezone.utc) if due.tzinfo is None else due) > now:
            continue
        job = latest.get(lesson.id)
        if job and job.status != "ready":
            continue
        key = lesson.video_asset_key or ""
        if lesson.kind == LessonKind.VIDEO or key:
            if not key or key.startswith(("http://", "https://")):
                continue
            if job and not key.endswith(".m3u8"):
                continue
        elif not lesson.content and not materials.get(lesson.id):
            continue
        if materials.get(lesson.id, 0) < lesson.required_material_count:
            continue
        result.add(lesson.id)
    return result

def lesson_is_available(db, lesson, course):
    return lesson.id in available_lesson_ids(db, [lesson], {course.id: course})
