import os
import secrets
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.metrics import record_request
from app.core.rate_limit import enforce_rate_limit

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    summary="LMS and AI services for Learning Website",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

from app.core.errors import _apply_cors_headers, install_error_handlers


def is_origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    if origin in settings.cors_origins:
        return True
    if settings.app_env != "production":
        return True
    return any(origin.endswith(suffix) for suffix in [
        ".vercel.app",
        ".trycloudflare.com",
        ".ngrok-free.app",
        ".ngrok-free.dev",
        ".ngrok.io",
        ".loca.lt",
    ])


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
            res = JSONResponse(
                status_code=exc.status_code,
                content={
                    "detail": str(exc.detail),
                    "error": {"code": "RATE_LIMITED", "message": exc.detail},
                    "request_id": request_id,
                },
                headers=exc.headers,
            )
            return _apply_cors_headers(request, res)
    if unsafe_method and origin and not is_origin_allowed(origin):
        res = JSONResponse(
            status_code=403,
            content={
                "detail": "Origin is not allowed",
                "error": {"code": "FORBIDDEN", "message": "Origin is not allowed"},
                "request_id": request_id,
            },
        )
        return _apply_cors_headers(request, res)
    if unsafe_method and origin and request.cookies.get(settings.session_cookie_name):
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
            return _apply_cors_headers(request, res)

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
                    return _apply_cors_headers(request, res)
            except (ValueError, TypeError):
                pass

    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        import logging
        logging.getLogger("matgar.server").exception("Unhandled error processing request %s: %s", request_id, exc)
        err_res = JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An internal server error occurred"}, "request_id": request_id},
        )
        return _apply_cors_headers(request, err_res)

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

    if origin and is_origin_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
        response.headers["Access-Control-Allow-Headers"] = "*"

    return response


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
            student_accounts = [
                ("student", "student@demo.com", "أحمد محمد"),
            ]
            for u_name, u_email, u_disp in student_accounts:
                st = db.query(User).filter(User.email == u_email).first()
                if not st:
                    st = User(
                        institution_id=inst.id,
                        username=u_name,
                        email=u_email,
                        display_name=u_disp,
                        role=UserRole.STUDENT,
                        password_hash=hash_password("Demo-Pass-2026!"),
                        is_active=True,
                    )
                    db.add(st)
                else:
                    st.display_name = u_disp

            # Purge any non-demo students from database
            from app.models.course import Enrollment
            from app.models.progress import LessonProgress
            from app.models.platform import AssignmentSubmission
            extra_students = db.query(User).filter(User.role == UserRole.STUDENT, User.email != "student@demo.com").all()
            for extra_s in extra_students:
                db.query(Enrollment).filter(Enrollment.student_id == extra_s.id).delete()
                db.query(LessonProgress).filter(LessonProgress.user_id == extra_s.id).delete()
                db.query(AssignmentSubmission).filter(AssignmentSubmission.student_id == extra_s.id).delete()
                db.delete(extra_s)
            db.commit()

            from app.models.course import Course, CourseStatus
            if db.query(Course).count() == 0:
                courses_to_seed = [
                    Course(
                        institution_id=inst.id,
                        teacher_id=teacher.id,
                        code="CHEM-1SEC",
                        title="الكيمياء - الصف الأول الثانوي",
                        description="منهج الكيمياء للصف الأول الثانوي — شرح وتدريبات واختبارات تفاعلية.",
                        status=CourseStatus.PUBLISHED,
                    ),
                    Course(
                        institution_id=inst.id,
                        teacher_id=teacher.id,
                        code="CHEM-2SEC",
                        title="الكيمياء - الصف الثاني الثانوي",
                        description="منهج الكيمياء للصف الثاني الثانوي — شرح وتدريبات واختبارات تفاعلية.",
                        status=CourseStatus.PUBLISHED,
                    ),
                    Course(
                        institution_id=inst.id,
                        teacher_id=teacher.id,
                        code="CHEM-3SEC",
                        title="الكيمياء - الصف الثالث الثانوي",
                        description="منهج الكيمياء للثانوية العامة — شرح وافٍ وتدريبات وتأهيل للامتحان النهائي.",
                        status=CourseStatus.PUBLISHED,
                    ),
                ]
                db.add_all(courses_to_seed)
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
