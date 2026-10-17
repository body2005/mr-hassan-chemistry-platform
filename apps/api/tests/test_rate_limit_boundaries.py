"""Real Redis boundary/race tests; conftest restricts these to isolated DB 15."""
import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException, Request

from app.core import concurrency, rate_limit
from app.core.config import Settings, get_settings


def request():
    return Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [],
                    'client': ('192.0.2.190', 1)})


@pytest.fixture
def store(monkeypatch):
    monkeypatch.delenv('DISABLE_RATE_LIMITING', raising=False)
    client = rate_limit._get_redis_client()
    assert client is not None and client.ping(), 'Requires the isolated QA Redis on DB 15'
    return client


@pytest.mark.parametrize(('category', 'field', 'expected'), [
    ('auth', 'rate_limit_login', 10),
    ('read', 'rate_limit_read', 300),
    ('video_stream', 'rate_limit_video_stream', 600),
    ('upload', 'rate_limit_upload', 20),
    ('quiz_extraction', 'rate_limit_quiz_extraction', 10),
    ('pdf_render', 'rate_limit_pdf_render', 30),
    ('heavy_query', 'rate_limit_heavy_query', 20),
    ('default', 'rate_limit_api_default', 300),
])
def test_configured_default_boundary_and_positive_retry_after(store, monkeypatch, category, field, expected):
    # Test repository defaults explicitly, independently of developer .env overrides.
    assert Settings.model_fields[field].default == expected
    settings = get_settings()
    monkeypatch.setattr(settings, field, expected)
    monkeypatch.setattr(settings, 'rate_limit_window_seconds', 60)
    identity = 'boundary-' + uuid.uuid4().hex
    for _ in range(expected):
        rate_limit.enforce_rate_limit(request(), category=category, identity=identity)
    with pytest.raises(HTTPException) as denied:
        rate_limit.enforce_rate_limit(request(), category=category, identity=identity)
    assert denied.value.status_code == 429
    assert 1 <= int(denied.value.headers['Retry-After']) <= 60
    # An exhausted actor must not block a different actor or a different category.
    rate_limit.enforce_rate_limit(request(), category=category, identity=identity + '-other')
    rate_limit.enforce_rate_limit(request(), category='independent_category', identity=identity)


def test_parallel_requests_cannot_race_past_shared_redis_budget(store):
    identity = 'race-' + uuid.uuid4().hex

    def send(_):
        try:
            rate_limit.enforce_rate_limit(request(), category='race', limit=20, window_seconds=60, identity=identity)
            return 200
        except HTTPException as exc:
            assert int(exc.headers['Retry-After']) > 0
            return exc.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(send, range(32)))
    assert statuses.count(200) == 20
    assert statuses.count(429) == 12


def test_real_redis_window_expires_without_counter_reset(store):
    identity = 'expiry-' + uuid.uuid4().hex
    rate_limit.enforce_rate_limit(request(), category='expiry', limit=1, window_seconds=1, identity=identity)
    with pytest.raises(HTTPException) as denied:
        rate_limit.enforce_rate_limit(request(), category='expiry', limit=1, window_seconds=1, identity=identity)
    assert denied.value.status_code == 429
    time.sleep(1.1)
    rate_limit.enforce_rate_limit(request(), category='expiry', limit=1, window_seconds=1, identity=identity)


@pytest.mark.parametrize(('pool', 'capacity'), [('client', 20), ('realtime', 5), ('video', 8)])
def test_distributed_concurrent_slots_reject_then_release(store, monkeypatch, pool, capacity):
    monkeypatch.setattr(concurrency, '_resolve_concurrency_key', lambda _: 'qa-' + pool)

    async def exercise():
        guards = []
        try:
            for _ in range(capacity):
                guard = concurrency.concurrency_guard(request(), pool=pool)
                await guard.__aenter__()
                guards.append(guard)
            assert store.zcard(f'admission:{pool}:qa-{pool}') == capacity
            with pytest.raises(HTTPException) as denied:
                async with concurrency.concurrency_guard(request(), pool=pool):
                    pytest.fail('Excess concurrent request was admitted')
            assert denied.value.status_code == 429
            assert int(denied.value.headers['Retry-After']) > 0
            await guards.pop().__aexit__(None, None, None)
            async with concurrency.concurrency_guard(request(), pool=pool):
                assert store.zcard(f'admission:{pool}:qa-{pool}') == capacity
        finally:
            for guard in guards:
                await guard.__aexit__(None, None, None)
        assert store.zcard(f'admission:{pool}:qa-{pool}') == 0

    asyncio.run(exercise())
