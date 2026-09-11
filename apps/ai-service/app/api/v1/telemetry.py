from typing import Any, Dict
from fastapi import APIRouter, Depends, Header, HTTPException, status
from app.config import get_settings
from app.core.security import verify_api_key
from app.core.telemetry import telemetry
from app.providers.factory import get_ai_provider
from app.traffic.cache import request_cache

router = APIRouter(prefix="/system", tags=["System & Telemetry"])


@router.get("/metrics", response_model=Dict[str, Any], dependencies=[Depends(verify_api_key)])
async def get_system_metrics() -> Dict[str, Any]:
    """
    Returns real-time service observability metrics:
    - Request counts and error rates
    - Latency percentiles (p50, p95, p99, avg)
    - Token spend (prompt & completion)
    - Active local GPU/VRAM inference load
    - Cache hit & miss statistics
    """
    return telemetry.get_summary()


@router.get("/health", response_model=Dict[str, Any])
async def get_system_health() -> Dict[str, Any]:
    """
    Health check verifying AI Provider availability, cache, and system status.
    """
    settings = get_settings()
    provider = get_ai_provider()
    provider_health = await provider.health_check()

    redis_client = await request_cache.get_redis_client()
    redis_healthy = False
    if redis_client:
        try:
            redis_healthy = bool(await redis_client.ping())
        except Exception:
            redis_healthy = False

    is_overall_healthy = provider_health.is_healthy

    return {
        "status": "healthy" if is_overall_healthy else "degraded",
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "provider": {
            "name": provider_health.provider_name,
            "healthy": provider_health.is_healthy,
            "models": provider_health.available_models,
            "error": provider_health.error_message
        },
        "redis_connected": redis_healthy
    }


@router.post("/cache/clear", dependencies=[Depends(verify_api_key)])
async def clear_cache() -> Dict[str, str]:
    """
    Flushes the request cache.
    """
    await request_cache.clear()
    return {"status": "success", "message": "Cache successfully cleared."}
