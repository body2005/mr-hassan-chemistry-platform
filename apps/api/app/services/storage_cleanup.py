"""Commit the deletion intent with the DB mutation, delete bytes afterwards.

Jobs survive API restarts. Workers claim jobs with SKIP LOCKED, and retry
storage outages with bounded backoff. Logs contain job IDs, never object URLs.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.storage import LocalStorageProvider, S3StorageProvider, get_storage_provider
from app.models.storage_cleanup import StorageCleanup

logger = logging.getLogger(__name__)


def enqueue_cleanup(db: Session, key: str | None) -> None:
    if key and not key.startswith(("http://", "https://", "/api/")):
        db.add(StorageCleanup(object_key=key))


def _delete(key: str) -> None:
    if key.startswith("/static/uploads/"):
        upload_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "uploads"))
        storage = LocalStorageProvider(upload_dir)
        key = os.path.basename(key)
    else:
        storage = get_storage_provider()
    if isinstance(storage, S3StorageProvider):
        # SDK aborts may fail during an outage. A missing completed object
        # does not mean no multipart bytes exist: retire them before acking
        # the durable intent. Storage errors keep the job pending.
        storage.abort_incomplete_uploads(key)
    if storage.exists(key) and not storage.delete(key):
        raise RuntimeError("Storage deletion was not acknowledged")


def compensate_upload(db: Session, key: str) -> None:
    """Call after rollback. Persist retry intent even if immediate cleanup fails."""
    enqueue_cleanup(db, key)
    db.commit()
    drain_cleanup()


def drain_cleanup(batch_size: int = 25) -> int:
    done = 0
    for _ in range(batch_size):
        with SessionLocal() as db:
            job = db.scalar(select(StorageCleanup).where(StorageCleanup.retry_at <= datetime.now(timezone.utc))
                            .order_by(StorageCleanup.retry_at).with_for_update(skip_locked=True).limit(1))
            if job is None:
                break
            try:
                _delete(job.object_key)
            except Exception:
                job.attempts += 1
                job.retry_at = datetime.now(timezone.utc) + timedelta(seconds=min(3600, 5 * 2 ** min(job.attempts, 10)))
                logger.warning("Storage cleanup deferred: job=%s attempt=%d", job.id, job.attempts)
            else:
                db.delete(job)
                done += 1
            db.commit()
    return done


async def cleanup_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(drain_cleanup)
        except Exception:
            logger.warning("Storage cleanup database temporarily unavailable")
        await asyncio.sleep(15)
