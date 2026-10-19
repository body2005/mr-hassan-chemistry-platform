from collections.abc import AsyncGenerator
import asyncio
import os

import anyio
from fastapi import HTTPException

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.pool import QueuePool
from app.core.performance import measure, install_sql_timings


class TimedQueuePool(QueuePool):
    def _do_get(self):
        # Includes pool wait and opening a new connection, separately from SQL.
        with measure('db_pool_acquire_ms'):
            return super()._do_get()

from app.core.config import get_settings

settings = get_settings()

engine_options: dict[str, object] = {"pool_pre_ping": True}
database_url = settings.sqlalchemy_database_url

if database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False, "timeout": 15}
    if os.getenv("APP_ENV") == "test":
        engine_options["poolclass"] = StaticPool
else:
    engine_options.update(
        poolclass=TimedQueuePool,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
    )
    engine_options["connect_args"] = {"connect_timeout": 5}

engine = create_engine(database_url, **engine_options)
install_sql_timings(engine)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA busy_timeout = 10000")
        cursor.close()


class RequestSession(Session):
    def close(self):
        try:
            super().close()
        finally:
            release = self.info.pop('request_db_slot', None)
            if release is not None:
                release()


SessionLocal = sessionmaker(bind=engine, class_=RequestSession, autoflush=False, expire_on_commit=False)


async def close_request_session(session: Session) -> None:
    """Return the connection and its admission slot, including on disconnect.

    Cleanup uses an independent thread limiter: it must not queue behind work
    waiting to acquire the very connections that cleanup is returning.
    """
    with anyio.CancelScope(shield=True):
        await anyio.to_thread.run_sync(session.close, limiter=anyio.CapacityLimiter(1))
        session.info.pop("verified_database_actor", None)
        release = session.info.pop("request_db_slot", None)
        if release is not None:
            release()


async def get_db() -> AsyncGenerator[Session, None]:
    # Sync auth dependencies and sync endpoints share AnyIO's thread pool.
    # Blocking on SQLAlchemy checkout there can occupy every thread while an
    # already-authenticated request holds a connection awaiting its endpoint.
    # Queue requests asynchronously before auth. Use the existing DB capacity,
    # but reserve at least half of AnyIO's threads for endpoint/cleanup handoff.
    loop = asyncio.get_running_loop()
    # Store it on its owning loop, rather than retaining closed test loops in a
    # module-level map through the semaphore's reference back to the loop.
    slots = getattr(loop, '_chemistry_request_db_slots', None)
    if slots is None:
        thread_budget = int(anyio.to_thread.current_default_thread_limiter().total_tokens)
        db_capacity = settings.db_pool_size + settings.db_max_overflow
        slots = asyncio.Semaphore(max(1, min(db_capacity, thread_budget // 2)))
        loop._chemistry_request_db_slots = slots
    with measure('db_request_queue_ms'):
        try:
            await asyncio.wait_for(slots.acquire(), timeout=settings.db_pool_timeout_seconds)
        except TimeoutError as exc:
            raise HTTPException(503, 'Database request capacity temporarily unavailable',
                                headers={'Retry-After': '2'}) from exc
    try:
        session = SessionLocal()
    except BaseException:
        slots.release()
        raise
    # close() is also used directly by existing synchronous media endpoints.
    # Always return the slot on its own event loop, once, from either thread.
    session.info['request_db_slot'] = lambda: loop.call_soon_threadsafe(slots.release)
    try:
        yield session
    finally:
        await close_request_session(session)
