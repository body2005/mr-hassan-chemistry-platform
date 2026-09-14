from __future__ import annotations

import uuid
import logging
import threading

from sqlalchemy import text

from app.core.errors import OperationCancelledError
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
    autoretry_for=(IOError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def index_source(
    self,
    source_id: str,
    generation: int,
    attempt_id: str,
) -> dict[str, str]:
    from app.core.database import SessionLocal
    from app.models.knowledge_center import KnowledgeSource, SourceStatus
    from app.services.knowledge_center_service import (
        is_source_cancelled,
        mark_parser_active,
        mark_parser_inactive,
        process_knowledge_source,
    )

    s_uuid = uuid.UUID(source_id)
    retry_number = self.request.retries + 1
    attempt_uuid = uuid.UUID(attempt_id)
    logger.info(
        "Celery worker starting source %s generation %d retry %d/4",
        source_id,
        generation,
        retry_number,
    )

    mark_parser_active(s_uuid)
    try:
        with SessionLocal() as db:
            if not _try_source_lock(db, s_uuid):
                logger.info("Source %s already has an active worker", source_id)
                return {"source_id": source_id, "status": "ALREADY_ACTIVE"}
            source = db.get(KnowledgeSource, s_uuid)
            if not source:
                logger.warning("KnowledgeSource %s not found in DB; abandoning task", source_id)
                _release_source_lock(db, s_uuid)
                return {"source_id": source_id, "status": "NOT_FOUND"}
            if (
                source.processing_generation != generation
                or source.processing_attempt_id != attempt_uuid
            ):
                logger.info("Discarding stale generation %d for source %s", generation, source_id)
                _release_source_lock(db, s_uuid)
                return {"source_id": source_id, "status": "STALE_ATTEMPT"}
            if source.status == SourceStatus.INDEXED:
                _release_source_lock(db, s_uuid)
                return {"source_id": source_id, "status": str(SourceStatus.INDEXED)}

            source.active_task_id = self.request.id
            db.commit()

            if is_source_cancelled(s_uuid):
                logger.info("Source %s was cancelled before processing started", source_id)
                source.status = SourceStatus.CANCELLED
                source.error_message = "تم إيقاف الفهرسة"
                db.commit()
                _release_source_lock(db, s_uuid)
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
            except Exception as exc:
                logger.exception("Error indexing source %s: %s", source_id, str(exc).split(":")[0])
                db.rollback()
                current = db.get(KnowledgeSource, s_uuid)
                if (
                    current
                    and current.processing_generation == generation
                    and current.processing_attempt_id == attempt_uuid
                ):
                    current.status = SourceStatus.FAILED
                    current.error_message = str(exc).split(":")[0][:255]
                    db.commit()
                raise
            finally:
                db.rollback()
                current = db.get(KnowledgeSource, s_uuid)
                if (
                    current
                    and current.processing_generation == generation
                    and current.processing_attempt_id == attempt_uuid
                    and current.active_task_id == self.request.id
                ):
                    current.active_task_id = None
                    db.commit()
                _release_source_lock(db, s_uuid)
    finally:
        mark_parser_inactive(s_uuid)
