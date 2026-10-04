"""Actual HTTPS HLS/Range/privacy checks against a restored DB and object store."""
import json
from urllib.parse import urljoin
import requests
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.course import Lesson, CourseModule, Course
from app.models.user import User
from app.models.video_upload import VideoUpload
from tests.integration.live_helpers import BASE, clear_auth, session

clear_auth()
with SessionLocal() as db:
    ready = db.scalar(select(VideoUpload).join(User, User.id == VideoUpload.owner_id)
        .join(Lesson, Lesson.id == VideoUpload.lesson_id).join(CourseModule, CourseModule.id == Lesson.module_id)
        .join(Course, Course.id == CourseModule.course_id)
        .where(VideoUpload.status == "ready", User.email == "teacher@demo.com", Lesson.price_egp == 0,
               Course.status == "published").order_by(VideoUpload.created_at.desc()).limit(1))
    if ready is None:
        raise SystemExit("Run the protected HLS browser test before this drill")
    lesson_id = str(ready.lesson_id)
with session("student03@demo.com", "qa-student-pass") as student:
    issued = student.post(f"{BASE}/lessons/{lesson_id}/video-token", timeout=15)
    assert issued.status_code == 200 and issued.json()["format"] == "hls"
    url = urljoin(BASE.removesuffix("/api/v1") + "/", issued.json()["stream_url"])
    master = student.get(url, timeout=15)
    assert master.status_code == 200
    child = next(line for line in master.text.splitlines() if line and not line.startswith("#"))
    playlist = student.get(urljoin(url, child), timeout=15)
    assert playlist.status_code == 200
    segment = next(line for line in playlist.text.splitlines() if line and not line.startswith("#"))
    segment_url = urljoin(url, segment)
    response = student.get(segment_url, headers={"Range": "bytes=0-99"}, timeout=15)
    assert response.status_code == 206 and len(response.content) == 100
    assert requests.get(segment_url, verify=student.verify, timeout=15).status_code == 403
    student.close()
    assert requests.get(url, verify=student.verify, timeout=15).status_code == 403
print(json.dumps({"restored_hls": True, "range_status": 206, "range_bytes": 100,
                  "anonymous_segment": 403, "revoked_manifest": 403}))
