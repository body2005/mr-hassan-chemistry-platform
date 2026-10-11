import os
import asyncio
from contextlib import suppress
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
from app.core.access_log import RedactAccessTokenFilter
from app.core.concurrency import AdmissionMiddleware
from app.core.config import get_settings
from app.core.database import engine
from app.core.metrics import record_request
from app.core.upload_limits import UploadBudgetMiddleware
from app.core.upload_auth import UploadAuthenticationMiddleware
from app.core.rate_limit import enforce_rate_limit
from app.core.response_security import ResponseSecurityHeadersMiddleware

settings = get_settings()
logger = logging.getLogger(__name__)
logging.getLogger("uvicorn.access").addFilter(RedactAccessTokenFilter())


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan (indexing recovery removed with the Knowledge Center)."""
    from app.services.storage_cleanup import cleanup_loop
    from app.services.session_maintenance import maintenance_loop
    from app.core.events import event_broker
    await event_broker.start()
    # Every persistent runtime can enqueue deletion intents. TestClient unit
    # databases alone opt out; production_like must not accumulate dead jobs.
    cleanup_task = asyncio.create_task(cleanup_loop()) if settings.app_env.lower() != "test" else None
    maintenance_task = asyncio.create_task(maintenance_loop()) if settings.app_env.lower() != "test" else None
    try:
        yield
    finally:
        await event_broker.stop()
        if cleanup_task:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task
        if maintenance_task:
            maintenance_task.cancel()
            with suppress(asyncio.CancelledError):
                await maintenance_task


app = FastAPI(
    title=settings.app_name,
    summary="Learning management and local document extraction",
    version="0.1.0",
    docs_url="/docs" if not settings.deployment_environment else None,
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

    # Profile and avatar reads are not credential operations. Charging every
    # reload/image request to the login budget can block a legitimate logout
    # or re-login. Keep the existing read budget and ALL credential mutation
    # limits; only these authenticated read-only routes change category.
    if normalized_method in {"GET", "HEAD"} and normalized_path in {
        f"{api_prefix}/auth/me", f"{api_prefix}/auth/profile-summary", f"{api_prefix}/auth/avatar",
    }:
        return "read"
    if normalized_path == f"{api_prefix}/auth/refresh":
        return "session_refresh"
    if normalized_path == f"{api_prefix}/auth/logout":
        return "session_logout"
    if normalized_path.startswith(f"{api_prefix}/auth/"):
        return "auth"
    if (
        "/preview-page/" in normalized_path
        or normalized_path.endswith("/preview-file")
        or normalized_path.endswith("/preview-token")
    ):
        return "preview"
    if normalized_method == "POST" and (
        normalized_path.endswith("/video")
        or normalized_path.endswith("/receipt")
        or normalized_path.endswith("/materials")
        or ("/assignments/" in normalized_path and normalized_path.endswith("/submissions/file"))
    ):
        return "upload"
    if normalized_method == "POST" and (
        "extract-from-file" in normalized_path or "/exam" in normalized_path
    ):
        return "quiz_extraction"
    if (
        f"{api_prefix}/submissions" in normalized_path
        or f"{api_prefix}/analytics" in normalized_path
        or f"{api_prefix}/payments/orders" in normalized_path
        or f"{api_prefix}/users" in normalized_path
        or "/reports/" in normalized_path
    ):
        return "heavy_query"
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
    category = "default"
    if request.url.path.startswith(settings.api_v1_prefix) and request.url.path not in {
        f"{settings.api_v1_prefix}/health",
        f"{settings.api_v1_prefix}/ready",
    }:
        try:
            category = classify_rate_limit_category(request.method, request.url.path)
            request.state.category = category
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
    authorization = request.headers.get("Authorization", "")
    has_bearer_auth = authorization.lower().startswith("bearer ") and bool(
        authorization[7:].strip()
    )
    # Cookie-only endpoints never use Authorization. Protected endpoints use
    # Bearer exclusively when present and reject it instead of falling back.
    cookie_auth_endpoint = request.url.path in {
        f"{settings.api_v1_prefix}/auth/logout",
        f"{settings.api_v1_prefix}/auth/refresh",
    }
    # Defense in depth only: trusted browser origins may legitimately be
    # cross-site. Metadata never grants identity or replaces double-submit.
    if (unsafe_method and request.headers.get('Sec-Fetch-Site') == 'cross-site'
            and not (origin and is_origin_allowed(origin))
            and (not has_bearer_auth or cookie_auth_endpoint)):
        return JSONResponse(status_code=403, content={'detail': 'Cross-site browser request is not allowed'})
    if (
        unsafe_method
        and (
            request.cookies.get(settings.session_cookie_name)
            or request.cookies.get(settings.refresh_cookie_name)
        )
        and (cookie_auth_endpoint or not has_bearer_auth)
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

    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
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
    except Exception as exc:
        logger.error("Unhandled error processing request %s (reason=%s)", request_id, type(exc).__name__)
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
    return response


# Register CORS outside admission and the auth middleware. It must be the
# single source of CORS headers; manually writing a wildcard
# Access-Control-Allow-Headers breaks credentialed Authorization preflights.
app.add_middleware(UploadBudgetMiddleware)
app.add_middleware(UploadAuthenticationMiddleware, classify=classify_rate_limit_category)
# Bound authentication work too, while keeping body/spool upload reservations
# inside the identity guard. Neither layer reads an unauthorized upload body.
app.add_middleware(AdmissionMiddleware, classify=classify_rate_limit_category)
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
    expose_headers=["X-Request-ID", "Retry-After"],
    max_age=600,
)
# Header-only ASGI wrapper must be outside ALL rejecting user middleware,
# including CORS preflights and upload/admission failures. It never grants
# identity, overrides CORS or buffers the streaming body.
app.add_middleware(ResponseSecurityHeadersMiddleware, secure=settings.secure_cookies)


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.include_router(api_router, prefix=settings.api_v1_prefix)
install_error_handlers(app)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}
