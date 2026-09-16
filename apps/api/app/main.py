import os
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
    """Resume interrupted indexing without using deprecated startup events."""
    from sqlalchemy import select
    from app.api.routes.knowledge_center import _LOCAL_INGEST_EXECUTOR, _run_bg_process_source
    from app.core.database import SessionLocal
    from app.models.knowledge_center import KnowledgeSource, SourceStatus

    try:
        with SessionLocal() as db:
            interrupted_ids = list(
                db.scalars(
                    select(KnowledgeSource.id).where(
                        KnowledgeSource.status.in_([SourceStatus.PROCESSING, SourceStatus.QUEUED])
                    )
                ).all()
            )
        for source_id in interrupted_ids:
            _LOCAL_INGEST_EXECUTOR.submit(_run_bg_process_source, source_id)
        if interrupted_ids:
            logger.info("Queued %s interrupted indexing task(s) for resume", len(interrupted_ids))
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


@app.middleware("http")
async def security_middleware(request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    origin = request.headers.get("Origin")
    unsafe_method = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    authorization = request.headers.get("Authorization", "")
    has_bearer_auth = authorization.lower().startswith("bearer ") and bool(
        authorization[7:].strip()
    )
    if request.url.path.startswith(settings.api_v1_prefix) and request.url.path not in {
        f"{settings.api_v1_prefix}/health",
        f"{settings.api_v1_prefix}/ready",
    }:
        try:
            path = request.url.path
            if path.startswith(f"{settings.api_v1_prefix}/auth/login"):
                category = "auth_login"
            elif "/ai" in path:
                category = "ai"
            elif "/upload" in path or "/sources" in path:
                category = "upload"
            elif "/quiz" in path or "/exam" in path or "/extract" in path:
                category = "quiz_extraction"
            elif request.method == "GET":
                category = "read"
            else:
                category = "default"

            enforce_rate_limit(request, category=category)
        except HTTPException as exc:
            res = JSONResponse(
                status_code=exc.status_code,
                content={
                    "detail": str(exc.detail),
                    "error": {"code": "RATE_LIMITED", "message": exc.detail},
                    "request_id": request_id,
                },
                headers=exc.headers,
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
    # Double-submit CSRF applies only to cookie-authenticated mutations.  The
    # cross-origin SPA cannot read a cookie scoped to the Render API domain,
    # and an explicit Bearer token is already protected from ambient CSRF.
    if (
        unsafe_method
        and origin
        and request.cookies.get(settings.session_cookie_name)
        and not has_bearer_auth
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
