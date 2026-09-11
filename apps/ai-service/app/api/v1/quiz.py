from typing import Union
from fastapi import APIRouter, Depends, Header, Request, Response, status
from app.core.security import verify_api_key
from app.schemas.common import AsyncTaskResponse
from app.schemas.quiz import QuizDraftResponse, QuizGenerationRequest
from app.services.quiz_service import quiz_service
from app.tasks.background_jobs import task_batch_generate_quiz
from app.traffic.rate_limiter import rate_limiter

router = APIRouter(prefix="/quiz", tags=["Quiz Generation"])


@router.post(
    "/draft",
    response_model=Union[QuizDraftResponse, AsyncTaskResponse],
    dependencies=[Depends(verify_api_key)]
)
async def generate_quiz_draft(
    request_data: QuizGenerationRequest,
    request: Request,
    response: Response,
    x_cache_bypass: bool = Header(False, alias="X-Cache-Bypass")
) -> Union[QuizDraftResponse, AsyncTaskResponse]:
    """
    Generates structured, validated draft assessment questions based on lesson texts.
    If async_mode=True, dispatches to Celery and returns HTTP 202 Accepted with task_id.
    """
    client_ip = request.client.host if request.client else "unknown_client"
    await rate_limiter.check_rate_limit(f"quiz:{client_ip}")

    # Asynchronous heavy batch path
    if request_data.async_mode:
        task = task_batch_generate_quiz.delay(request_data.model_dump())
        response.status_code = status.HTTP_202_ACCEPTED
        return AsyncTaskResponse(
            task_id=task.id,
            status="queued"
        )

    # Synchronous interactive generation
    res = await quiz_service.generate_quiz_draft(
        request=request_data,
        bypass_cache=x_cache_bypass
    )

    if res.cached:
        request.state.cache_hit = True

    return res
