import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_system_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["provider"]["name"] == "mock"
    assert data["provider"]["healthy"] is True


@pytest.mark.asyncio
async def test_system_metrics_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/system/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "requests" in data
    assert "cache" in data
    assert "tokens" in data
    assert "resource_load" in data
    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_cache_clear_endpoint(async_client: AsyncClient):
    response = await async_client.post("/api/v1/system/cache/clear")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
