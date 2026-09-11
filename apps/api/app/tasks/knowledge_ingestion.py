from __future__ import annotations

import uuid

from app.tasks.celery_app import celery_app


@celery_app.task(name="knowledge_center.index_source", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def index_source(self, source_id: str) -> dict[str, str]:
    from app.core.database import SessionLocal
    from app.services.knowledge_center_service import process_knowledge_source

    with SessionLocal() as db:
        source = process_knowledge_source(db, uuid.UUID(source_id))
        return {"source_id": str(source.id), "status": str(source.status)}
