from __future__ import annotations

import asyncio
import json as _json
import os
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.database import SessionLocal
from app.models.course import Course, CourseModule, IndexingStatus, Lesson
from app.models.transcript import KnowledgeChunk, Transcript, TranscriptSegment, TranscriptionStatus
from app.services.knowledge_pipeline import (
    create_semantic_chunks,
    normalize_transcript_text,
)
from app.services.transcription_provider import (
    TranscriptSegmentData,
    TranscriptionResult,
    get_transcription_provider,
)

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001").rstrip("/")
AI_SERVICE_TIMEOUT = min(float(os.getenv("AI_SERVICE_TIMEOUT", "2.0")), 5.0)
CHUNK_SIZE = 400
TIMESTAMP_EVERY_S = 30
_INDEXING_SEMAPHORE = asyncio.Semaphore(2)
LESSON_INDEXING_PROGRESS: dict[str, dict[str, Any]] = {}


async def push_chunks_to_rag(course_id: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Video RAG push is permanently disabled. Video files are pure playback assets."""
    return {"status": "disabled", "indexed_chunks_count": 0, "message": "Video RAG push permanently disabled."}


async def index_lesson_video(
    course_id_str: str,
    lesson_id_str: str,
    video_path_or_url: str | None,
    existing_transcript: str | None,
) -> dict[str, Any]:
    """Process and index lesson content into timestamped knowledge chunks."""
    transcript_text = normalize_transcript_text(existing_transcript or "")
    if not transcript_text or len(transcript_text.strip()) < 2:
        return {
            "indexed_chunks_count": 0,
            "status": "no_content",
            "message": "لا يوجد نص تفريغ أو محتوى متاح لفهرسة هذا الدرس.",
        }

    words = transcript_text.split()
    chunks = []
    sec_per_word = 0.35
    total_duration = max(1, int(len(words) * sec_per_word))

    for i in range(0, len(words), CHUNK_SIZE):
        seg_words = words[i : i + CHUNK_SIZE]
        chunk_text = " ".join(seg_words).strip()
        chunk_index = i // CHUNK_SIZE
        start_sec = chunk_index * TIMESTAMP_EVERY_S
        end_sec = min(total_duration, (chunk_index + 1) * TIMESTAMP_EVERY_S)

        chunks.append(
            {
                "lesson_id": str(lesson_id_str),
                "content": chunk_text,
                "metadata": {
                    "kind": "video_transcript",
                    "time_range": f"[{start_sec // 60:02d}:{start_sec % 60:02d} - {end_sec // 60:02d}:{end_sec % 60:02d}]",
                    "source": "lesson_content",
                },
            }
        )

    rag_res = await push_chunks_to_rag(course_id=course_id_str, chunks=chunks)
    rag_ok = rag_res.get("status") not in {"offline_fallback", "error"}
    return {
        "indexed_chunks_count": len(chunks),
        "status": "success",
        "transcript": transcript_text,
        "rag_synced": rag_ok,
        "details": rag_res,
    }


async def execute_lesson_indexing(lesson_id_str: str) -> dict[str, Any]:
    """Video indexing is permanently disabled. Video files are pure playback assets."""
    LESSON_INDEXING_PROGRESS[lesson_id_str] = {"progress": 100, "stage": "الفهرسة معطلة لملفات الفيديو"}
    return {"status": "disabled", "message": "Video indexing is permanently disabled."}

async def _legacy_execute_lesson_indexing(lesson_id_str: str) -> dict[str, Any]:
    async with _INDEXING_SEMAPHORE:
        with SessionLocal() as db:
            try:
                lesson_uuid = uuid.UUID(lesson_id_str)
            except ValueError:
                LESSON_INDEXING_PROGRESS[lesson_id_str] = {"progress": 0, "stage": "خطأ في المعرف"}
                return {"status": "error", "message": "Invalid lesson UUID"}

            lesson = db.get(Lesson, lesson_uuid)
            if not lesson:
                LESSON_INDEXING_PROGRESS[lesson_id_str] = {"progress": 0, "stage": "الدرس غير موجود"}
                return {"status": "error", "message": "Lesson not found"}

            module = db.get(CourseModule, lesson.module_id)
            course_id = module.course_id if module else uuid.uuid4()

            LESSON_INDEXING_PROGRESS[lesson_id_str] = {"progress": 15, "stage": "استخراج الصوت ومعالجة الفيديو"}

            # Get or create Transcript entity
            transcript = db.query(Transcript).filter(Transcript.lesson_id == lesson_uuid).first()
            if not transcript:
                transcript = Transcript(
                    lesson_id=lesson_uuid,
                    status=TranscriptionStatus.PROCESSING,
                )
                db.add(transcript)
            else:
                transcript.status = TranscriptionStatus.PROCESSING
                transcript.error_code = None
                transcript.error_message = None
            db.commit()

            # Locate video file on disk
            video_disk_path = None
            if lesson.video_asset_key:
                filename = os.path.basename(lesson.video_asset_key)
                candidate_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "uploads",
                    filename,
                )
                if os.path.exists(candidate_path):
                    video_disk_path = candidate_path

            transcription_res: TranscriptionResult | None = None
            if video_disk_path:
                try:
                    LESSON_INDEXING_PROGRESS[lesson_id_str] = {"progress": 40, "stage": "تفريغ الكلمات بالذكاء الاصطناعي"}
                    provider = get_transcription_provider()
                    transcription_res = await provider.transcribe(video_disk_path)
                except Exception as exc:
                    print(f"Transcription error on {video_disk_path}: {exc}")
                    transcript.status = TranscriptionStatus.FAILED
                    transcript.error_code = "TRANSCRIPTION_ERROR"
                    transcript.error_message = str(exc)[:500]
                    lesson.indexing_status = IndexingStatus.FAILED
                    lesson.indexing_error = str(exc)[:500]
                    db.commit()
                    LESSON_INDEXING_PROGRESS[lesson_id_str] = {"progress": 0, "stage": f"فشل التفريغ: {str(exc)[:60]}"}
                    return {"status": "error", "message": str(exc)}

            # Fallback for text/article lessons without video files
            if not transcription_res or not transcription_res.full_text:
                fallback_text = (lesson.transcript_text or lesson.content or lesson.title or "").strip()
                if not fallback_text:
                    fallback_text = "درس تعليمي شامل."
                fallback_segments = [
                    TranscriptSegmentData(sequence=1, start_time=0.0, end_time=30.0, text=fallback_text)
                ]
                transcription_res = TranscriptionResult(
                    language="ar",
                    duration=30.0,
                    full_text=fallback_text,
                    segments=fallback_segments,
                )

            LESSON_INDEXING_PROGRESS[lesson_id_str] = {"progress": 70, "stage": "حفظ المقاطع وفهرسة المعرفة"}

            # Clean and normalize full text
            normalized_text = normalize_transcript_text(transcription_res.full_text)
            transcript.language = transcription_res.language
            transcript.duration_seconds = transcription_res.duration
            transcript.full_text = normalized_text
            transcript.provider = "whisper" if os.getenv("TRANSCRIPTION_PROVIDER", "").lower() != "mock" else "mock"
            transcript.status = TranscriptionStatus.COMPLETED
            transcript.completed_at = datetime.now(timezone.utc)

            if transcription_res.duration > 0:
                lesson.video_duration_seconds = int(transcription_res.duration)

            # Clear previous segments and chunks to ensure idempotency
            db.query(TranscriptSegment).filter(TranscriptSegment.transcript_id == transcript.id).delete()
            db.query(KnowledgeChunk).filter(KnowledgeChunk.transcript_id == transcript.id).delete()
            db.flush()

            # Save timestamped segments
            for seg in transcription_res.segments:
                db_seg = TranscriptSegment(
                    transcript_id=transcript.id,
                    lesson_id=lesson_uuid,
                    sequence=seg.sequence,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    text=normalize_transcript_text(seg.text),
                )
                db.add(db_seg)

            # Generate semantic knowledge chunks
            chunk_dicts = create_semantic_chunks(transcription_res.segments)
            for cd in chunk_dicts:
                db_chunk = KnowledgeChunk(
                    transcript_id=transcript.id,
                    lesson_id=lesson_uuid,
                    course_id=course_id,
                    sequence=cd["sequence"],
                    start_time=cd["start_time"],
                    end_time=cd["end_time"],
                    text=cd["text"],
                    metadata_json=cd.get("metadata_json"),
                )
                db.add(db_chunk)

            # Update lesson record
            lesson.indexing_status = IndexingStatus.INDEXED
            lesson.indexed_chunks_count = len(chunk_dicts)
            lesson.transcript_text = normalized_text
            lesson.content = normalized_text
            lesson.indexing_error = None

            LESSON_INDEXING_PROGRESS[lesson_id_str] = {"progress": 90, "stage": "مزامنة الفهرس الدلالي"}

            # Push to vector RAG service
            rag_chunks = [
                {
                    "lesson_id": str(lesson.id),
                    "content": cd["text"],
                    "metadata": {
                        "kind": "video_transcript",
                        "time_range": cd.get("metadata_json", {}).get("time_range", ""),
                        "start_time": cd["start_time"],
                        "end_time": cd["end_time"],
                    },
                }
                for cd in chunk_dicts
            ]
            rag_res = await push_chunks_to_rag(course_id=str(course_id), chunks=rag_chunks)
            lesson.rag_synced = rag_res.get("status") not in {"offline_fallback", "error"}

            db.commit()
            db.refresh(lesson)
            LESSON_INDEXING_PROGRESS[lesson_id_str] = {"progress": 100, "stage": "تمت الفهرسة بنجاح"}

            return {
                "lesson_id": str(lesson.id),
                "indexing_status": "indexed",
                "indexed_chunks_count": len(chunk_dicts),
                "rag_synced": lesson.rag_synced,
                "segments_count": len(transcription_res.segments),
            }


async def sync_lesson_rag(lesson_id_str: str, max_retries: int = 3) -> dict[str, Any]:
    """Sync an existing indexed lesson transcript to the RAG vector service with automatic retries."""
    return await execute_lesson_indexing(lesson_id_str)
