from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_roles
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.user import User, UserRole
from app.schemas import AIInvocationRequest, AIInvocationResponse
from app.services import ai_service
from app.services.ai_access_policy import enforce_ai_access

router = APIRouter(prefix="/ai")
Db = Annotated[Session, Depends(get_db)]
Manager = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]


@router.post("/invocations", response_model=AIInvocationResponse, status_code=201)
def invoke_ai(
    payload: AIInvocationRequest, user: CurrentUser, db: Db, request: Request
) -> AIInvocationResponse:
    enforce_rate_limit(request, bucket="ai", limit=30, window_seconds=60)
    enforce_ai_access(db, user, request, {"task": payload.task})
    try:
        invocation = ai_service.invoke(db, user, payload)
    except ai_service.AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return AIInvocationResponse.model_validate(invocation)


@router.post("/invocations/{invocation_id}/approve", response_model=AIInvocationResponse)
def approve_ai(invocation_id: uuid.UUID, user: Manager, db: Db) -> AIInvocationResponse:
    try:
        invocation = ai_service.approve(db, user, invocation_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AIInvocationResponse.model_validate(invocation)
