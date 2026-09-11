from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import verify_api_key
from app.schemas.common import AsyncTaskResponse
from app.tasks.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["Asynchronous Background Jobs"])


@router.get("/{task_id}", response_model=AsyncTaskResponse, dependencies=[Depends(verify_api_key)])
async def get_task_status(task_id: str) -> AsyncTaskResponse:
    """
    Polls status and retrieves result for queued background jobs (batch quiz, batch grading, report generation).
    """
    try:
        async_result = AsyncResult(task_id, app=celery_app)
        state = async_result.state

        if state == "SUCCESS":
            return AsyncTaskResponse(
                task_id=task_id,
                status="completed",
                result=async_result.result,
                error=None
            )
        elif state == "FAILURE":
            return AsyncTaskResponse(
                task_id=task_id,
                status="failed",
                result=None,
                error=str(async_result.result)
            )
        elif state in ["STARTED", "PROGRESS"]:
            return AsyncTaskResponse(
                task_id=task_id,
                status="in_progress",
                result=None,
                error=None
            )
        else:  # PENDING, RECEIVED, etc.
            return AsyncTaskResponse(
                task_id=task_id,
                status="queued",
                result=None,
                error=None
            )
    except Exception as e:
        return AsyncTaskResponse(
            task_id=task_id,
            status="failed",
            result=None,
            error=f"Error inspecting task: {str(e)}"
        )
