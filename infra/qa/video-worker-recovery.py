"""Synthetic QA: stopped encoder / hard crash during processing / durable retry.

Run serially, never beside browser/load/restore or other fault tests. No secrets,
signed URLs, or unredacted exception response bodies are printed.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from urllib.parse import urljoin

from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.course import Lesson
from app.models.video_upload import VideoUpload
from scripts.s3_snapshot import client
from tests.integration.live_helpers import BASE, clear_auth, container, isolated, lesson, session


def wait_state(teacher, identity, state, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = teacher.get(f"{BASE}/video-uploads/{identity}", timeout=15)
        # Only known generic dependency messages may appear in diagnostics;
        # never include arbitrary response bodies, credentials or signed URLs.
        known = {"Admission service temporarily unavailable", "Concurrent resource limit reached",
                 "Rate limiting is temporarily unavailable.", "A required service is temporarily unavailable"}
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        assert response.status_code == 200, (
            f"Control request returned {response.status_code}; "
            f"Retry-After={response.headers.get('Retry-After')}; "
            f"dependency={detail if isinstance(detail, str) and detail in known else 'not identified'}")
        value = response.json()["status"]
        if value == state:
            return
        assert value not in {"failed", "cancelled", "expired"}, value
        time.sleep(0.5 if state == "processing" else 3)
    raise AssertionError(f"Expected {state} before the bounded deadline")


def stage(teacher, item, media):
    created = teacher.post(f"{BASE}/lessons/{item['id']}/video-uploads", json={
        "filename": "recovery.webm", "content_type": "video/webm",
        "size_bytes": media.stat().st_size, "fingerprint": "b" * 64,
        "request_key": uuid.uuid4().hex}, timeout=15)
    assert created.status_code == 201
    identity = uuid.UUID(created.json()["id"])
    with SessionLocal() as db:
        job = db.get(VideoUpload, identity)
        key, allocation = job.object_key, job.multipart_id
    store = client()
    with media.open("rb") as source:
        number = 1
        while part := source.read(created.json()["part_bytes"]):
            store.upload_part(Bucket=os.environ["S3_BUCKET"], Key=key,
                              UploadId=allocation, PartNumber=number, Body=part)
            number += 1
    assert teacher.post(f"{BASE}/video-uploads/{identity}/complete", timeout=15).status_code == 202
    return identity


def wait_encoding(encoder, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # Docker needs a PID column to map host processes into the container.
        # Requesting only comm makes the daemon fail before any observation.
        listing = encoder.top(ps_args="-eo pid,comm")
        command_column = listing["Titles"].index("COMMAND")
        if any(row[command_column] == "ffmpeg" for row in listing["Processes"]):
            return
        time.sleep(0.2)
    raise AssertionError("No real FFmpeg process observed before crash")


def protected_segment(student, item):
    issued = student.post(f"{BASE}/lessons/{item['id']}/video-token", timeout=15)
    assert issued.status_code == 200 and issued.json()["format"] == "hls"
    origin = BASE.removesuffix("/api/v1") + "/"
    master_url = urljoin(origin, issued.json()["stream_url"])
    master = student.get(master_url, timeout=15)
    assert master.status_code == 200
    child = next(line for line in master.text.splitlines() if line and not line.startswith("#"))
    playlist = student.get(urljoin(origin, child), timeout=15)
    assert playlist.status_code == 200
    segment = next(line for line in playlist.text.splitlines() if line and not line.startswith("#"))
    response = student.get(urljoin(origin, segment), headers={"Range": "bytes=0-99"}, timeout=15)
    assert response.status_code == 206 and len(response.content) == 100


def main():
    isolated()
    clear_auth()
    identity = json.loads(subprocess.run(["python", "-m", "scripts.seed_qa_teacher"],
        capture_output=True, text=True, check=True, timeout=30).stdout.strip())
    encoder = container("video-worker")
    encoder.reload()
    assert encoder.status == "running", "Start the isolated video worker first"
    media = Path(os.environ["QA_MEDIA_DIR"]) / "video.webm"
    interrupted = False
    try:
        with session(identity["email"], identity["password"]) as teacher:
            course, item = lesson(teacher, "video")
            original = stage(teacher, item, media)
            wait_state(teacher, original, "ready")
            with session("student04@demo.com", "qa-student-pass") as student:
                assert student.post(f"{BASE}/courses/{course['id']}/enroll", timeout=15).status_code == 200
                protected_segment(student, item)
                # Stop only the allowlisted encoder. New work remains queued;
                # the student's previously ready generation stays playable.
                interrupted = True
                encoder.stop(timeout=0)
                replacement = stage(teacher, item, media)
                wait_state(teacher, replacement, "queued", timeout=15)
                protected_segment(student, item)
                encoder.start()
                wait_state(teacher, replacement, "processing", timeout=45)
                wait_encoding(encoder)
                # A forced stop kills FFmpeg too, releases the PG advisory lock,
                # and does not let restart-policy race the explicit restart.
                encoder.stop(timeout=0)
                with SessionLocal() as db:
                    job = db.get(VideoUpload, replacement)
                    assert job.status == "processing" and job.attempts == 1
                    crashed_outputs = list(job.outputs)
                    assert db.get(Lesson, uuid.UUID(item["id"])).video_asset_key.endswith(f"/{db.get(VideoUpload, original).manifest_key}")
                protected_segment(student, item)
                recovered_at = time.monotonic()
                encoder.start()
                wait_state(teacher, replacement, "ready")
                elapsed = round(time.monotonic() - recovered_at, 3)
                protected_segment(student, item)
                with SessionLocal() as db:
                    job = db.get(VideoUpload, replacement)
                    assert job.attempts == 2 and job.error_code is None
                    assert db.get(VideoUpload, original).status == "superseded"
                    assert db.get(Lesson, uuid.UUID(item["id"])).video_asset_key.endswith(f"/{job.manifest_key}")
                    assert len(list(db.scalars(select(VideoUpload).where(VideoUpload.lesson_id == uuid.UUID(item["id"]), VideoUpload.status == "ready")))) == 1
                    assert not set(crashed_outputs).intersection(job.outputs)
                    digest = hashlib.sha256()
                    response = client().get_object(Bucket=os.environ["S3_BUCKET"], Key=job.object_key)
                    try:
                        for chunk in response["Body"].iter_chunks(1024 * 1024):
                            digest.update(chunk)
                    finally:
                        response["Body"].close()
                    assert digest.hexdigest() == job.sha256
                    with media.open("rb") as source:
                        assert hashlib.file_digest(source, "sha256").hexdigest() == job.sha256
                print(json.dumps({"queued_while_encoder_down": True,
                    "old_generation_playable_during_outage_and_crash": True,
                    "range_status": 206, "crash_retry_attempts": 2,
                    "ffmpeg_observed_before_hard_stop": True,
                    "ready_generations": 1, "original_sha256_match": True,
                    "recovery_seconds": elapsed, "fixture_bytes": media.stat().st_size,
                    "fixture_upload": "private S3 fixture, not gateway load"}))
    finally:
        if interrupted:
            encoder.reload()
            if encoder.status != "running":
                encoder.start()


if __name__ == "__main__":
    main()
