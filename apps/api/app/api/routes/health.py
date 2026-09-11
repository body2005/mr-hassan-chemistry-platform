from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.metrics import render_metrics
from app.schemas import ReadinessResponse

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
    )


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check(db: Annotated[Session, Depends(get_db)]) -> ReadinessResponse:
    settings = get_settings()
    dependencies = {"database": "ok", "redis": "unavailable"}
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc

    try:
        import redis

        redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.2).ping()
        dependencies["redis"] = "ok"
    except Exception:
        # Redis is not required for the synchronous auth/course slice, but its state is visible.
        pass

    if settings.app_env == "production" and dependencies["redis"] != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Required dependencies are unavailable",
                "dependencies": dependencies,
            },
        )

    return ReadinessResponse(
        status="ready" if dependencies["redis"] == "ok" else "degraded",
        service=settings.app_name,
        environment=settings.app_env,
        dependencies=dependencies,
    )
