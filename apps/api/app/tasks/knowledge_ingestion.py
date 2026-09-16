from __future__ import annotations

import logging
import threading
import uuid

from sqlalchemy import select, text

from app.core.database import SessionLocal, engine
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


class SourceAdvisoryLock:
    """Manages dedicated-connection PostgreSQL session advisory lock or local test lock.

    In PostgreSQL, advisory locks are session-level, meaning they are bound to the
    specific physical backend connection. This lock holds a dedicated connection
    from the engine open for the entire duration of the task, ensuring unlock
    executes on the exact same connection and the connection is never returned
    to the pool while the lock is held.
    """

    def __init__(self, source_id: uuid.UUID):
        self.source_id = source_id
        self._lock_key = int.from_bytes(source_id.bytes[:8], byteorder="big", signed=True)
        self._conn = None
        self.acquired = False
        self.is_postgres = (engine.dialect.name == "postgresql")

    def acquire(self) -> bool:
        if self.is_postgres:
            self._conn = engine.connect()
            try:
                res = self._conn.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": self._lock_key},
                )
                self.acquired = bool(res)
                if not self.acquired:
                    self._conn.close()
                    self._conn = None
                return self.acquired
            except Exception:
                if self._conn:
                    self._conn.close()
                    self._conn = None
                raise
        else:
            with _LOCAL_LOCK_GUARD:
                if self.source_id in _LOCAL_ACTIVE_SOURCES:
                    self.acquired = False
                    return False
                _LOCAL_ACTIVE_SOURCES.add(self.source_id)
                self.acquired = True
                return True

    def release(self) -> None:
        if not self.acquired:
            return
        if self.is_postgres:
            if self._conn:
                try:
                    self._conn.execute(
                        text("SELECT pg_advisory_unlock(:key)"),
                        {"key": self._lock_key},
                    )
                except Exception as exc:
                    logger.warning("Failed to release advisory lock for source %s: %s", self.source_id, exc)
                finally:
                    self._conn.close()
                    self._conn = None
            self.acquired = False
        else:
            with _LOCAL_LOCK_GUARD:
                _LOCAL_ACTIVE_SOURCES.discard(self.source_id)
            self.acquired = False

    def __enter__(self) -> SourceAdvisoryLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


def _try_source_lock(db, source_id: uuid.UUID) -> bool:
    """Legacy helper maintained for backward compatibility with external callers."""
    if db.bind.dialect.name == "postgresql":
        lock_key = int.from_bytes(source_id.bytes[:8], byteorder="big", signed=True)
        return bool(db.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}))
    with _LOCAL_LOCK_GUARD:
        if source_id in _LOCAL_ACTIVE_SOURCES:
            return False
        _LOCAL_ACTIVE_SOURCES.add(source_id)
        return True


def _release_source_lock(db, source_id: uuid.UUID) -> None:
    """Legacy helper maintained for backward compatibility with external callers."""
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

    lock = SourceAdvisoryLock(s_uuid)
    lock_acquired = False
    parser_marked_active = False

    try:
        # 1. Acquire advisory lock FIRST on dedicated physical connection
        if not lock.acquire():
            logger.info("Source %s already has an active worker lock", source_id)
            return {"source_id": source_id, "status": "ALREADY_ACTIVE"}
        lock_acquired = True

        # 2. Mark parser active ONLY after lock is acquired
        mark_parser_active(s_uuid)
        parser_marked_active = True

        # 3. Check source existence and matching generation/attempt
        with SessionLocal() as db:
            source = db.get(KnowledgeSource, s_uuid)
            if not source:
                logger.warning("KnowledgeSource %s not found in DB; abandoning task", source_id)
                return {"source_id": source_id, "status": "NOT_FOUND"}

            if source.status == SourceStatus.DELETING:
                logger.info("Source %s is DELETING; worker abandoning task", source_id)
                return {"source_id": source_id, "status": "DELETING"}

            if (
                source.processing_generation != generation
                or source.processing_attempt_id != attempt_uuid
            ):
                logger.info("Discarding stale generation %d for source %s", generation, source_id)
                return {"source_id": source_id, "status": "STALE_ATTEMPT"}

            if source.status == SourceStatus.INDEXED:
                return {"source_id": source_id, "status": str(SourceStatus.INDEXED)}

            if source.status in (SourceStatus.CANCELLED, SourceStatus.STOPPED):
                return {"source_id": source_id, "status": str(source.status)}

            source.active_task_id = self.request.id
            source.status = SourceStatus.PROCESSING
            db.commit()

            if is_source_cancelled(s_uuid, generation=generation, attempt_id=attempt_uuid):
                logger.info("Source %s was cancelled before processing started", source_id)
                current = db.get(KnowledgeSource, s_uuid)
                if current and current.status != SourceStatus.DELETING:
                    current.status = SourceStatus.CANCELLED
                    current.error_message = "تم إيقاف الفهرسة"
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
                current = db.get(KnowledgeSource, s_uuid)
                if current and current.status != SourceStatus.DELETING:
                    current.status = SourceStatus.CANCELLED
                    current.error_message = "تم إيقاف الفهرسة"
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
                    # Keep status active, do not set FAILED, do not wipe progress
                    raise self.retry(exc=retryable_exc, countdown=min(60 * (2 ** self.request.retries), 300))
                else:
                    # Retries exhausted: mark FAILED
                    current = db.get(KnowledgeSource, s_uuid)
                    if (
                        current
                        and current.status != SourceStatus.DELETING
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
                    and current.status != SourceStatus.DELETING
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
            try:
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
            except Exception as e:
                logger.warning("Failed to clear active_task_id for source %s: %s", source_id, e)
            lock.release()
