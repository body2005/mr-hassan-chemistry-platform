from fastapi import APIRouter, Depends, Header, Request
from app.core.security import verify_api_key
from app.schemas.reports import (
    ReportNarrativeRequest,
    ReportNarrativeResponse,
)
from app.services.report_service import report_service
from app.traffic.rate_limiter import rate_limiter

router = APIRouter(prefix="/reports", tags=["Course Report Narrative Synthesis"])


@router.post("/narrative", response_model=ReportNarrativeResponse, dependencies=[Depends(verify_api_key)])
async def generate_report_narrative(
    request_data: ReportNarrativeRequest,
    request: Request,
    x_cache_bypass: bool = Header(False, alias="X-Cache-Bypass")
) -> ReportNarrativeResponse:
    """
    Generates structured narrative prose for institutional course reports.
    """
    client_ip = request.client.host if request.client else "unknown_client"
    await rate_limiter.check_rate_limit(f"reports:{client_ip}", limit=20, window_seconds=60)

    response = await report_service.generate_report_narrative(
        request=request_data,
        bypass_cache=x_cache_bypass
    )

    if response.cached:
        request.state.cache_hit = True

    return response
