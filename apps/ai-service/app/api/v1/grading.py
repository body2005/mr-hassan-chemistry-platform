from fastapi import APIRouter, Depends, Header, Request
from app.core.exceptions import UnsupportedGradingTypeException
from app.core.security import verify_api_key
from app.schemas.grading import OBJECTIVE_QUESTION_TYPES, EssayGradingRequest, EssayGradingResponse
from app.services.grading_service import grading_service
from app.traffic.rate_limiter import rate_limiter

router = APIRouter(prefix="/grading", tags=["Rubric Essay Grading"])


@router.post("/essay", response_model=EssayGradingResponse, dependencies=[Depends(verify_api_key)])
async def grade_essay(
    request_data: EssayGradingRequest,
    request: Request,
    x_cache_bypass: bool = Header(False, alias="X-Cache-Bypass")
) -> EssayGradingResponse:
    """
    Grades a subjective student essay against a rubric and maximum score.
    Returns per-criterion score breakdown, concise feedback, and confidence signals.
    Rejects objective question types with HTTP 400.
    """
    # Strict validation against objective questions
    if request_data.question_type.lower().strip() in OBJECTIVE_QUESTION_TYPES:
        raise UnsupportedGradingTypeException(request_data.question_type)

    client_ip = request.client.host if request.client else "unknown_client"
    await rate_limiter.check_rate_limit(f"grading:{client_ip}")

    response = await grading_service.grade_essay(
        request=request_data,
        bypass_cache=x_cache_bypass
    )

    if response.cached:
        request.state.cache_hit = True

    return response
