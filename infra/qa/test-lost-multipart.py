"""Reproduce lost MPU on real PostgreSQL/S3 with a NEW synthetic teacher only."""
import json
import os
import subprocess
import uuid
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.video_upload import VideoUpload
from scripts.s3_snapshot import client
from tests.integration.live_helpers import BASE, isolated, lesson, session

isolated()
# Capture the generated credentials internally; never print them in QA output.
seed = subprocess.run(["python", "-m", "scripts.seed_qa_teacher"], capture_output=True,
                      check=True, text=True, timeout=30)
identity = json.loads(seed.stdout.strip())
with session(identity["email"], identity["password"]) as teacher:
    _, item = lesson(teacher, "video")
    data = {"filename": "lost.webm", "content_type": "video/webm", "size_bytes": 100,
            "fingerprint": "a" * 64, "request_key": uuid.uuid4().hex}
    created = teacher.post(f"{BASE}/lessons/{item['id']}/video-uploads", json=data, timeout=15)
    assert created.status_code == 201
    upload_id = uuid.UUID(created.json()["id"])
    with SessionLocal() as db:
        job = db.scalar(select(VideoUpload).where(VideoUpload.id == upload_id))
        # Only the exact newly created test session is deliberately removed.
        store = client()
        store.abort_multipart_upload(Bucket=os.environ["S3_BUCKET"], Key=job.object_key, UploadId=job.multipart_id)
    status = teacher.get(f"{BASE}/video-uploads/{upload_id}", timeout=15)
    assert status.status_code == 200
    assert status.json()["status"] == "expired"
    assert status.json()["error_code"] == "VIDEO_UPLOAD_STORAGE_SESSION_LOST"
    assert teacher.post(f"{BASE}/video-uploads/{upload_id}/complete", timeout=15).status_code == 409
    data["request_key"] = uuid.uuid4().hex
    restarted = teacher.post(f"{BASE}/lessons/{item['id']}/video-uploads", json=data, timeout=15)
    assert restarted.status_code == 201 and restarted.json()["id"] != str(upload_id)
    assert teacher.delete(f"{BASE}/video-uploads/{restarted.json()['id']}", timeout=15).status_code == 204
print(json.dumps({"missing_mpu_status": 200, "state": "expired", "completion": 409,
                  "new_intent": 201, "test_session_cleanup": 204, "server_500": 0}))
