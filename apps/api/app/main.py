import os
import secrets
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.errors import install_error_handlers
from app.core.metrics import record_request
from app.core.rate_limit import enforce_rate_limit
from app.models import Base

Base.metadata.create_all(bind=engine)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    summary="LMS and AI services for Learning Website",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

def is_origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    if origin in settings.cors_origins:
        return True
    if settings.app_env != "production":
        return True
    return any(origin.endswith(suffix) for suffix in [".trycloudflare.com", ".ngrok-free.app", ".ngrok-free.dev", ".ngrok.io", ".loca.lt"])


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.app_env == "production" else [],
    allow_origin_regex=None if settings.app_env == "production" else r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
            enforce_rate_limit(
                request,
                bucket=f"api:{request.url.path}",
                limit=300,
                window_seconds=60,
            )
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {"code": "RATE_LIMITED", "message": exc.detail},
                    "request_id": request_id,
                },
                headers=exc.headers,
            )
    if unsafe_method and origin and not is_origin_allowed(origin):
        return JSONResponse(status_code=403, content={"detail": "Origin is not allowed"})
    # CSRF validation: enforce whenever a cookie session is used on an unsafe
    # method with an Origin header (Bearer tokens are not CSRF-susceptible).
    auth_header = request.headers.get("Authorization") or ""
    has_bearer = auth_header.startswith("Bearer ")
    if (
        not has_bearer
        and unsafe_method
        and origin
        and request.cookies.get(settings.session_cookie_name)
    ):
        csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_cookie or not secrets.compare_digest(csrf_cookie, csrf_header or ""):
            if settings.app_env == "production":
                return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
            # In development / demo tunnels, allow request to proceed without 403 block

    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    record_request(
        request.url.path,
        request.method,
        response.status_code,
        int((time.perf_counter() - started) * 1000),
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.secure_cookies:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'self'"
    return response


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(api_router, prefix=settings.api_v1_prefix)
install_error_handlers(app)


@app.on_event("startup")
def ensure_demo_users_exist() -> None:
    """Ensure default institution, teacher, and student exist for immediate login in any environment."""
    from app.core.database import SessionLocal
    from app.services.auth_service import get_or_create_institution, hash_password
    from app.models.user import User, UserRole
    try:
        with SessionLocal() as db:
            inst = get_or_create_institution(db, "demo")
            teacher = db.query(User).filter(User.email == "teacher@demo.com").first()
            if not teacher:
                teacher = User(
                    institution_id=inst.id,
                    username="teacher",
                    email="teacher@demo.com",
                    display_name="مستر حسن شعبان",
                    role=UserRole.TEACHER,
                    password_hash=hash_password("Demo-Pass-2026!"),
                    is_active=True,
                )
                db.add(teacher)
            student = db.query(User).filter(User.email == "student@demo.com").first()
            if not student:
                student = User(
                    institution_id=inst.id,
                    username="student",
                    email="student@demo.com",
                    display_name="أحمد محمد",
                    role=UserRole.STUDENT,
                    password_hash=hash_password("Demo-Pass-2026!"),
                    is_active=True,
                )
                db.add(student)
            db.commit()
    except Exception as exc:
        print(f"[startup] ensure_demo_users_exist note: {exc}")


@app.on_event("startup")
def resume_interrupted_indexing() -> None:
    """Automatically resume any knowledge sources left in PROCESSING or QUEUED state in background threads."""
    import threading
    from app.core.database import SessionLocal
    from app.models.knowledge_center import KnowledgeSource, SourceStatus
    from app.services.knowledge_center_service import process_knowledge_source
    from sqlalchemy import select

    def _worker(source_id):
        with SessionLocal() as db_session:
            try:
                process_knowledge_source(db_session, source_id)
            except Exception as e:
                print(f"[startup] Background resume notice for source {source_id}: {e}")

    try:
        with SessionLocal() as db:
            interrupted = db.scalars(
                select(KnowledgeSource).where(
                    KnowledgeSource.status.in_([SourceStatus.PROCESSING, SourceStatus.QUEUED])
                )
            ).all()
            if interrupted:
                print(f"[startup] Found {len(interrupted)} indexing task(s) to resume in background.")
                for source in interrupted:
                    t = threading.Thread(target=_worker, args=(source.id,), daemon=True)
                    t.start()
    except Exception as exc:
        print(f"[startup] resume_interrupted_indexing notice: {exc}")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}
