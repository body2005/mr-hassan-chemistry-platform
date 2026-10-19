import asyncio
import threading
import time

import anyio
import httpx
from fastapi import Depends, FastAPI

from app.core import database


def test_auth_endpoint_handoff_does_not_exhaust_threads(monkeypatch):
    """More requests than both pools must finish without checkout starvation."""
    connections = threading.BoundedSemaphore(2)
    held = set()

    class Session:
        def __init__(self):
            self.info = {}

        def authenticate(self):
            assert connections.acquire(timeout=1), 'DB checkout starved behind pending endpoints'
            held.add(self)
            time.sleep(.002)

        def close(self):
            if self in held:
                held.remove(self)
                connections.release()

    monkeypatch.setattr(database, 'SessionLocal', Session)
    monkeypatch.setattr(database.settings, 'db_pool_size', 2)
    app = FastAPI()

    def auth(db=Depends(database.get_db)):
        db.authenticate()

    @app.get('/')
    def endpoint(actor=Depends(auth)):
        time.sleep(.002)
        return {'ok': True}

    async def run():
        limiter = anyio.to_thread.current_default_thread_limiter()
        previous = limiter.total_tokens
        limiter.total_tokens = 4
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
                responses = await asyncio.wait_for(asyncio.gather(*(client.get('/') for _ in range(40))), 5)
            assert all(r.status_code == 200 for r in responses)
            assert not held
        finally:
            limiter.total_tokens = previous

    asyncio.run(run())


def test_early_stream_release_returns_admission_slot_once(monkeypatch):
    async def run():
        from unittest.mock import MagicMock
        db = MagicMock(info={})
        releases = []
        db.info['request_db_slot'] = lambda: releases.append(True)
        await database.close_request_session(db)
        await database.close_request_session(db)
        assert releases == [True]
        assert 'request_db_slot' not in db.info
    asyncio.run(run())


def test_sync_media_close_returns_slot_on_owning_loop():
    async def run():
        loop = asyncio.get_running_loop()
        slots = asyncio.Semaphore(1)
        await slots.acquire()
        session = database.RequestSession()
        session.info['request_db_slot'] = lambda: loop.call_soon_threadsafe(slots.release)
        await asyncio.to_thread(session.close)
        await asyncio.wait_for(slots.acquire(), .1)
        # Dependency cleanup cannot release a second time after media close.
        await database.close_request_session(session)
        assert slots.locked()
    asyncio.run(run())


def test_database_admission_wait_has_deadline(monkeypatch):
    from fastapi import HTTPException
    import pytest
    monkeypatch.setattr(database.settings, 'db_pool_timeout_seconds', .01)

    async def run():
        loop = asyncio.get_running_loop()
        loop._chemistry_request_db_slots = asyncio.Semaphore(0)
        dependency = database.get_db()
        with pytest.raises(HTTPException) as failure:
            await anext(dependency)
        assert failure.value.status_code == 503
        assert failure.value.headers == {'Retry-After': '2'}
    asyncio.run(run())
