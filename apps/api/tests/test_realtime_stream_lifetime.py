import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.core import events


def test_stream_deadline_releases_both_idle_and_busy_subscriptions(monkeypatch):
    async def exercise(busy):
        now = [100.0]
        monkeypatch.setattr(events, 'monotonic', lambda: now[0])
        unregister = AsyncMock()
        monkeypatch.setattr(events.event_broker, 'unregister', unregister)
        sub = events.EventSubscription(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 'student',
                                       asyncio.Queue(), datetime.now(timezone.utc), asyncio.get_running_loop())
        stream = events.sse_event_generator(sub)
        assert 'event: connected' in await anext(stream)

        async def queue_wait(awaitable, timeout):
            awaitable.close()
            assert timeout == 1.0  # No heartbeat may extend the deadline.
            now[0] += timeout
            if busy:
                return {'type': 'notification_created', 'data': {'title': 'Late hint'}}
            raise asyncio.TimeoutError

        monkeypatch.setattr(events.asyncio, 'wait_for', queue_wait)
        now[0] = 100.0 + events.SSE_MAX_CONNECTION_SECONDS - 1
        assert [item async for item in stream] == []
        unregister.assert_awaited_once_with(sub.id)

    asyncio.run(exercise(False))
    asyncio.run(exercise(True))


def test_client_close_and_revoked_session_still_release_subscription(monkeypatch):
    async def exercise(revoked):
        unregister = AsyncMock()
        monkeypatch.setattr(events.event_broker, 'unregister', unregister)
        sub = events.EventSubscription(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 'student',
                                       asyncio.Queue(), datetime.now(timezone.utc), asyncio.get_running_loop())
        stream = events.sse_event_generator(sub, lambda: False)
        await anext(stream)
        if revoked:
            await sub.queue.put({'type': 'notification_created', 'data': {}})
            assert [item async for item in stream] == []
        else:
            await stream.aclose()
        unregister.assert_awaited_once_with(sub.id)

    asyncio.run(exercise(False))
    asyncio.run(exercise(True))
