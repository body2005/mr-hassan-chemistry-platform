import os
import re
import secrets
import time
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.metrics import record_request
from app.core.rate_limit import enforce_rate_limit

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Resume interrupted indexing tasks with centralized dispatch."""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, or_, and_
    from app.core.database import SessionLocal
    from app.models.knowledge_center import KnowledgeSource, SourceStatus
    from app.services.knowledge_center_service import dispatch_source_processing

    try:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        with SessionLocal() as db:
            stmt = (
                select(KnowledgeSource.id)
                .where(
                    or_(
                        KnowledgeSource.status == SourceStatus.QUEUED,
                        and_(
                            KnowledgeSource.status == SourceStatus.PROCESSING,
                            KnowledgeSource.updated_at <= stale_cutoff,
                        ),
                    )
                )
            )
            candidate_ids = list(db.scalars(stmt).all())

        dispatched_count = 0
        for source_id in candidate_ids:
            with SessionLocal() as db:
                if dispatch_source_processing(db, source_id, is_startup=True):
                    dispatched_count += 1
        if candidate_ids:
            logger.info("Startup recovery: dispatched %s / %s eligible source(s)", dispatched_count, len(candidate_ids))
    except Exception:
        logger.exception("Unable to resume interrupted indexing tasks at startup")
    yield

app = FastAPI(
    title=settings.app_name,
    summary="LMS and AI services for Learning Website",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

from app.core.errors import install_error_handlers


def is_origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    if origin in settings.cors_origins:
        return True
    origin_regex = settings.cors_origin_regex
    return bool(origin_regex and re.fullmatch(origin_regex, origin))


def classify_rate_limit_category(method: str, path: str) -> str:
    """Classify each request once; source reads must never be charged as uploads."""
    normalized_method = method.upper()
    normalized_path = path.rstrip("/")
    api_prefix = settings.api_v1_prefix

    if normalized_path.startswith(f"{api_prefix}/auth/"):
        return "auth"
    if normalized_path.startswith(f"{api_prefix}/ai"):
        return "ai"
    if (
        "/preview-page/" in normalized_path
        or normalized_path.endswith("/preview-file")
        or normalized_path.endswith("/preview-token")
    ):
        return "preview"
    if normalized_method == "POST" and (
        normalized_path in {
            f"{api_prefix}/knowledge-center/sources/upload",
            f"{api_prefix}/knowledge-center/sources/upload-batch",
        }
        or normalized_path.endswith("/video")
        or normalized_path.endswith("/receipt")
    ):
        return "upload"
    if normalized_method == "POST" and (
        "extract-from-file" in normalized_path or "/exam" in normalized_path
    ):
        return "quiz_extraction"
    if normalized_method in {"PUT", "PATCH", "DELETE"} or normalized_path.endswith(
        ("/reindex", "/stop-indexing")
    ):
        return "mutation"
    if normalized_method in {"GET", "HEAD"}:
        return "read"
    return "default"


@app.middleware("http")
async def security_middleware(request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    origin = request.headers.get("Origin")
    unsafe_method = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    if request.url.path.startswith(settings.api_v1_prefix) and request.url.path not in {
        f"{settings.api_v1_prefix}/health",
        f"{settings.api_v1_prefix}/ready",
    }:
        try:
            category = classify_rate_limit_category(request.method, request.url.path)
            enforce_rate_limit(request, category=category)
            request.state.rate_limit_categories = {category}
        except HTTPException as exc:
            res = JSONResponse(
                status_code=exc.status_code,
                content={
                    "detail": str(exc.detail),
                    "error": {
                        "code": "RATE_LIMITED" if exc.status_code == 429 else "SERVICE_UNAVAILABLE",
                        "message": exc.detail,
                    },
                    "request_id": request_id,
                },
                headers=exc.headers or ({"Retry-After": "1"} if exc.status_code == 503 else None),
            )
            return res
    if unsafe_method and origin and not is_origin_allowed(origin):
        res = JSONResponse(
            status_code=403,
            content={
                "detail": "Origin is not allowed",
                "error": {"code": "FORBIDDEN", "message": "Origin is not allowed"},
                "request_id": request_id,
            },
        )
        return res
    # Cookie-authenticated mutations require an origin-bound double-submit
    # token. Login and password reset do not rely on an existing session.
    csrf_exempt_paths = {
        f"{settings.api_v1_prefix}/auth/login",
        f"{settings.api_v1_prefix}/auth/register",
        f"{settings.api_v1_prefix}/auth/password-reset/request",
        f"{settings.api_v1_prefix}/auth/password-reset/confirm",
    }
    if (
        unsafe_method
        and (
            request.cookies.get(settings.session_cookie_name)
            or request.cookies.get(settings.refresh_cookie_name)
        )
        and request.url.path not in csrf_exempt_paths
    ):
        csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_cookie or not secrets.compare_digest(csrf_cookie, csrf_header or ""):
            res = JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF validation failed",
                    "error": {"code": "FORBIDDEN", "message": "CSRF validation failed"},
                    "request_id": request_id,
                },
            )
            return res

    if request.method == "POST" and request.url.path in {
        f"{settings.api_v1_prefix}/knowledge-center/sources/upload",
        f"{settings.api_v1_prefix}/knowledge-center/sources/upload-batch",
    }:
        content_length_header = request.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                maximum_http_body = (
                    settings.max_request_size_mb + settings.multipart_overhead_mb
                ) * 1024 * 1024
                if content_length > maximum_http_body:
                    res = JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request size exceeds the {settings.max_request_size_mb} MB limit",
                            },
                            "request_id": request_id,
                        },
                    )
                    return res
            except (ValueError, TypeError):
                pass

    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled error processing request %s: %s", request_id, exc)
        err_res = JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An internal server error occurred"}, "request_id": request_id},
        )
        return err_res

    record_request(
        request.url.path,
        request.method,
        response.status_code,
        int((time.perf_counter() - started) * 1000),
    )
    response.headers["X-Request-ID"] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.secure_cookies:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'self'"

    return response


# Register CORS after the custom middleware so it is the outermost layer.  It
# must be the single source of CORS headers; manually writing a wildcard
# Access-Control-Allow-Headers breaks credentialed Authorization preflights.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
        "Origin",
        "X-CSRF-Token",
        "X-Request-ID",
        "X-Requested-With",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,
)


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.include_router(api_router, prefix=settings.api_v1_prefix)
install_error_handlers(app)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}
