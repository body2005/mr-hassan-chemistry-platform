from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone, timedelta
UTC = timezone.utc
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.course import Course, IndexingStatus, Lesson
from app.models.transcript import (
    KnowledgeChunk,
    Transcript,
    TranscriptSegment,
    TranscriptionJob,
    TranscriptionJobStatus,
    TranscriptionStatus,
)
from app.services.knowledge_pipeline import create_semantic_chunks, normalize_transcript_text
from app.services.remote_compute.base import RemoteComputeProvider
from app.services.remote_compute.kaggle_provider import KaggleProvider
from app.services.remote_compute.local_provider import LocalFallbackProvider
from app.services.remote_compute.mock_provider import MockRemoteProvider
from app.services.transcription_provider import (
    TranscriptSegmentData,
    TranscriptionResult,
    extract_audio_track,
    get_media_duration_seconds,
    get_transcription_provider,
)

logger = logging.getLogger(__name__)

# Active providers
MOCK_PROVIDER = MockRemoteProvider()
LOCAL_PROVIDER = LocalFallbackProvider()


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hash of a secret token for secure database storage."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def get_remote_provider(name: str | None = None) -> RemoteComputeProvider:
    """Resolve the active compute provider based on environment configuration."""
    target = (name or os.getenv("REMOTE_PROVIDER", "auto")).lower()
    if target == "mock" or os.getenv("APP_ENV") == "test":
        return MOCK_PROVIDER
    if target == "kaggle" or os.getenv("KAGGLE_ASR_URL") or os.getenv("REMOTE_ASR_URL"):
        return KaggleProvider()
    return LOCAL_PROVIDER


class TranscriptionJobManager:
    """
    Central orchestrator for end-to-end asynchronous transcription jobs.
    Manages token generation, dispatch, HMAC verification, artifact import, and persistence.
    """

    @staticmethod
    def create_job(
        db: Session,
        lesson_id: uuid.UUID,
        course_id: uuid.UUID,
        video_id: str,
        storage_path: str,
        provider_name: str | None = None,
        model_name: str = "QwenCleo-ASR",
        token_ttl_hours: int = 6,
    ) -> tuple[TranscriptionJob, str, str]:
        """
        Create and persist a new TranscriptionJob with cryptographically secure tokens.
        Returns (job, raw_download_token, raw_callback_secret).
        """
        raw_download_token = secrets.token_urlsafe(32)
        raw_callback_secret = secrets.token_hex(32)
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=token_ttl_hours)

        chosen_provider = provider_name or os.getenv("TRANSCRIPTION_PROVIDER", "auto")
        if chosen_provider == "auto":
            chosen_provider = "kaggle" if (os.getenv("KAGGLE_ASR_URL") or os.getenv("REMOTE_ASR_URL")) else "local_whisper"

        job = TranscriptionJob(
            lesson_id=lesson_id,
            course_id=course_id,
            video_id=str(video_id),
            storage_path=str(storage_path),
            status=TranscriptionJobStatus.QUEUED,
            provider=chosen_provider,
            model_name=model_name,
            progress_percent=0,
            current_stage="queued",
            signed_download_token_hash=hash_token(raw_download_token),
            signed_token_expires_at=expires_at,
            callback_secret_hash=raw_callback_secret,  # Stored for HMAC signing verification
            retry_count=0,
            max_retries=int(os.getenv("REMOTE_MAX_RETRIES", "3")),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        return job, raw_download_token, raw_callback_secret

    @staticmethod
    def resolve_download_file(db: Session, token: str) -> str | None:
        """Validate signed download token and return local file path if authorized and unexpired."""
        token_h = hash_token(token)
        now = datetime.now(UTC)
        job = db.scalar(
            select(TranscriptionJob).where(
                TranscriptionJob.signed_download_token_hash == token_h,
                TranscriptionJob.signed_token_expires_at > now,
            )
        )
        if not job or not os.path.exists(job.storage_path):
            return None
        return job.storage_path

    @staticmethod
    @staticmethod
    def verify_callback_signature(
        job: TranscriptionJob,
        auth_header: str | None,
        body_bytes: bytes,
        timestamp: str | None = None,
    ) -> bool:
        """
        Verify authenticated callback using HMAC-SHA256 signature with replay protection.
        """
        if not auth_header:
            return False

        secret = job.callback_secret_hash

        # Replay Attack Prevention: Validate timestamp freshness (within 10 minutes)
        if timestamp:
            try:
                ts_float = float(timestamp)
                now_ts = time.time()
                if abs(now_ts - ts_float) > 600:
                    logger.warning(f"[JobManager] Callback timestamp stale/replay rejected: drift={abs(now_ts - ts_float):.1f}s")
                    return False
            except Exception:
                pass

        # Option 1: Direct token match (for internal testing/local fallback)
        if auth_header.strip() == secret.strip():
            return True

        # Option 2: HMAC-SHA256 signature
        provided_sig = auth_header.replace("sha256=", "").strip()

        # Check timestamp-bound HMAC: HMAC(secret, f"{timestamp}.{body}")
        if timestamp:
            sig_payload = f"{timestamp}.".encode("utf-8") + body_bytes
            expected_sig_ts = hmac.new(secret.encode("utf-8"), sig_payload, hashlib.sha256).hexdigest()
            if hmac.compare_digest(provided_sig, expected_sig_ts):
                return True

        # Fallback to direct body HMAC: HMAC(secret, body)
        expected_sig_raw = hmac.new(
            secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(provided_sig, expected_sig_raw)

    @classmethod
    async def process_callback(
        cls,
        db: Session,
        job_id: uuid.UUID,
        payload: dict[str, Any],
        auth_header: str | None,
        body_bytes: bytes,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """
        Process authenticated callback from remote worker and ingest transcript artifacts.
        Ensures strict idempotency, duration integrity validation, and RAG indexing.
        """
        job = db.get(TranscriptionJob, job_id)
        if not job:
            return {"error": "JOB_NOT_FOUND", "message": "Job ID not found"}

        # 1. Verify Authentication & Replay Protection
        if not cls.verify_callback_signature(job, auth_header, body_bytes, timestamp=timestamp):
            logger.warning(f"[JobManager] Callback unauthorized or replay detected for job {job_id}")
            return {"error": "UNAUTHORIZED", "message": "Invalid callback signature or token"}

        # 2. Verify Cross-Course / Lesson Isolation
        if payload.get("video_id") and str(payload.get("video_id")) != str(job.video_id):
            return {"error": "VIDEO_MISMATCH", "message": "Video ID mismatch"}
        if payload.get("lesson_id") and str(payload.get("lesson_id")) != str(job.lesson_id):
            return {"error": "LESSON_MISMATCH", "message": "Lesson ID mismatch"}

        # 3. Idempotency Check
        incoming_seg_count = len(payload.get("segments") or [])
        if job.status == TranscriptionJobStatus.COMPLETED and incoming_seg_count <= (job.segment_count or 0):
            logger.info(f"[JobManager] Job {job_id} already completed. Ignoring duplicate callback.")
            return {"status": "already_completed", "job_id": str(job.id)}

        cb_status = payload.get("status", "completed").lower()

        # Handle Failure Callback
        if cb_status == "failed":
            job.status = TranscriptionJobStatus.FAILED
            job.error_code = payload.get("error_code", "REMOTE_WORKER_ERROR")
            job.error_message = payload.get("message", "Remote worker failed to transcribe media")
            job.current_stage = "failed"
            lesson = db.get(Lesson, job.lesson_id)
            if lesson:
                lesson.indexing_status = IndexingStatus.FAILED
                lesson.indexing_error = job.error_message
            db.commit()
            return {"status": "failed_recorded", "job_id": str(job.id)}

        # 4. Ingest Transcript Data
        full_text = payload.get("full_text", "").strip()
        segments_raw = payload.get("segments", [])
        duration = float(payload.get("duration", 0.0))

        if not segments_raw and not full_text:
            job.status = TranscriptionJobStatus.FAILED
            job.error_code = "EMPTY_TRANSCRIPT"
            job.error_message = "Remote worker returned empty transcript payload"
            db.commit()
            return {"error": "EMPTY_TRANSCRIPT", "message": "Transcript cannot be empty"}

        # Calculate Duration Coverage Ratio (Production threshold >= 0.95)
        min_coverage_threshold = float(os.getenv("MIN_COVERAGE_RATIO", "0.95"))
        expected_duration = get_media_duration_seconds(job.storage_path) or duration
        final_timestamp = segments_raw[-1].get("end_time", duration) if segments_raw else duration
        coverage_ratio = final_timestamp / expected_duration if expected_duration > 0 else 1.0
        job.coverage_ratio = coverage_ratio

        # Reject Suspicious Truncation (Production standard: must cover >= 95% of lecture audio)
        if expected_duration > 30 and coverage_ratio < min_coverage_threshold:
            job.status = TranscriptionJobStatus.FAILED
            job.error_code = "TRUNCATED_TRANSCRIPT"
            job.error_message = f"Transcript coverage ({coverage_ratio*100:.1f}%) is below minimum required {min_coverage_threshold*100:.0f}% ({final_timestamp:.1f}s of {expected_duration:.1f}s)"
            lesson = db.get(Lesson, job.lesson_id)
            if lesson:
                lesson.indexing_status = IndexingStatus.FAILED
                lesson.indexing_error = job.error_message
            db.commit()
            return {"error": "TRUNCATED_TRANSCRIPT", "message": job.error_message}

        # 5. Persist Transcript and Segments Idempotently
        existing_transcript = db.scalar(
            select(Transcript).where(Transcript.lesson_id == job.lesson_id)
        )
        if existing_transcript:
            transcript = existing_transcript
            transcript.full_text = full_text
            transcript.duration_seconds = expected_duration
            transcript.status = TranscriptionStatus.COMPLETED
            transcript.provider = job.provider
            transcript.provider_model = job.model_name
            transcript.completed_at = datetime.now(UTC)
            # Remove old segments and chunks
            db.query(TranscriptSegment).filter(TranscriptSegment.transcript_id == transcript.id).delete()
            db.query(KnowledgeChunk).filter(KnowledgeChunk.transcript_id == transcript.id).delete()
        else:
            transcript = Transcript(
                lesson_id=job.lesson_id,
                status=TranscriptionStatus.COMPLETED,
                language=payload.get("language", "ar"),
                duration_seconds=expected_duration,
                full_text=full_text,
                provider=job.provider,
                provider_model=job.model_name,
                completed_at=datetime.now(UTC),
            )
            db.add(transcript)
            db.flush()

        # Insert Segments
        seg_models = []
        for idx, seg in enumerate(segments_raw, 1):
            seg_models.append(
                TranscriptSegment(
                    transcript_id=transcript.id,
                    lesson_id=job.lesson_id,
                    sequence=idx,
                    start_time=float(seg.get("start_time", 0.0)),
                    end_time=float(seg.get("end_time", 0.0)),
                    text=str(seg.get("text", "")).strip(),
                )
            )
        db.add_all(seg_models)

        # 6. Create Knowledge Chunks and Push to RAG
        seg_data_list = [
            TranscriptSegmentData(
                sequence=s.sequence,
                start_time=s.start_time,
                end_time=s.end_time,
                text=s.text,
            )
            for s in seg_models
        ]
        raw_chunks = create_semantic_chunks(seg_data_list)
        chunk_models = []
        for rc in raw_chunks:
            chunk_models.append(
                KnowledgeChunk(
                    transcript_id=transcript.id,
                    lesson_id=job.lesson_id,
                    course_id=job.course_id,
                    sequence=rc["sequence"],
                    start_time=rc["start_time"],
                    end_time=rc["end_time"],
                    text=rc["text"],
                )
            )
        db.add_all(chunk_models)

        # 7. Update Job and Lesson Status
        job.status = TranscriptionJobStatus.COMPLETED
        job.progress_percent = 100
        job.current_stage = "ready"
        job.duration_seconds = expected_duration
        job.segment_count = len(seg_models)
        job.chunk_count = len(chunk_models)
        job.completed_at = datetime.now(UTC)

        lesson = db.get(Lesson, job.lesson_id)
        if lesson:
            lesson.indexing_status = IndexingStatus.INDEXED
            lesson.indexing_error = None
            lesson.video_duration_seconds = int(expected_duration)

        db.commit()
        logger.info(f"[JobManager] Job {job_id} successfully processed and indexed ({len(seg_models)} segments, {len(chunk_models)} chunks).")

        return {
            "status": "success",
            "job_id": str(job.id),
            "segments_count": len(seg_models),
            "chunks_count": len(chunk_models),
            "duration": expected_duration,
            "coverage_ratio": coverage_ratio,
        }

    @classmethod
    async def dispatch_job_async(
        cls,
        job_id: uuid.UUID,
        raw_download_token: str,
        raw_callback_secret: str,
        base_url: str,
    ) -> None:
        """
        Asynchronously dispatch the transcription job to the configured RemoteComputeProvider.
        Includes automatic fallback to local CPU ONLY IF explicitly configured via ENABLE_LOCAL_FALLBACK=true.
        """
        db = SessionLocal()
        try:
            job = db.get(TranscriptionJob, job_id)
            if not job or job.status != TranscriptionJobStatus.QUEUED:
                return

            from app.core.config import get_settings
            settings = get_settings()
            effective_base_url = (os.getenv("REMOTE_CALLBACK_BASE_URL") or settings.remote_callback_base_url or "").rstrip("/")
            if not effective_base_url:
                effective_base_url = base_url.rstrip("/")

            media_url = f"{effective_base_url}/api/v1/transcription/download/{raw_download_token}"
            callback_url = f"{effective_base_url}/api/v1/transcription/jobs/{job.id}/callback"

            provider = get_remote_provider(job.provider)
            success = await provider.submit_job(
                job=job,
                media_download_url=media_url,
                callback_url=callback_url,
                callback_secret=raw_callback_secret,
            )

            if success:
                job.status = TranscriptionJobStatus.PROCESSING
                job.current_stage = "processing"
                job.progress_percent = 25
                db.commit()
            else:
                # Handle Fallback: do NOT burn local CPU unless explicitly configured!
                enable_fallback = os.getenv("ENABLE_LOCAL_FALLBACK", "false").lower() == "true"
                if enable_fallback:
                    logger.warning(f"[JobManager] Remote dispatch failed for job {job.id}. Executing local fallback.")
                    job.provider = "local_whisper"
                    job.model_name = os.getenv("WHISPER_MODEL", "small")
                    job.status = TranscriptionJobStatus.PROCESSING
                    job.current_stage = "local_processing"
                    job.progress_percent = 30
                    db.commit()
                    
                    # Execute local transcription in worker thread
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, cls._run_local_execution_sync, str(job.id), raw_callback_secret, base_url)
                else:
                    logger.warning(f"[JobManager] Remote worker unavailable for job {job.id} and local fallback is disabled.")
                    job.status = TranscriptionJobStatus.FAILED
                    job.current_stage = "failed"
                    job.error_code = "REMOTE_WORKER_UNAVAILABLE"
                    job.error_message = "Remote compute provider is offline or unreachable and local fallback is disabled"
                    lesson = db.get(Lesson, job.lesson_id)
                    if lesson:
                        lesson.indexing_status = IndexingStatus.FAILED
                        lesson.indexing_error = job.error_message
                    db.commit()
        finally:
            db.close()

    @classmethod
    def _run_local_execution_sync(cls, job_id_str: str, callback_secret: str, base_url: str) -> None:
        """Synchronous local fallback worker execution."""
        db = SessionLocal()
        try:
            job_id = uuid.UUID(job_id_str)
            job = db.get(TranscriptionJob, job_id)
            if not job:
                return

            whisper_prov = get_transcription_provider()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                res: TranscriptionResult = loop.run_until_complete(whisper_prov.transcribe(job.storage_path))
            finally:
                loop.close()

            payload = {
                "status": "completed",
                "job_id": str(job.id),
                "video_id": str(job.video_id),
                "lesson_id": str(job.lesson_id),
                "course_id": str(job.course_id),
                "duration": res.duration,
                "full_text": res.full_text,
                "segments": [s.model_dump() for s in res.segments],
            }

            body_bytes = json.dumps(payload).encode("utf-8")
            loop2 = asyncio.new_event_loop()
            asyncio.set_event_loop(loop2)
            try:
                loop2.run_until_complete(
                    cls.process_callback(db, job_id, payload, callback_secret, body_bytes)
                )
            finally:
                loop2.close()
        except Exception as exc:
            logger.error(f"[JobManager] Local fallback execution error: {exc}", exc_info=True)
            if job:
                job.status = TranscriptionJobStatus.FAILED
                job.error_code = "LOCAL_FALLBACK_ERROR"
                job.error_message = str(exc)
                db.commit()
        finally:
            db.close()
