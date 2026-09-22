from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine

pytest.importorskip(
    "psycopg",
    reason="Postgres integration test requires the psycopg driver (pip install 'psycopg[binary]')",
)


def test_source_advisory_lock_is_connection_scoped(monkeypatch) -> None:
    """Two PostgreSQL connections contend; release must happen on the owner."""
    from app.tasks import knowledge_ingestion

    dsn = os.getenv(
        "TEST_POSTGRES_DSN",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5434/chemistry_fresh_test",
    )
    postgres_engine = create_engine(dsn, pool_pre_ping=True)
    monkeypatch.setattr(knowledge_ingestion, "engine", postgres_engine)

    source_id = uuid.uuid4()
    first = knowledge_ingestion.SourceAdvisoryLock(source_id)
    second = knowledge_ingestion.SourceAdvisoryLock(source_id)
    third = knowledge_ingestion.SourceAdvisoryLock(source_id)
    try:
        assert first.acquire() is True
        assert second.acquire() is False
        first.release()
        assert third.acquire() is True
    finally:
        third.release()
        second.release()
        first.release()
        postgres_engine.dispose()
