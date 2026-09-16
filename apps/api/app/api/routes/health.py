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
    import os
    settings = get_settings()
    from app.core.storage import get_storage_provider
    storage = get_storage_provider()
    storage_check = storage.check_readiness()

    dependencies: dict[str, str] = {
        "database": "ok",
        "redis": "unavailable",
        "storage": str(storage_check["status"]),
        "celery_broker": "unavailable",
        "celery_worker": "unavailable",
        "ingestion_dispatcher": "unavailable",
    }
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
        pass

    if settings.ingestion_backend == "celery":
        broker_url = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", settings.redis_url))
        broker_ok = False
        try:
            import redis

            if broker_url.startswith("redis://") or broker_url.startswith("rediss://"):
                redis.Redis.from_url(broker_url, socket_connect_timeout=0.3).ping()
                broker_ok = True
            else:
                from app.tasks.celery_app import celery_app
                with celery_app.connection_for_read() as conn:
                    conn.ensure_connection(max_retries=1)
                    broker_ok = True
        except Exception:
            broker_ok = False

        dependencies["celery_broker"] = "ok" if broker_ok else "unavailable"

        worker_ok = False
        if broker_ok:
            try:
                from app.tasks.celery_app import celery_app
                insp = celery_app.control.inspect(timeout=0.3)
                replies = insp.ping() if insp else None
                if replies and any(replies.values()):
                    worker_ok = True
            except Exception:
                worker_ok = False

        dependencies["celery_worker"] = "ok" if worker_ok else "unavailable"
        dependencies["ingestion_dispatcher"] = "ok" if (broker_ok and worker_ok) else "unavailable"
    elif settings.allow_local_ingestion:
        dependencies["celery_broker"] = "not_configured"
        dependencies["celery_worker"] = "not_configured"
        dependencies["ingestion_dispatcher"] = "ok"
    else:
        dependencies["celery_broker"] = "not_configured"
        dependencies["celery_worker"] = "not_configured"
        dependencies["ingestion_dispatcher"] = "unavailable"

    # In production and production_like, all core services (DB, Storage, Ingestion) must be healthy
    is_prod_like = settings.app_env.lower() in {"production", "production_like"}
    if is_prod_like:
        critical_deps = [
            dependencies["database"],
            dependencies["storage"],
            dependencies["ingestion_dispatcher"],
        ]
        if settings.redis_required:
            critical_deps.append(dependencies["redis"])

        if any(d != "ok" for d in critical_deps):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Required production dependencies are unavailable",
                    "dependencies": dependencies,
                },
            )
    elif settings.redis_required and dependencies["redis"] != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Required dependencies are unavailable",
                "dependencies": dependencies,
            },
        )

    all_ok = all(
        v == "ok"
        for v in dependencies.values()
        if v != "not_configured"
    )
    overall_status = "ready" if all_ok else "degraded"

    return ReadinessResponse(
        status=overall_status,
        service=settings.app_name,
        environment=settings.app_env,
        dependencies=dependencies,
    )
