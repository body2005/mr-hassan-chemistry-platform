import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.config import get_settings
from app.main import app
from app.traffic.cache import request_cache


@pytest.fixture(autouse=True)
def override_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("DEFAULT_PROVIDER", "mock")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("SEMAPHORE_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "10")
    
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def clear_test_cache():
    await request_cache.clear()
    yield
    await request_cache.clear()
