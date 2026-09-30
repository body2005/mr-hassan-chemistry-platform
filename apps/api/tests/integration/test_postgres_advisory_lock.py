"""Real PostgreSQL ownership contract; removed indexing wrapper is not silently skipped."""
from sqlalchemy import text
import uuid
from .live_helpers import pg_engine


def test_source_advisory_lock_is_connection_scoped():
    engine = pg_engine()
    key = uuid.uuid4().int % (2**63 - 1)
    try:
        with engine.connect() as first, engine.connect() as second:
            assert first.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            assert not second.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            assert not second.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            assert first.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            assert second.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            assert second.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    finally:
        engine.dispose()
