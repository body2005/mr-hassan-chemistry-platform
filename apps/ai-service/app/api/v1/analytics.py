from fastapi import APIRouter, Depends, Header, Request
from app.core.security import verify_api_key
from app.schemas.analytics import (
    AggregatedClassStatsRequest,
    AnalyticsInterpretationResponse,
)
from app.services.analytics_service import analytics_service
from app.traffic.rate_limiter import rate_limiter

router = APIRouter(prefix="/analytics", tags=["Class Analytics TA Interpretation"])


@router.post("/interpret", response_model=AnalyticsInterpretationResponse, dependencies=[Depends(verify_api_key)])
async def interpret_class_analytics(
    request_data: AggregatedClassStatsRequest,
    request: Request,
    x_cache_bypass: bool = Header(False, alias="X-Cache-Bypass")
) -> AnalyticsInterpretationResponse:
    """
    Transforms aggregated assessment and cohort stats into insightful TA pedagogical diagnostics.
    Identifies bottlenecks and recommends instructional fixes.
    """
    client_ip = request.client.host if request.client else "unknown_client"
    await rate_limiter.check_rate_limit(f"analytics:{client_ip}", limit=30, window_seconds=60)

    response = await analytics_service.interpret_statistics(
        request=request_data,
        bypass_cache=x_cache_bypass
    )

    if response.cached:
        request.state.cache_hit = True

    return response
