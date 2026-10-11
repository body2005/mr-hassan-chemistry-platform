from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.metrics import render_metrics
from app.schemas import ReadinessResponse
from app.api.dependencies import require_roles
from app.models.user import UserRole
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import threading
import time

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
def metrics(_monitor=Depends(require_roles(UserRole.PLATFORM_ADMIN))) -> Response:
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")


def _probe_readiness(db: Session) -> ReadinessResponse:
    import os
    settings = get_settings()
    from app.core.storage import get_storage_provider
    try:
        storage_check = get_storage_provider().check_readiness()
    except Exception:
        storage_check = {"status": "unavailable"}

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

        redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.2, socket_timeout=0.3).ping()
        dependencies["redis"] = "ok"
    except Exception:
        pass

    if settings.ingestion_backend == "celery":
        broker_url = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", settings.redis_url))
        broker_ok = False
        try:
            import redis

            if broker_url.startswith("redis://") or broker_url.startswith("rediss://"):
                redis.Redis.from_url(broker_url, socket_connect_timeout=0.3, socket_timeout=0.3).ping()
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
    is_prod_like = settings.deployment_environment
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

# One shared probe per API process, max one background connection/task, with a
# 2s HTTP wait budget and 5s cache. A slow dependency cannot grow a work queue.
_probe_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="readiness")
_probe_lock = threading.Lock()
_probe_future = None
_probe_cache = None


def _run_probe():
    with SessionLocal() as db:
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL statement_timeout = '1500ms'"))
        return _probe_readiness(db)


def _cached_readiness():
    global _probe_future, _probe_cache
    if get_settings().app_env in {"test", "testing"}:
        return _run_probe()
    with _probe_lock:
        if _probe_cache and time.monotonic() - _probe_cache[0] < 5:
            if isinstance(_probe_cache[1], Exception):
                raise _probe_cache[1]
            return _probe_cache[1]
        if _probe_future is None:
            _probe_future = _probe_executor.submit(_run_probe)
        future = _probe_future
    try:
        result = future.result(timeout=2)
    except TimeoutError:
        raise HTTPException(503, "Readiness temporarily unavailable")
    except Exception as error:
        # Negative readiness results are cached too. A fast failing dependency
        # must not turn a public probe storm into repeated expensive checks.
        with _probe_lock:
            _probe_cache = (time.monotonic(), error)
        raise
    finally:
        if future.done():
            with _probe_lock:
                if _probe_future is future:
                    _probe_future = None
    with _probe_lock:
        _probe_cache = (time.monotonic(), result)
    return result


@router.get("/ready")
def readiness_check():
    try:
        result = _cached_readiness()
    except Exception:
        # No dependency names/configuration/exception detail on the public probe.
        raise HTTPException(503, "Service is not ready")
    return {"status": result.status}


@router.get("/ready/details", response_model=ReadinessResponse, include_in_schema=False)
def readiness_details(_monitor=Depends(require_roles(UserRole.PLATFORM_ADMIN))):
    return _cached_readiness()
