from __future__ import annotations

import uuid
import logging
import threading

from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.errors import OperationCancelledError
from app.models.knowledge_center import KnowledgeSource, SourceStatus
from app.services.knowledge_center_service import (
    is_source_cancelled,
    mark_parser_active,
    mark_parser_inactive,
    process_knowledge_source,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
_LOCAL_LOCK_GUARD = threading.Lock()
_LOCAL_ACTIVE_SOURCES: set[uuid.UUID] = set()


def _try_source_lock(db, source_id: uuid.UUID) -> bool:
    if db.bind.dialect.name == "postgresql":
        lock_key = int.from_bytes(source_id.bytes[:8], byteorder="big", signed=True)
        return bool(db.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}))
    with _LOCAL_LOCK_GUARD:
        if source_id in _LOCAL_ACTIVE_SOURCES:
            return False
        _LOCAL_ACTIVE_SOURCES.add(source_id)
        return True


def _release_source_lock(db, source_id: uuid.UUID) -> None:
    if db.bind.dialect.name == "postgresql":
        lock_key = int.from_bytes(source_id.bytes[:8], byteorder="big", signed=True)
        db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
        return
    with _LOCAL_LOCK_GUARD:
        _LOCAL_ACTIVE_SOURCES.discard(source_id)


@celery_app.task(
    name="knowledge_center.index_source",
    bind=True,
    max_retries=3,
)
def index_source(
    self,
    source_id: str,
    generation: int,
    attempt_id: str,
) -> dict[str, str]:
    s_uuid = uuid.UUID(source_id)
    attempt_uuid = uuid.UUID(attempt_id)
    logger.info(
        "Celery worker starting source %s generation %d attempt %s (retry %d/%d)",
        source_id,
        generation,
        attempt_id,
        self.request.retries,
        self.max_retries,
    )

    lock_acquired = False
    parser_marked_active = False

    try:
        with SessionLocal() as db:
            # 1. Acquire advisory lock FIRST
            if not _try_source_lock(db, s_uuid):
                logger.info("Source %s already has an active worker lock", source_id)
                return {"source_id": source_id, "status": "ALREADY_ACTIVE"}
            lock_acquired = True

            # 2. Mark parser active ONLY after lock is acquired
            mark_parser_active(s_uuid)
            parser_marked_active = True

            # 3. Check source existence and matching generation/attempt
            source = db.get(KnowledgeSource, s_uuid)
            if not source:
                logger.warning("KnowledgeSource %s not found in DB; abandoning task", source_id)
                return {"source_id": source_id, "status": "NOT_FOUND"}

            if (
                source.processing_generation != generation
                or source.processing_attempt_id != attempt_uuid
            ):
                logger.info("Discarding stale generation %d for source %s", generation, source_id)
                return {"source_id": source_id, "status": "STALE_ATTEMPT"}

            if source.status == SourceStatus.INDEXED:
                return {"source_id": source_id, "status": str(SourceStatus.INDEXED)}

            source.active_task_id = self.request.id
            db.commit()

            if is_source_cancelled(s_uuid):
                logger.info("Source %s was cancelled before processing started", source_id)
                source.status = SourceStatus.CANCELLED
                source.error_message = "تم إيقاف الفهرسة"
                db.commit()
                return {"source_id": source_id, "status": str(SourceStatus.CANCELLED)}

            try:
                processed_source = process_knowledge_source(
                    db,
                    s_uuid,
                    generation=generation,
                    attempt_id=attempt_uuid,
                )
                return {"source_id": str(processed_source.id), "status": str(processed_source.status)}
            except OperationCancelledError:
                logger.info("Indexing cancelled cooperatively for source %s", source_id)
                source.status = SourceStatus.CANCELLED
                source.error_message = "تم إيقاف الفهرسة"
                db.commit()
                return {"source_id": source_id, "status": str(SourceStatus.CANCELLED)}
            except (IOError, ConnectionError, TimeoutError, OSError) as retryable_exc:
                logger.warning(
                    "Retryable error indexing source %s (retry %d/%d): %s",
                    source_id,
                    self.request.retries,
                    self.max_retries,
                    str(retryable_exc),
                )
                db.rollback()
                if self.request.retries < self.max_retries:
                    # Keep status active (QUEUED or PROCESSING), do not set FAILED, do not wipe progress
                    raise self.retry(exc=retryable_exc, countdown=min(60 * (2 ** self.request.retries), 300))
                else:
                    # Retries exhausted: mark FAILED
                    current = db.get(KnowledgeSource, s_uuid)
                    if (
                        current
                        and current.processing_generation == generation
                        and current.processing_attempt_id == attempt_uuid
                    ):
                        current.status = SourceStatus.FAILED
                        current.error_message = f"فشلت المعالجة بعد {self.max_retries} محاولات: {str(retryable_exc).split(':')[0][:200]}"
                        db.commit()
                    raise
            except Exception as fatal_exc:
                logger.exception("Non-recoverable error indexing source %s: %s", source_id, str(fatal_exc).split(":")[0])
                db.rollback()
                current = db.get(KnowledgeSource, s_uuid)
                if (
                    current
                    and current.processing_generation == generation
                    and current.processing_attempt_id == attempt_uuid
                ):
                    current.status = SourceStatus.FAILED
                    current.error_message = str(fatal_exc).split(":")[0][:255]
                    db.commit()
                raise
    finally:
        if parser_marked_active:
            mark_parser_inactive(s_uuid)
        if lock_acquired:
            with SessionLocal() as db_clean:
                current = db_clean.get(KnowledgeSource, s_uuid)
                if (
                    current
                    and current.processing_generation == generation
                    and current.processing_attempt_id == attempt_uuid
                    and current.active_task_id == self.request.id
                ):
                    current.active_task_id = None
                    db_clean.commit()
                _release_source_lock(db_clean, s_uuid)
