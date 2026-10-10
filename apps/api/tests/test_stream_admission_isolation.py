import asyncio
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException, Request
from starlette.requests import ClientDisconnect
from app.core import concurrency
from app.api.routes.realtime import RealtimeResponse


def test_busy_streams_do_not_exhaust_login_and_quiz_slots(monkeypatch):
    monkeypatch.delenv('DISABLE_RATE_LIMITING', raising=False)
    monkeypatch.setattr(concurrency.ResourceLease, 'acquire', AsyncMock(return_value=False))
    request = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [], 'client': ('192.0.2.15', 1)})

    async def exercise():
        guards = [concurrency.concurrency_guard(request, pool='video') for _ in range(8)]
        try:
            for guard in guards:
                await guard.__aenter__()
            with pytest.raises(HTTPException) as denied:
                async with concurrency.concurrency_guard(request, pool='video'):
                    pass
            assert denied.value.status_code == 429
            async with concurrency.concurrency_guard(request):
                assert concurrency.get_concurrency_stats()['total_in_flight'] == 9
        finally:
            for guard in guards:
                await guard.__aexit__(None, None, None)
        assert concurrency.get_concurrency_stats()['total_in_flight'] == 0
    asyncio.run(exercise())


def test_realtime_releases_subscription_when_headers_fail(monkeypatch):
    cleanup = AsyncMock()
    monkeypatch.setattr('app.api.routes.realtime.event_broker.unregister', cleanup)
    started = []
    async def body():
        started.append(True)
        yield 'data: test\n\n'
    async def send(_):
        raise OSError('client disconnected before headers')
    async def receive():
        return {'type': 'http.disconnect'}
    response = RealtimeResponse(body(), subscription_id='test-sub', media_type='text/event-stream')
    with pytest.raises(ClientDisconnect):
        asyncio.run(response({'type': 'http', 'asgi': {'spec_version': '2.4'}}, receive, send))
    assert not started
    cleanup.assert_awaited_once_with('test-sub')
