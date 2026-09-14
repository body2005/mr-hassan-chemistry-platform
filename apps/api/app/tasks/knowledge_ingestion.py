from __future__ import annotations

import uuid

from app.tasks.celery_app import celery_app


import logging
from app.core.errors import OperationCancelledError
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="knowledge_center.index_source",
    bind=True,
    autoretry_for=(IOError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def index_source(self, source_id: str) -> dict[str, str]:
    from app.core.database import SessionLocal
    from app.models.knowledge_center import KnowledgeSource, SourceStatus
    from app.services.knowledge_center_service import (
        is_source_cancelled,
        mark_parser_active,
        mark_parser_inactive,
        process_knowledge_source,
    )

    s_uuid = uuid.UUID(source_id)
    attempt = self.request.retries + 1
    logger.info("Celery worker starting indexing for source %s (attempt %d/4)", source_id, attempt)

    mark_parser_active(s_uuid)
    try:
        with SessionLocal() as db:
            source = db.get(KnowledgeSource, s_uuid)
            if not source:
                logger.warning("KnowledgeSource %s not found in DB; abandoning task", source_id)
                return {"source_id": source_id, "status": "NOT_FOUND"}

            if is_source_cancelled(s_uuid):
                logger.info("Source %s was cancelled before processing started", source_id)
                source.status = SourceStatus.STOPPED
                source.error_message = "تم إيقاف الفهرسة"
                db.commit()
                return {"source_id": source_id, "status": str(SourceStatus.STOPPED)}

            try:
                processed_source = process_knowledge_source(db, s_uuid)
                return {"source_id": str(processed_source.id), "status": str(processed_source.status)}
            except OperationCancelledError:
                logger.info("Indexing cancelled cooperatively for source %s", source_id)
                source.status = SourceStatus.STOPPED
                source.error_message = "تم إيقاف الفهرسة"
                db.commit()
                return {"source_id": source_id, "status": str(SourceStatus.STOPPED)}
            except Exception as exc:
                logger.exception("Error indexing source %s: %s", source_id, str(exc).split(":")[0])
                source.status = SourceStatus.FAILED
                source.error_message = str(exc).split(":")[0][:255]
                db.commit()
                raise
    finally:
        mark_parser_inactive(s_uuid)
