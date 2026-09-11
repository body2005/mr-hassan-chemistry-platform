from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
import uuid
from datetime import datetime, timezone, timedelta
UTC = timezone.utc

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.main import app
from app.models import Base
from app.models.course import Course, CourseModule, IndexingStatus, Lesson
from app.models.institution import Institution
from app.models.transcript import (
    KnowledgeChunk,
    Transcript,
    TranscriptSegment,
    TranscriptionJob,
    TranscriptionJobStatus,
    TranscriptionStatus,
)
from app.models.user import User, UserRole
import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parents[3])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.services.transcription_job_manager import (
    TranscriptionJobManager,
    hash_token,
)
from kaggle_worker.kaggle_qwencleo_worker import deduplicate_overlap_words

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        inst = db.query(Institution).filter(Institution.slug == "test-inst").first()
        if not inst:
            inst = Institution(id=uuid.uuid4(), name="Test Institution", slug="test-inst")
            db.add(inst)
            db.commit()
            db.refresh(inst)

        teacher = db.query(User).filter(User.email == "test.teacher@test.com").first()
        if not teacher:
            teacher = User(
                id=uuid.uuid4(),
                institution_id=inst.id,
                email="test.teacher@test.com",
                username="testteacher",
                display_name="Test Teacher",
                password_hash="argon2_fake_hash",
                role=UserRole.TEACHER,
            )
            db.add(teacher)
            db.commit()
            db.refresh(teacher)

        course = db.query(Course).filter(Course.code == "TEST-ASR-101").first()
        if not course:
            course = Course(
                id=uuid.uuid4(),
                institution_id=inst.id,
                teacher_id=teacher.id,
                title="ASR Test Course",
                code="TEST-ASR-101",
            )
            db.add(course)
            db.commit()
            db.refresh(course)

        module = db.query(CourseModule).filter(CourseModule.course_id == course.id).first()
        if not module:
            module = CourseModule(
                id=uuid.uuid4(),
                course_id=course.id,
                title="Module 1",
                position=1,
            )
            db.add(module)
            db.commit()
            db.refresh(module)

        lesson = db.query(Lesson).filter(Lesson.title == "ASR Test Lesson").first()
        if not lesson:
            lesson = Lesson(
                id=uuid.uuid4(),
                module_id=module.id,
                title="ASR Test Lesson",
                kind="video",
                position=1,
            )
            db.add(lesson)
            db.commit()
            db.refresh(lesson)

        yield {
            "db": db,
            "institution": inst,
            "teacher": teacher,
            "course": course,
            "module": module,
            "lesson": lesson,
        }
    finally:
        db.close()


def test_job_creation_and_token_generation(setup_db):
    db: Session = setup_db["db"]
    lesson: Lesson = setup_db["lesson"]
    course: Course = setup_db["course"]

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"fake_video_content_data_stream_12345")
        fake_path = f.name

    try:
        job, raw_token, raw_secret = TranscriptionJobManager.create_job(
            db=db,
            lesson_id=lesson.id,
            course_id=course.id,
            video_id="fake_video_id.mp4",
            storage_path=fake_path,
        )

        assert job.id is not None
        assert job.status == TranscriptionJobStatus.QUEUED
        assert job.signed_download_token_hash == hash_token(raw_token)
        assert job.callback_secret_hash == raw_secret
        exp_time = job.signed_token_expires_at if job.signed_token_expires_at.tzinfo else job.signed_token_expires_at.replace(tzinfo=UTC)
        assert exp_time > datetime.now(UTC)
    finally:
        if os.path.exists(fake_path):
            os.remove(fake_path)


def test_signed_download_url_validation(setup_db):
    db: Session = setup_db["db"]
    lesson: Lesson = setup_db["lesson"]
    course: Course = setup_db["course"]

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"video_binary_payload_xyz")
        fake_path = f.name

    try:
        job, raw_token, _ = TranscriptionJobManager.create_job(
            db=db,
            lesson_id=lesson.id,
            course_id=course.id,
            video_id="test_media.mp4",
            storage_path=fake_path,
        )

        # 1. Valid token
        resp = client.get(f"/api/v1/transcription/download/{raw_token}")
        assert resp.status_code == 200
        assert resp.content == b"video_binary_payload_xyz"

        # 2. Invalid token
        resp_invalid = client.get("/api/v1/transcription/download/tampered_token_999")
        assert resp_invalid.status_code == 404

        # 3. Expired token
        job.signed_token_expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
        resp_expired = client.get(f"/api/v1/transcription/download/{raw_token}")
        assert resp_expired.status_code == 404
    finally:
        if os.path.exists(fake_path):
            os.remove(fake_path)


def test_authenticated_callback_and_idempotency(setup_db):
    db: Session = setup_db["db"]
    lesson: Lesson = setup_db["lesson"]
    course: Course = setup_db["course"]

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"sample_lecture_audio")
        fake_path = f.name

    try:
        job, _, raw_secret = TranscriptionJobManager.create_job(
            db=db,
            lesson_id=lesson.id,
            course_id=course.id,
            video_id="lecture_01.mp4",
            storage_path=fake_path,
        )

        payload = {
            "status": "completed",
            "job_id": str(job.id),
            "video_id": "lecture_01.mp4",
            "lesson_id": str(lesson.id),
            "course_id": str(course.id),
            "duration": 120.0,
            "full_text": "مرحباً بكم في شرح الجيولوجيا والفوالق العادية والمعكوسة.",
            "segments": [
                {"sequence": 1, "start_time": 0.0, "end_time": 60.0, "text": "مرحباً بكم في شرح الجيولوجيا."},
                {"sequence": 2, "start_time": 60.0, "end_time": 120.0, "text": "الفوالق العادية والمعكوسة."},
            ],
        }
        body_bytes = json.dumps(payload).encode("utf-8")

        # 1. Invalid signature rejection
        bad_resp = client.post(
            f"/api/v1/transcription/jobs/{job.id}/callback",
            content=body_bytes,
            headers={"X-Callback-Auth": "wrong_secret_123"},
        )
        assert bad_resp.status_code == 401

        # 2. Valid signature success
        sig = hmac.new(raw_secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        good_resp = client.post(
            f"/api/v1/transcription/jobs/{job.id}/callback",
            content=body_bytes,
            headers={"X-Signature-SHA256": sig, "Content-Type": "application/json"},
        )
        assert good_resp.status_code == 200
        res_json = good_resp.json()
        assert res_json["status"] == "success"
        assert res_json["segments_count"] == 2

        # Verify DB persistence
        db.expire_all()
        transcript = db.query(Transcript).filter(Transcript.lesson_id == lesson.id).first()
        assert transcript is not None
        assert transcript.status == TranscriptionStatus.COMPLETED
        segments = db.query(TranscriptSegment).filter(TranscriptSegment.transcript_id == transcript.id).all()
        assert len(segments) == 2

        # 3. Idempotency Check: Repeat identical callback
        dup_resp = client.post(
            f"/api/v1/transcription/jobs/{job.id}/callback",
            content=body_bytes,
            headers={"X-Signature-SHA256": sig, "Content-Type": "application/json"},
        )
        assert dup_resp.status_code == 200
        assert dup_resp.json()["status"] == "already_completed"

        # Verify no duplicate segments were added
        db.expire_all()
        segments_after = db.query(TranscriptSegment).filter(TranscriptSegment.transcript_id == transcript.id).all()
        assert len(segments_after) == 2
    finally:
        if os.path.exists(fake_path):
            os.remove(fake_path)


def test_callback_replay_attack_prevention(setup_db):
    db: Session = setup_db["db"]
    lesson: Lesson = setup_db["lesson"]
    course: Course = setup_db["course"]

    job, _, raw_secret = TranscriptionJobManager.create_job(
        db=db,
        lesson_id=lesson.id,
        course_id=course.id,
        video_id="replay_test.mp4",
        storage_path="replay_test.mp4",
    )

    payload = {
        "status": "completed",
        "job_id": str(job.id),
        "video_id": "replay_test.mp4",
        "lesson_id": str(lesson.id),
        "course_id": str(course.id),
        "duration": 60.0,
        "full_text": "اختبار الحماية من هجمات الإعادة.",
        "segments": [{"sequence": 1, "start_time": 0.0, "end_time": 60.0, "text": "نص التجربة"}],
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    # Stale timestamp: 20 minutes in the past
    stale_timestamp = str(int(time.time() - 1200))
    sig_payload = f"{stale_timestamp}.".encode("utf-8") + body_bytes
    sig = hmac.new(raw_secret.encode("utf-8"), sig_payload, hashlib.sha256).hexdigest()

    resp = client.post(
        f"/api/v1/transcription/jobs/{job.id}/callback",
        content=body_bytes,
        headers={
            "X-Signature-SHA256": sig,
            "X-Timestamp": stale_timestamp,
            "Content-Type": "application/json",
        },
    )
    # Must be rejected due to stale timestamp drift
    assert resp.status_code == 401


def test_cross_course_isolation_protection(setup_db):
    db: Session = setup_db["db"]
    lesson: Lesson = setup_db["lesson"]
    course: Course = setup_db["course"]

    job, _, raw_secret = TranscriptionJobManager.create_job(
        db=db,
        lesson_id=lesson.id,
        course_id=course.id,
        video_id="correct_video.mp4",
        storage_path="some_path.mp4",
    )

    tampered_payload = {
        "status": "completed",
        "job_id": str(job.id),
        "video_id": "correct_video.mp4",
        "lesson_id": str(uuid.uuid4()),  # Cross-lesson tampering attempt
        "course_id": str(course.id),
        "duration": 60.0,
        "full_text": "Tampered content",
        "segments": [{"sequence": 1, "start_time": 0.0, "end_time": 60.0, "text": "Tampered"}],
    }
    body_bytes = json.dumps(tampered_payload).encode("utf-8")
    sig = hmac.new(raw_secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    resp = client.post(
        f"/api/v1/transcription/jobs/{job.id}/callback",
        content=body_bytes,
        headers={"X-Signature-SHA256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 403


def test_truncated_transcript_rejection(setup_db):
    db: Session = setup_db["db"]
    lesson: Lesson = setup_db["lesson"]
    course: Course = setup_db["course"]

    # 2.5-hour media simulation (9000s)
    job, _, raw_secret = TranscriptionJobManager.create_job(
        db=db,
        lesson_id=lesson.id,
        course_id=course.id,
        video_id="long_lecture.mp4",
        storage_path="long_lecture.mp4",
    )

    truncated_payload = {
        "status": "completed",
        "job_id": str(job.id),
        "video_id": "long_lecture.mp4",
        "lesson_id": str(lesson.id),
        "course_id": str(course.id),
        "duration": 9000.0,
        "full_text": "جزء قصير جداً توقف بعد أربع دقائق فقط.",
        "segments": [{"sequence": 1, "start_time": 0.0, "end_time": 240.0, "text": "جزء قصير"}],
    }
    body_bytes = json.dumps(truncated_payload).encode("utf-8")
    sig = hmac.new(raw_secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    resp = client.post(
        f"/api/v1/transcription/jobs/{job.id}/callback",
        content=body_bytes,
        headers={"X-Signature-SHA256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data or "detail" in data
    err_str = json.dumps(data)
    assert "coverage" in err_str.lower() or "truncated" in err_str.lower()

    db.expire_all()
    reloaded_job = db.get(TranscriptionJob, job.id)
    assert reloaded_job.status == TranscriptionJobStatus.FAILED
    assert reloaded_job.error_code == "TRUNCATED_TRANSCRIPT"


def test_failure_callback_handling(setup_db):
    db: Session = setup_db["db"]
    lesson: Lesson = setup_db["lesson"]
    course: Course = setup_db["course"]

    job, _, raw_secret = TranscriptionJobManager.create_job(
        db=db,
        lesson_id=lesson.id,
        course_id=course.id,
        video_id="broken_video.mp4",
        storage_path="broken_video.mp4",
    )

    fail_payload = {
        "status": "failed",
        "job_id": str(job.id),
        "video_id": "broken_video.mp4",
        "error_code": "FFMPEG_EXTRACTION_ERROR",
        "message": "Corrupted audio stream",
    }
    body_bytes = json.dumps(fail_payload).encode("utf-8")
    sig = hmac.new(raw_secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    resp = client.post(
        f"/api/v1/transcription/jobs/{job.id}/callback",
        content=body_bytes,
        headers={"X-Signature-SHA256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed_recorded"

    db.expire_all()
    reloaded_job = db.get(TranscriptionJob, job.id)
    assert reloaded_job.status == TranscriptionJobStatus.FAILED
    assert reloaded_job.error_code == "FFMPEG_EXTRACTION_ERROR"


def test_overlap_deduplication_logic():
    # Case 1: Overlap duplication from chunk boundaries
    prev = "أهلاً بكم في شرح الصخور النارية والصخور الرسوبية"
    curr = "والصخور الرسوبية والصخور المتحولة في باطن الأرض"
    deduped = deduplicate_overlap_words(prev, curr, max_check_words=5)
    assert deduped == "والصخور المتحولة في باطن الأرض"

    # Case 2: Teacher emphasis (should be preserved when within chunk)
    prev2 = "ركز معايا في النقطة دي"
    curr2 = "ركز معايا في النقطة دي عشان مهمة جداً"
    deduped2 = deduplicate_overlap_words(prev2, curr2, max_check_words=6)
    assert deduped2 == "عشان مهمة جداً"


def test_job_status_endpoint(setup_db):
    db: Session = setup_db["db"]
    lesson: Lesson = setup_db["lesson"]
    course: Course = setup_db["course"]
    teacher: User = setup_db["teacher"]
    from app.core.security import create_session_token

    job, _, _ = TranscriptionJobManager.create_job(
        db=db,
        lesson_id=lesson.id,
        course_id=course.id,
        video_id="video_status_test.mp4",
        storage_path="path.mp4",
    )

    # 1. Unauthenticated request must return 401
    resp_unauth = client.get(f"/api/v1/transcription/jobs/{job.id}")
    assert resp_unauth.status_code == 401

    # 2. Authenticated request for course teacher returns 200
    token = create_session_token(teacher)
    resp = client.get(f"/api/v1/transcription/jobs/{job.id}", cookies={"matgar_session": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(job.id)
    assert data["status"] == "queued"
    assert data["progress_percent"] == 0
