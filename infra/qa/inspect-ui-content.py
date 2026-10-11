"""Read-only, synthetic local QA diagnostics; never print keys/tokens/payloads."""
import json
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.course import Lesson, CourseModule, Course
from app.models.video_upload import VideoUpload
from tests.integration.live_helpers import isolated

isolated()
with SessionLocal() as db:
    lessons = db.execute(select(Lesson, Course).join(CourseModule, Lesson.module_id == CourseModule.id)
        .join(Course, CourseModule.course_id == Course.id)
        .where(Lesson.title.contains("بيولوجيا"))).all()
    for lesson, course in lessons:
        jobs = list(db.scalars(select(VideoUpload).where(VideoUpload.lesson_id == lesson.id)))
        print(json.dumps({"lesson_id": str(lesson.id), "title": lesson.title,
            "kind": lesson.kind, "has_asset": bool(lesson.video_asset_key),
            "asset_kind": "hls" if (lesson.video_asset_key or "").endswith("master.m3u8") else "other" if lesson.video_asset_key else "none",
            "course_published": str(course.status),
            "upload_jobs": [{"status": j.status, "error_code": j.error_code,
                             "bytes": j.size_bytes, "attempts": j.attempts} for j in jobs]}, ensure_ascii=False))
