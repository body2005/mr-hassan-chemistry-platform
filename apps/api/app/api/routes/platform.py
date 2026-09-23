from __future__ import annotations

import mimetypes
import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
UTC = timezone.utc
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
import shutil
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_roles
from app.core.database import get_db
from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.storage import generate_safe_object_key, get_storage_provider
from app.models.course import Course, CourseModule, Enrollment, EnrollmentStatus, Lesson, MaterializationStatus
from app.models.transcript import Transcript, TranscriptSegment, TranscriptionStatus
from app.models.platform import (
    Assignment,
    AssignmentStatus,
    AssignmentSubmission,
    AuditLog,
    CalendarEvent,
    Certificate,
    Notification,
    Question,
    Quiz,
    QuizQuestion,
    QuizStatus,
)
from app.models.progress import LessonProgress
from app.models.platform import LessonComment, AttemptStatus, QuizAttempt
from app.models.user import User, UserRole
from app.schemas import (
    AnalyticsResponse,
    AssignmentCreateRequest,
    AssignmentAttemptResponse,
    AssignmentResponse,
    AssignmentSubmissionCreateRequest,
    AssignmentSubmissionResponse,
    AuditLogResponse,
    CalendarEventCreateRequest,
    CalendarEventResponse,
    CertificateResponse,
    GradeSubmissionRequest,
    LessonCreateRequest,
    LessonProgressResponse,
    ModuleCreateRequest,
    ModuleResponse,
    NotificationBroadcastRequest,
    NotificationCreateRequest,
    NotificationResponse,
    QuestionCreateRequest,
    QuestionResponse,
    QuizAttemptResponse,
    QuizAttemptSubmitRequest,
    QuizCreateRequest,
    QuizResponse,
    UserResponse,
)

from app.services import platform_service
from app.services.audit_service import record_audit
from app.services.payment_service import can_access_lesson_content
from app.models.platform import RefreshSession, RevokedSession

VIDEO_TOKEN_TTL_SECONDS = 300
# A video session is keyed by (account, lesson). Issue a token only while the
# concurrent-session budget for that pair is not exhausted; return its expiry.
def _register_video_session(db: Session, user_id: uuid.UUID, lesson_id: uuid.UUID, ttl_seconds: int) -> datetime:
    settings = get_settings()
    max_sessions = settings.video_max_concurrent_sessions
    now = datetime.now(UTC)
    base_key = f"video-session:{user_id}:{lesson_id}"
    r = _video_session_redis()
    if r is not None:
        try:
            # Drop expired entries first so the budget reflects live sessions.
            r.zremrangebyscore(base_key, "-inf", now.timestamp())
            if r.zcard(base_key) >= max_sessions:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many concurrent video sessions for this account.",
                    headers={"Retry-After": "30"},
                )
            r.zadd(base_key, {str(uuid.uuid4()): now.timestamp() + ttl_seconds})
            r.expire(base_key, ttl_seconds + 5)
            return now + timedelta(seconds=ttl_seconds)
        except HTTPException:
            raise
        except Exception:
            logger.warning("Redis unavailable for video session tracking; falling back to memory")
    # Dev/test fallback: best-effort in-process ledger.
    entries = _memory_video_sessions[base_key]
    cutoff = now.timestamp()
    while entries and entries[0] <= cutoff:
        entries.popleft()
    if len(entries) >= max_sessions:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many concurrent video sessions for this account.",
            headers={"Retry-After": "30"},
        )
    entries.append(now.timestamp() + ttl_seconds)
    return now + timedelta(seconds=ttl_seconds)


_memory_video_sessions: dict[str, deque[float]] = defaultdict(deque)


def _video_session_redis():
    try:
        import redis as _redis

        client = _redis.Redis.from_url(get_settings().redis_url, socket_timeout=1.0, socket_connect_timeout=1.0)
        client.ping()
        return client
    except Exception:
        return None


def _revoke_video_sessions(db: Session, user_id: uuid.UUID, family_id: uuid.UUID | None) -> None:
    """Record a deny-until marker that outlives the 5-minute token TTL."""
    from app.core.rate_limit import _get_redis_client

    now = datetime.now(UTC)
    until = now + timedelta(seconds=VIDEO_TOKEN_TTL_SECONDS + 30)
    r = _get_redis_client()
    keys = [f"video-deny:{user_id}"]
    if family_id is not None:
        keys.append(f"video-deny:{family_id}")
    if r is not None:
        try:
            for key in keys:
                r.set(key, until.isoformat(), ex=VIDEO_TOKEN_TTL_SECONDS + 30)
            return
        except Exception:
            logger.warning("Redis unavailable for video revocation; using memory marker")
    for key in keys:
        _memory_video_deny[key] = until


_memory_video_deny: dict[str, datetime] = {}


def _video_denied(db: Session, user_id: uuid.UUID, family_id: uuid.UUID | None) -> bool:
    from app.core.rate_limit import _get_redis_client

    now = datetime.now(UTC)
    r = _get_redis_client()
    keys = [f"video-deny:{user_id}"]
    if family_id is not None:
        keys.append(f"video-deny:{family_id}")
    if r is not None:
        try:
            for key in keys:
                if r.get(key):
                    return True
            return False
        except Exception:
            pass
    return any(_memory_video_deny.get(key, now) > now for key in keys)


logger = logging.getLogger(__name__)
router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
Manager = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]
Student = Annotated[User, Depends(require_roles(UserRole.STUDENT))]


def _bad_request(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _submission_responses(
    db: Session, submissions: list[AssignmentSubmission]
) -> list[AssignmentSubmissionResponse]:
    if not submissions:
        return []
    assignment_ids = {item.assignment_id for item in submissions}
    student_ids = {item.student_id for item in submissions}
    assignments = {
        item.id: item
        for item in db.scalars(select(Assignment).where(Assignment.id.in_(assignment_ids))).all()
    }
    course_ids = {item.course_id for item in assignments.values()}
    courses = {
        item.id: item
        for item in db.scalars(select(Course).where(Course.id.in_(course_ids))).all()
    }
    students = {
        item.id: item
        for item in db.scalars(select(User).where(User.id.in_(student_ids))).all()
    }
    responses: list[AssignmentSubmissionResponse] = []
    for submission in submissions:
        assignment = assignments.get(submission.assignment_id)
        course = courses.get(assignment.course_id) if assignment else None
        student = students.get(submission.student_id)
        responses.append(
            AssignmentSubmissionResponse.model_validate(submission).model_copy(
                update={
                    "assignment_title": assignment.title if assignment else None,
                    "assignment_prompt": assignment.prompt if assignment else None,
                    "max_score": assignment.max_score if assignment else None,
                    "course_title": course.title if course else None,
                    "student_name": student.display_name if student else None,
                }
            )
        )
    return responses


def _lesson_course(db: Session, lesson_id: uuid.UUID) -> tuple[Lesson, Course]:
    row = db.execute(
        select(Lesson, Course)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .join(Course, CourseModule.course_id == Course.id)
        .where(Lesson.id == lesson_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return row[0], row[1]


def _require_lesson_access(db: Session, user: User, lesson_id: uuid.UUID) -> tuple[Lesson, Course]:
    lesson, course = _lesson_course(db, lesson_id)
    if not can_access_lesson_content(db, user, lesson_id):
        if course.institution_id != user.institution_id:
            raise HTTPException(status_code=404, detail="Lesson not found")
        raise HTTPException(status_code=403, detail="Purchase or active enrollment is required")
    return lesson, course


def _lesson_upload_dir() -> str:
    """Return the private video store without exposing its filesystem path."""
    return os.getenv(
        "VIDEO_UPLOAD_DIR",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "uploads",
        ),
    )


def _lesson_video_path(lesson_id: uuid.UUID) -> str:
    upload_dir = _lesson_upload_dir()
    if not os.path.isdir(upload_dir):
        raise HTTPException(status_code=404, detail="Video not found")
    matches = [name for name in os.listdir(upload_dir) if name.startswith(f"{lesson_id}.")]
    if not matches:
        raise HTTPException(status_code=404, detail="Video not found")
    return os.path.join(upload_dir, matches[0])


def _parse_byte_range(range_header: str | None, size: int) -> tuple[int, int] | None:
    """Parse a single HTTP byte range, rejecting malformed or unsatisfiable input."""
    if not range_header:
        return None
    if not range_header.startswith("bytes=") or "," in range_header:
        raise HTTPException(status_code=416, detail="Invalid byte range")
    start_text, separator, end_text = range_header[6:].partition("-")
    if not separator:
        raise HTTPException(status_code=416, detail="Invalid byte range")
    try:
        if not start_text:
            suffix = int(end_text)
            if suffix <= 0:
                raise ValueError
            start = max(size - suffix, 0)
            end = size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Invalid byte range") from exc
    if start < 0 or start >= size or end < start:
        raise HTTPException(status_code=416, detail="Requested range is not satisfiable")
    return start, min(end, size - 1)


def _stream_stored_media(request: Request, storage_key: str, filename: str, media_type: str) -> Response:
    """Serve local or object-storage media without exposing a storage URL."""
    storage = get_storage_provider()
    try:
        local_path = storage.get_local_path(storage_key)
        if local_path:
            return FileResponse(
                local_path,
                media_type=media_type,
                filename=filename,
                headers={
                    "Content-Disposition": "inline",
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "private, no-cache, no-store",
                    "Referrer-Policy": "strict-origin-when-cross-origin",
                    "X-Content-Type-Options": "nosniff",
                },
            )
        size = storage.get_size(storage_key)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Video not found") from exc
    except Exception as exc:
        # Storage providers intentionally avoid exposing upstream bucket errors.
        raise HTTPException(status_code=404, detail="Video not found") from exc

    byte_range = _parse_byte_range(request.headers.get("range"), size)
    start, end = byte_range if byte_range else (0, size - 1)
    length = end - start + 1
    headers = {
        "Content-Disposition": "inline",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Cache-Control": "private, no-cache, no-store",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Content-Type-Options": "nosniff",
    }
    if byte_range:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(
        storage.open_stream(storage_key, start=start, length=length),
        status_code=206 if byte_range else 200,
        media_type=media_type,
        headers=headers,
    )


@router.post("/courses/{course_id}/modules", response_model=ModuleResponse, status_code=201)
def create_module(
    course_id: uuid.UUID, payload: ModuleCreateRequest, user: Manager, db: Db
) -> ModuleResponse:
    try:
        module = platform_service.add_module(db, user, course_id, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    module.lessons = []
    return ModuleResponse.model_validate(module)


@router.post("/lessons/{lesson_id}/video")
async def upload_lesson_video(
    lesson_id: uuid.UUID,
    user: Manager,
    db: Db,
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    enforce_rate_limit(request, bucket="upload", limit=5, window_seconds=60)
    lesson, course = _lesson_course(db, lesson_id)
    if user.role != UserRole.PLATFORM_ADMIN and course.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Lesson not found")
    try:
        platform_service.ensure_course_manager(user, course)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    allowed_extensions = {".mp4", ".webm", ".mov", ".m4v"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=422, detail="Unsupported video format")
    if file.content_type and not file.content_type.startswith("video/"):
        raise HTTPException(status_code=422, detail="Uploaded file is not a video")

    filename = f"{lesson_id}{ext}"
    temp_file = tempfile.NamedTemporaryFile(prefix="lesson-video-", suffix=ext, delete=False)
    filepath = temp_file.name
    temp_file.close()

    file_size_limit = 500 * 1024 * 1024
    written = 0
    try:
        with open(filepath, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > file_size_limit:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={"code": "FILE_TOO_LARGE", "message": "حجم ملف الفيديو لا يجب أن يتجاوز 500 ميجابايت."},
                    )
                buffer.write(chunk)
    except Exception:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise

    storage = get_storage_provider()
    storage_key = generate_safe_object_key(f"lesson_videos/{lesson.id}", filename)
    try:
        stored_path = storage.save_file(filepath, storage_key, file.content_type or mimetypes.guess_type(filename)[0])
    except Exception as exc:
        try:
            storage.delete(storage_key)
        except Exception:
            logger.exception("Failed to clean up video object after storage failure: %s", storage_key)
        raise HTTPException(status_code=500, detail="Unable to store lesson video") from exc
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

    previous_asset = lesson.video_asset_key
    video_url = f"/api/v1/lessons/{lesson_id}/video"
    lesson.video_asset_key = stored_path
    lesson.materialization_status = MaterializationStatus.NOT_INDEXED
    lesson.indexing_error = None
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            storage.delete(stored_path)
        except Exception:
            logger.exception("Failed to clean up video object after database failure: %s", stored_path)
        raise HTTPException(status_code=500, detail="Unable to save lesson video") from exc
    db.refresh(lesson)

    if previous_asset and previous_asset != stored_path and not previous_asset.startswith("/api/"):
        try:
            storage.delete(previous_asset)
        except Exception:
            logger.exception("Failed to clean up replaced video object: %s", previous_asset)

    return {
        "id": str(lesson.id),
        "video_url": video_url,
        "filename": filename,
        "message": "Video uploaded successfully as a protected playback asset.",
    }


@router.get("/lessons/{lesson_id}/video")
def stream_lesson_video(lesson_id: uuid.UUID, request: Request, user: CurrentUser, db: Db) -> Response:
    # Teacher/admin management preview. Students must use the token stream.
    if user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Student playback requires a video stream token")
    enforce_rate_limit(request, bucket="lesson-video-preview", category="read")
    lesson, _ = _require_lesson_access(db, user, lesson_id)
    if lesson.video_asset_key and not lesson.video_asset_key.startswith("/api/"):
        media_type = mimetypes.guess_type(lesson.video_asset_key)[0] or "video/mp4"
        return _stream_stored_media(request, lesson.video_asset_key, f"lesson-{lesson.id}", media_type)
    return FileResponse(
        _lesson_video_path(lesson.id),
        media_type="video/mp4",
        headers={
            "Content-Disposition": "inline",
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, no-cache, no-store",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/lessons/{lesson_id}/video-token")
def create_lesson_video_token(lesson_id: uuid.UUID, request: Request, user: CurrentUser, db: Db) -> dict:
    from app.core.security import create_video_token, decode_session_token

    enforce_rate_limit(request, bucket="lesson-video-token", category="read")
    lesson, _ = _require_lesson_access(db, user, lesson_id)

    session_cookie = request.cookies.get(get_settings().session_cookie_name)
    session_payload = decode_session_token(session_cookie) if session_cookie else None
    if not session_payload:
        raise HTTPException(status_code=401, detail="A live session is required for video playback")
    if _video_denied(db, user.id, session_payload.get("family_id")):
        raise HTTPException(status_code=403, detail="Video access has been revoked")
    session_id = str(session_payload.get("jti") or "")
    if not session_id:
        raise HTTPException(status_code=401, detail="A live session is required for video playback")
    family_id: uuid.UUID | None = None
    raw_family = session_payload.get("family_id")
    if raw_family:
        try:
            family_id = uuid.UUID(str(raw_family))
        except (TypeError, ValueError):
            family_id = None
    expires_at = _register_video_session(db, user.id, lesson.id, VIDEO_TOKEN_TTL_SECONDS)
    token = create_video_token(
        user=user,
        lesson_id=lesson.id,
        expires_in_seconds=VIDEO_TOKEN_TTL_SECONDS,
        nonce=session_id,
        family_id=family_id,
    )
    return {
        "video_token": token,
        "stream_url": f"/api/v1/lessons/{lesson.id}/stream?token={token}",
        "expires_in": VIDEO_TOKEN_TTL_SECONDS,
    }


@router.get("/lessons/{lesson_id}/stream")
def stream_lesson_authenticated_range(
    lesson_id: uuid.UUID,
    request: Request,
    db: Db,
    token: str | None = None,
) -> Response:
    from app.core.security import decode_session_token, decode_video_token

    enforce_rate_limit(request, bucket="lesson-video-stream", category="read")
    payload = decode_video_token(token) if token else None
    if not payload or payload.get("lesson_id") != str(lesson_id):
        raise HTTPException(status_code=403, detail="Invalid or expired video stream token")
    if payload.get("purpose") != "video_stream" or payload.get("aud") != "video_stream":
        raise HTTPException(status_code=403, detail="Invalid or expired video stream token")
    nonce = str(payload.get("nonce") or "")
    if not nonce:
        raise HTTPException(status_code=403, detail="Invalid or expired video stream token")

    user_id = uuid.UUID(str(payload["sub"]))
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=403, detail="Invalid or expired video stream token")

    # Replay the same authorization the token endpoint enforced at issue time.
    if _video_denied(db, user.id, payload.get("family_id")):
        raise HTTPException(status_code=403, detail="Video access has been revoked")
    # Strict session binding: the streaming client must present the live
    # session that requested the token (nonce == session jti, same subject).
    # Same-origin <video> requests carry cookies automatically, so browser
    # playback works; link sharing, other accounts, and anonymous replays die.
    session_cookie = request.cookies.get(get_settings().session_cookie_name)
    session_payload = decode_session_token(session_cookie) if session_cookie else None
    session_ok = bool(
        session_payload
        and str(session_payload.get("sub")) == str(user.id)
        and str(session_payload.get("jti") or "") == nonce
    )
    if not session_ok:
        raise HTTPException(status_code=403, detail="Video session is no longer active")

    lesson, _ = _lesson_course(db, lesson_id)
    if lesson.video_asset_key and not lesson.video_asset_key.startswith("/api/"):
        media_type = mimetypes.guess_type(lesson.video_asset_key)[0] or "video/mp4"
        return _stream_stored_media(request, lesson.video_asset_key, f"lesson-{lesson.id}", media_type)
    return FileResponse(
        _lesson_video_path(lesson_id),
        media_type="video/mp4",
        headers={
            "Content-Disposition": "inline",
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, no-cache, no-store",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/lessons/{lesson_id}/transcript")
def get_lesson_transcript(lesson_id: uuid.UUID, user: CurrentUser, db: Db) -> dict:
    lesson, _ = _require_lesson_access(db, user, lesson_id)
    transcript = db.query(Transcript).filter(Transcript.lesson_id == lesson_id).first()
    if not transcript:
        return {
            "lesson_id": str(lesson.id),
            "status": "not_indexed" if lesson.materialization_status == MaterializationStatus.NOT_INDEXED else "processing",
            "language": "ar",
            "duration_seconds": 0.0,
            "full_text": lesson.transcript_text or "",
            "segments_count": 0,
        }
    return {
        "lesson_id": str(lesson.id),
        "transcript_id": str(transcript.id),
        "status": transcript.status.value if hasattr(transcript.status, "value") else str(transcript.status),
        "language": transcript.language,
        "duration_seconds": transcript.duration_seconds,
        "full_text": transcript.full_text,
        "provider": transcript.provider,
        "provider_model": transcript.provider_model,
        "completed_at": transcript.completed_at.isoformat() if transcript.completed_at else None,
    }


@router.get("/lessons/{lesson_id}/transcript/segments")
def get_lesson_transcript_segments(
    lesson_id: uuid.UUID, user: CurrentUser, db: Db, q: str | None = None
) -> dict:
    lesson, _ = _require_lesson_access(db, user, lesson_id)

    query = db.query(TranscriptSegment).filter(TranscriptSegment.lesson_id == lesson_id)
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(TranscriptSegment.text.ilike(search_term))

    segments = query.order_by(TranscriptSegment.sequence).all()
    return {
        "lesson_id": str(lesson.id),
        "count": len(segments),
        "segments": [
            {
                "id": str(s.id),
                "sequence": s.sequence,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "time_formatted": f"{int(s.start_time)//60:02d}:{int(s.start_time)%60:02d}",
                "text": s.text,
            }
            for s in segments
        ],
    }


@router.post("/modules/{module_id}/lessons", response_model=dict, status_code=201)
def create_lesson(
    module_id: uuid.UUID,
    payload: LessonCreateRequest,
    user: Manager,
    db: Db,
    background_tasks: BackgroundTasks,
) -> dict:
    try:
        lesson = platform_service.add_lesson(db, user, module_id, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc

    # Video files are pure playback assets; AI indexing is permanently disabled for video lessons.
    lesson.materialization_status = MaterializationStatus.NOT_INDEXED
    db.commit()

    return {
        "id": lesson.id,
        "title": lesson.title,
        "kind": lesson.kind,
        "position": lesson.position,
        "materialization_status": "not_indexed",
        "price_egp": float(lesson.price_egp or 0),
    }


@router.post("/courses/{course_id}/reindex-all")
def reindex_all_course_lessons(
    course_id: uuid.UUID,
    db: Db,
    user: Manager,
    background_tasks: BackgroundTasks,
) -> dict:
    try:
        course = platform_service.course_for_user(db, user, course_id)
        platform_service.ensure_course_manager(user, course)
    except (LookupError, PermissionError) as exc:
        raise _bad_request(exc) from exc

    query = (
        select(Lesson)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .where(CourseModule.course_id == course_id)
    )
    lessons = db.scalars(query).all()

    queued = 0
    skipped = []

    for l in lessons:
        skipped.append({"lesson_id": str(l.id), "reason": "فهرسة الفيديو معطلة بالكامل"})

    return {"queued_lessons": 0, "skipped": skipped}

@router.delete("/modules/{module_id}/lessons/{lesson_id}", status_code=204)
def delete_lesson(module_id: uuid.UUID, lesson_id: uuid.UUID, user: Manager, db: Db) -> None:
    try:
        platform_service.delete_lesson(db, user, module_id, lesson_id)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc


@router.get("/progress/lessons/{lesson_id}", response_model=LessonProgressResponse)
def lesson_progress(lesson_id: uuid.UUID, user: Student, db: Db) -> LessonProgressResponse:
    progress = db.scalar(
        select(LessonProgress)
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .join(CourseModule, CourseModule.id == Lesson.module_id)
        .join(Course, Course.id == CourseModule.course_id)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(
            LessonProgress.lesson_id == lesson_id,
            LessonProgress.student_id == user.id,
            Course.institution_id == user.institution_id,
            Enrollment.student_id == user.id,
            Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        )
    )
    if progress is None:
        raise HTTPException(status_code=404, detail="Lesson progress not found")
    return LessonProgressResponse.model_validate(progress)


@router.get("/progress/me", response_model=list[LessonProgressResponse])
def my_progress(user: Student, db: Db) -> list[LessonProgressResponse]:
    items = db.scalars(
        select(LessonProgress).where(
            LessonProgress.student_id == user.id,
            LessonProgress.institution_id == user.institution_id,
        )
    ).all()
    return [LessonProgressResponse.model_validate(item) for item in items]


@router.post("/progress/lessons/{lesson_id}/complete", response_model=LessonProgressResponse)
def complete_lesson(lesson_id: uuid.UUID, user: Student, db: Db) -> LessonProgressResponse:
    _require_lesson_access(db, user, lesson_id)
    progress = db.scalar(
        select(LessonProgress)
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .join(CourseModule, CourseModule.id == Lesson.module_id)
        .join(Course, Course.id == CourseModule.course_id)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(
            LessonProgress.lesson_id == lesson_id,
            LessonProgress.student_id == user.id,
            Course.institution_id == user.institution_id,
            Enrollment.student_id == user.id,
            Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        )
    )
    if progress is None:
        lesson = db.scalar(
            select(Lesson)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .join(Course, Course.id == CourseModule.course_id)
            .join(Enrollment, Enrollment.course_id == Course.id)
            .where(
                Lesson.id == lesson_id,
                Course.institution_id == user.institution_id,
                Enrollment.student_id == user.id,
                Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
            )
        )
        if lesson is None:
            raise HTTPException(status_code=404, detail="Lesson not found")
        progress = LessonProgress(
            institution_id=user.institution_id,
            student_id=user.id,
            lesson_id=lesson_id,
        )
        db.add(progress)
    progress.completion_percent = 100
    progress.completed_at = progress.completed_at or datetime.now(UTC)
    progress.last_event_at = progress.completed_at
    course_id = db.scalar(
        select(Course.id)
        .join(CourseModule, CourseModule.course_id == Course.id)
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .where(Lesson.id == lesson_id)
    )
    if course_id:
        enrollment = db.scalar(
            select(Enrollment).where(
                Enrollment.course_id == course_id,
                Enrollment.student_id == user.id,
            )
        )
        total_lessons = db.scalar(
            select(func.count(Lesson.id))
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .where(CourseModule.course_id == course_id)
        ) or 0
        completed_lessons = db.scalar(
            select(func.count(LessonProgress.id))
            .join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .where(
                CourseModule.course_id == course_id,
                LessonProgress.student_id == user.id,
                LessonProgress.completion_percent >= 100,
            )
        ) or 0
        if enrollment and total_lessons:
            enrollment.progress_percent = round(completed_lessons / total_lessons * 100, 2)
            if enrollment.progress_percent >= 100:
                enrollment.status = EnrollmentStatus.COMPLETED
                enrollment.completed_at = progress.completed_at
    db.commit()
    db.refresh(progress)
    return LessonProgressResponse.model_validate(progress)


@router.post("/questions", response_model=QuestionResponse, status_code=201)
def create_question(
    payload: QuestionCreateRequest, user: Manager, db: Db, request: Request
) -> QuestionResponse:
    try:
        question = platform_service.create_question(db, user, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    record_audit(
        db,
        request,
        action="question_created",
        resource_type="question",
        actor=user,
        resource_id=str(question.id),
    )
    db.commit()
    return QuestionResponse.model_validate(question)


@router.get("/questions", response_model=list[QuestionResponse])
def list_questions(
    user: Manager, db: Db, course_id: uuid.UUID | None = None
) -> list[QuestionResponse]:
    query = select(Question).where(
        Question.institution_id == user.institution_id, Question.is_active.is_(True)
    )
    if course_id:
        query = query.where(Question.course_id == course_id)
    return [
        QuestionResponse.model_validate(item)
        for item in db.scalars(query.order_by(Question.created_at.desc())).all()
    ]


@router.post("/quizzes", response_model=QuizResponse, status_code=201)
def create_quiz(payload: QuizCreateRequest, user: Manager, db: Db) -> QuizResponse:
    if payload.question_ids:
        unindexed_count = db.scalar(
            select(func.count(Question.id))
            .where(Question.id.in_(payload.question_ids), Question.learning_objective == "محتوى غير مفهرس")
        )
        if unindexed_count and unindexed_count > 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="لا يمكن إنشاء أو حفظ كويز يحتوي على أسئلة بمحتوى غير مفهرس.",
            )
    try:
        quiz = platform_service.create_quiz(db, user, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return QuizResponse.model_validate(quiz)


@router.post("/quizzes/{quiz_id}/publish", response_model=QuizResponse)
def publish_quiz(quiz_id: uuid.UUID, user: Manager, db: Db) -> QuizResponse:
    try:
        quiz = platform_service.publish_quiz(db, user, quiz_id)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return QuizResponse.model_validate(quiz)


@router.get("/quizzes", response_model=list[QuizResponse])
def list_quizzes(
    user: CurrentUser, db: Db, course_id: uuid.UUID | None = None
) -> list[QuizResponse]:
    query = select(Quiz).where(Quiz.institution_id == user.institution_id)
    if course_id:
        query = query.where(Quiz.course_id == course_id)
    if user.role == UserRole.STUDENT:
        query = query.where(Quiz.status == "published")
    return [
        QuizResponse.model_validate(item)
        for item in db.scalars(query.order_by(Quiz.created_at.desc())).all()
    ]


@router.post("/quizzes/{quiz_id}/attempts", response_model=QuizAttemptResponse)
def start_quiz(quiz_id: uuid.UUID, user: Student, db: Db) -> QuizAttemptResponse:
    try:
        attempt = platform_service.start_quiz(db, user, quiz_id)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return QuizAttemptResponse.model_validate(attempt)


@router.post("/quiz-attempts/{attempt_id}/submit", response_model=QuizAttemptResponse)
def submit_quiz(
    attempt_id: uuid.UUID, payload: QuizAttemptSubmitRequest, user: Student, db: Db
) -> QuizAttemptResponse:
    try:
        attempt = platform_service.submit_quiz(db, user, attempt_id, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return QuizAttemptResponse.model_validate(attempt)


@router.post("/assignments", response_model=AssignmentResponse, status_code=201)
def create_assignment(
    payload: AssignmentCreateRequest, user: Manager, db: Db
) -> AssignmentResponse:
    try:
        assignment = platform_service.create_assignment(db, user, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return AssignmentResponse.model_validate(assignment)


@router.post("/assignments/{assignment_id}/publish", response_model=AssignmentResponse)
def publish_assignment(assignment_id: uuid.UUID, user: Manager, db: Db) -> AssignmentResponse:
    try:
        assignment = platform_service.publish_assignment(db, user, assignment_id)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return AssignmentResponse.model_validate(assignment)


@router.get("/assignments", response_model=list[AssignmentResponse])
def list_assignments(
    user: CurrentUser, db: Db, course_id: uuid.UUID | None = None
) -> list[AssignmentResponse]:
    query = select(Assignment).where(Assignment.institution_id == user.institution_id)
    if course_id:
        query = query.where(Assignment.course_id == course_id)
    if user.role == UserRole.STUDENT:
        query = query.where(Assignment.status == AssignmentStatus.PUBLISHED)
    return [
        AssignmentResponse.model_validate(item)
        for item in db.scalars(query.order_by(Assignment.created_at.desc())).all()
    ]


@router.post("/assignments/{assignment_id}/attempts", response_model=AssignmentAttemptResponse)
def start_assignment(assignment_id: uuid.UUID, user: Student, db: Db) -> AssignmentAttemptResponse:
    try:
        attempt = platform_service.start_assignment(db, user, assignment_id)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return AssignmentAttemptResponse.model_validate(attempt)


@router.post(
    "/assignments/{assignment_id}/submissions", response_model=AssignmentSubmissionResponse
)
def submit_assignment(
    assignment_id: uuid.UUID,
    payload: AssignmentSubmissionCreateRequest,
    user: Student,
    db: Db,
) -> AssignmentSubmissionResponse:
    try:
        submission = platform_service.submit_assignment(db, user, assignment_id, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return _submission_responses(db, [submission])[0]


@router.get(
    "/assignments/{assignment_id}/submissions", response_model=list[AssignmentSubmissionResponse]
)
def list_submissions(
    assignment_id: uuid.UUID, user: CurrentUser, db: Db
) -> list[AssignmentSubmissionResponse]:
    assignment = db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id, Assignment.institution_id == user.institution_id
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if user.role == UserRole.STUDENT:
        query = select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == user.id,
        )
    else:
        course = db.get(Course, assignment.course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        try:
            platform_service.ensure_course_manager(user, course)
        except PermissionError as exc:
            raise _bad_request(exc) from exc
        query = select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment_id
        )
    return _submission_responses(
        db, list(db.scalars(query.order_by(AssignmentSubmission.version.desc())).all())
    )


@router.get("/submissions/me", response_model=list[AssignmentSubmissionResponse])
def my_submissions(user: Student, db: Db) -> list[AssignmentSubmissionResponse]:
    items = db.scalars(
        select(AssignmentSubmission)
        .where(
            AssignmentSubmission.student_id == user.id,
            AssignmentSubmission.institution_id == user.institution_id,
        )
        .order_by(AssignmentSubmission.submitted_at.desc())
    ).all()
    return _submission_responses(db, list(items))


@router.get("/submissions", response_model=list[AssignmentSubmissionResponse])
def all_submissions(user: Manager, db: Db) -> list[AssignmentSubmissionResponse]:
    items = db.scalars(
        select(AssignmentSubmission)
        .where(AssignmentSubmission.institution_id == user.institution_id)
        .order_by(AssignmentSubmission.submitted_at.desc())
        .limit(500)
    ).all()
    return _submission_responses(db, list(items))


@router.get("/submissions/{submission_id}/file")
def download_submission_file(
    submission_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
):
    """Stream a student's uploaded solution file to the course manager.

    Managers only; the owning student has no re-download path here (their
    copy was the upload itself). The native object_key never appears in the
    response — the file is streamed from storage.
    """
    submission = db.get(AssignmentSubmission, submission_id)
    if submission is None or submission.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = db.get(Assignment, submission.assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    course = db.get(Course, assignment.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    if user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        platform_service.ensure_course_manager(user, course)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not submission.object_key:
        raise HTTPException(status_code=404, detail="Submission has no attached file")

    from app.core.storage import get_storage_provider
    from urllib.parse import quote

    storage = get_storage_provider()
    if not storage.exists(submission.object_key):
        raise HTTPException(status_code=404, detail="File missing from storage")

    filename = f"{str(submission.student_id)[:8]}-v{submission.version}.pdf"
    stream = storage.open_stream(submission.object_key)
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/submissions/{submission_id}/grade", response_model=AssignmentSubmissionResponse)
def grade_submission(
    submission_id: uuid.UUID,
    payload: GradeSubmissionRequest,
    user: Manager,
    db: Db,
    request: Request,
) -> AssignmentSubmissionResponse:
    try:
        submission = platform_service.grade_submission(db, user, submission_id, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    record_audit(
        db,
        request,
        action="submission_graded",
        resource_type="assignment_submission",
        actor=user,
        resource_id=str(submission.id),
        after={"score": submission.final_score, "approved": payload.approve},
    )
    db.commit()
    return _submission_responses(db, [submission])[0]


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    user: CurrentUser, db: Db, unread_only: bool = False
) -> list[NotificationResponse]:
    query = select(Notification).where(
        Notification.recipient_id == user.id,
        Notification.institution_id == user.institution_id,
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return [
        NotificationResponse.model_validate(item)
        for item in db.scalars(query.order_by(Notification.created_at.desc()).limit(200)).all()
    ]


@router.post("/notifications", response_model=NotificationResponse, status_code=201)
def create_notification(
    payload: NotificationCreateRequest, user: Manager, db: Db
) -> NotificationResponse:
    try:
        notification = platform_service.create_notification(db, user, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return NotificationResponse.model_validate(notification)


@router.post("/notifications/broadcast", response_model=list[NotificationResponse], status_code=201)
def broadcast_notification(
    payload: NotificationBroadcastRequest, user: Manager, db: Db
) -> list[NotificationResponse]:
    try:
        notifications = platform_service.broadcast_notification(db, user, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return [NotificationResponse.model_validate(item) for item in notifications]


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: uuid.UUID, user: CurrentUser, db: Db
) -> NotificationResponse:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == user.id,
            Notification.institution_id == user.institution_id,
        )
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read_at = notification.read_at or datetime.now(UTC)
    db.commit()
    db.refresh(notification)
    return NotificationResponse.model_validate(notification)


@router.get("/calendar", response_model=list[CalendarEventResponse])
def list_calendar(user: CurrentUser, db: Db) -> list[CalendarEventResponse]:
    query = select(CalendarEvent).where(CalendarEvent.institution_id == user.institution_id)
    if user.role == UserRole.STUDENT:
        query = query.where(
            CalendarEvent.is_published.is_(True), CalendarEvent.cancelled_at.is_(None)
        )
    return [
        CalendarEventResponse.model_validate(item)
        for item in db.scalars(query.order_by(CalendarEvent.starts_at.asc()).limit(500)).all()
    ]


@router.post("/calendar", response_model=CalendarEventResponse, status_code=201)
def create_calendar(
    payload: CalendarEventCreateRequest, user: Manager, db: Db
) -> CalendarEventResponse:
    try:
        event = platform_service.create_calendar_event(db, user, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return CalendarEventResponse.model_validate(event)


@router.post("/calendar/{event_id}/cancel", response_model=CalendarEventResponse)
def cancel_calendar(event_id: uuid.UUID, user: Manager, db: Db) -> CalendarEventResponse:
    event = db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id, CalendarEvent.institution_id == user.institution_id
        )
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    if user.role == UserRole.TEACHER and event.creator_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this event")
    event.cancelled_at = datetime.now(UTC)
    db.commit()
    db.refresh(event)
    return CalendarEventResponse.model_validate(event)


@router.put("/calendar/{event_id}", response_model=CalendarEventResponse)
def update_calendar(
    event_id: uuid.UUID, payload: CalendarEventCreateRequest, user: Manager, db: Db
) -> CalendarEventResponse:
    event = db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.institution_id == user.institution_id,
        )
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    if user.role == UserRole.TEACHER and event.creator_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this event")
    event.course_id = payload.course_id
    event.title = payload.title.strip()
    event.description = payload.description
    event.event_type = payload.event_type
    event.starts_at = payload.starts_at
    event.ends_at = payload.ends_at
    event.is_published = payload.is_published
    event.cancelled_at = None
    db.commit()
    db.refresh(event)
    return CalendarEventResponse.model_validate(event)


@router.post(
    "/certificates/courses/{course_id}", response_model=CertificateResponse, status_code=201
)
def issue_certificate(course_id: uuid.UUID, user: Student, db: Db) -> CertificateResponse:
    try:
        certificate = platform_service.issue_certificate(db, user, course_id)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return CertificateResponse.model_validate(certificate)


@router.get("/certificates/verify/{token}", response_model=CertificateResponse)
def verify_certificate(token: str, db: Db) -> CertificateResponse:
    certificate = db.scalar(
        select(Certificate).where(
            Certificate.verification_token == token, Certificate.revoked_at.is_(None)
        )
    )
    if certificate is None:
        raise HTTPException(status_code=404, detail="Certificate is invalid or revoked")
    return CertificateResponse.model_validate(certificate)


@router.get("/analytics/courses/{course_id}", response_model=AnalyticsResponse)
def analytics(course_id: uuid.UUID, user: Manager, db: Db) -> AnalyticsResponse:
    try:
        data = platform_service.course_analytics(db, user, course_id)
    except (LookupError, PermissionError, ValueError) as exc:
        raise _bad_request(exc) from exc
    return AnalyticsResponse.model_validate(data)


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def audit_logs(user: Manager, db: Db, limit: int = 100) -> list[AuditLogResponse]:
    query = select(AuditLog).where(AuditLog.institution_id == user.institution_id)
    return [
        AuditLogResponse.model_validate(item)
        for item in db.scalars(
            query.order_by(AuditLog.occurred_at.desc()).limit(min(limit, 500))
        ).all()
    ]


@router.get("/users", response_model=list[UserResponse])
def list_users(user: Manager, db: Db, role: UserRole | None = None) -> list[UserResponse]:
    query = select(User).where(
        User.institution_id == user.institution_id,
        User.deleted_at.is_(None),
    )
    if role:
        query = query.where(User.role == role)
    return [
        UserResponse.model_validate(item)
        for item in db.scalars(query.order_by(User.created_at.desc())).all()
    ]


@router.post("/users/{user_id}/block", response_model=UserResponse)
def block_user(user_id: uuid.UUID, actor: Manager, db: Db, request: Request) -> UserResponse:
    target = db.scalar(
        select(User).where(
            User.id == user_id,
            User.institution_id == actor.institution_id,
            User.role == UserRole.STUDENT,
            User.deleted_at.is_(None),
        )
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if actor.role == UserRole.TEACHER:
        has_course = db.scalar(
            select(Enrollment.id)
            .join(Course, Course.id == Enrollment.course_id)
            .where(Enrollment.student_id == target.id, Course.teacher_id == actor.id)
        )
        if has_course is None:
            raise HTTPException(status_code=403, detail="Student is outside your courses")
    target.is_active = not target.is_active
    record_audit(
        db,
        request,
        action="student_block_toggled",
        resource_type="user",
        actor=actor,
        resource_id=str(target.id),
        after={"is_active": target.is_active},
    )
    db.commit()
    db.refresh(target)
    return UserResponse.model_validate(target)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: uuid.UUID, actor: Manager, db: Db, request: Request) -> None:
    target = db.scalar(
        select(User).where(
            User.id == user_id,
            User.institution_id == actor.institution_id,
            User.role == UserRole.STUDENT,
            User.deleted_at.is_(None),
        )
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if actor.role == UserRole.TEACHER:
        has_course = db.scalar(
            select(Enrollment.id)
            .join(Course, Course.id == Enrollment.course_id)
            .where(Enrollment.student_id == target.id, Course.teacher_id == actor.id)
        )
        if has_course is None:
            raise HTTPException(status_code=403, detail="Student is outside your courses")
    target.deleted_at = datetime.now(UTC)
    target.is_active = False
    record_audit(
        db,
        request,
        action="student_deleted",
        resource_type="user",
        actor=actor,
        resource_id=str(target.id),
    )
    db.commit()


from pydantic import BaseModel

class ASRConfigPayload(BaseModel):
    kaggle_asr_url: str = ""

@router.get("/system/asr-config")
def get_asr_config():
    from app.core.config import get_settings
    settings = get_settings()
    url = os.getenv("KAGGLE_ASR_URL") or settings.kaggle_asr_url or os.getenv("REMOTE_ASR_URL") or ""
    return {
        "kaggle_asr_url": url,
        "mode": "remote_kaggle" if url else "local_whisper",
        "provider": "QwenCleo-ASR (Kaggle GPU)" if url else "Faster-Whisper Small (Local CPU)"
    }

@router.post("/system/asr-config")
def update_asr_config(payload: ASRConfigPayload):
    os.environ["KAGGLE_ASR_URL"] = payload.kaggle_asr_url.strip()
    return {
        "status": "success",
        "kaggle_asr_url": os.environ["KAGGLE_ASR_URL"],
        "mode": "remote_kaggle" if os.environ["KAGGLE_ASR_URL"] else "local_whisper",
        "provider": "QwenCleo-ASR (Kaggle GPU)" if os.environ["KAGGLE_ASR_URL"] else "Faster-Whisper Small (Local CPU)"
    }


# ---------------------------------------------------------------------------
# Lesson materials (standalone; replaces Knowledge-Center based materials)
# ---------------------------------------------------------------------------

@router.post("/lessons/{lesson_id}/materials", status_code=201)
async def upload_lesson_material(
    request: Request,
    lesson_id: uuid.UUID,
    user: Manager,
    db: Db,
    file: UploadFile = File(...),
) -> dict:
    enforce_rate_limit(request, bucket="upload")
    from app.services.lesson_materials import upload_material

    asset = await upload_material(db, user, lesson_id, file)
    return {
        "id": str(asset.id),
        "lesson_id": str(asset.lesson_id),
        "filename": asset.filename,
        "size_bytes": asset.size_bytes or 0,
        "mime_type": asset.mime_type,
        "download_url": f"/api/v1/lessons/{asset.lesson_id}/materials/{asset.id}/download",
    }


@router.get("/lessons/{lesson_id}/materials/{asset_id}/download")
def download_lesson_material(
    lesson_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
):
    from app.services.lesson_materials import open_material_stream

    stream, media_type, filename = open_material_stream(db, user, lesson_id, asset_id, as_attachment=True)
    from urllib.parse import quote

    return StreamingResponse(
        stream,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename or 'material')}",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/lessons/{lesson_id}/materials/{asset_id}", status_code=204)
def delete_lesson_material(
    lesson_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: Manager,
    db: Db,
) -> Response:
    from app.services.lesson_materials import delete_material

    delete_material(db, user, lesson_id, asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/courses/{course_id}/assessments")
def list_course_assessments(course_id: uuid.UUID, user: CurrentUser, db: Db) -> dict:
    """Student-facing per-lesson/unit assessments with access gating.

    Returns published quizzes/assignments for this course grouped by
    lesson_id/module_id. Every item carries `accessible`: whether this student
    may open/attempt it (enrollment + payment/entitlement on the lesson).
    """
    lesson_ids: list[uuid.UUID] = []
    lesson_titles: dict[uuid.UUID, str] = {}
    accessible_lessons: set[uuid.UUID] = set()
    course = db.get(Course, course_id)
    if course is None or course.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Course not found")

    enrolled = db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == user.id,
            Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        )
    )
    modules = list(
        db.scalars(
            select(CourseModule)
            .where(CourseModule.course_id == course_id)
            .order_by(CourseModule.position)
        ).all()
    )
    for module in modules:
        for lesson in db.scalars(
            select(Lesson).where(Lesson.module_id == module.id).order_by(Lesson.position)
        ).all():
            lesson_ids.append(lesson.id)
            lesson_titles[lesson.id] = lesson.title
            if user.role != UserRole.STUDENT:
                accessible_lessons.add(lesson.id)
            elif enrolled and can_access_lesson_content(db, user, lesson.id):
                accessible_lessons.add(lesson.id)

    quizzes = list(
        db.scalars(
            select(Quiz)
            .where(
                Quiz.course_id == course_id,
                Quiz.institution_id == user.institution_id,
                Quiz.status == "published",
            )
            .order_by(Quiz.published_at.desc())
        ).all()
    )
    assignments = list(
        db.scalars(
            select(Assignment)
            .where(
                Assignment.course_id == course_id,
                Assignment.institution_id == user.institution_id,
                Assignment.status == "published",
            )
            .order_by(Assignment.created_at.desc())
        ).all()
    )

    def quiz_item(q: Quiz) -> dict:
        attempts_used = (
            db.scalar(
                select(func.count(QuizAttempt.id)).where(
                    QuizAttempt.quiz_id == q.id,
                    QuizAttempt.student_id == user.id,
                    QuizAttempt.is_practice.is_(False),
                )
            )
            if user.role == UserRole.STUDENT
            else 0
        )
        return {
            "id": str(q.id),
            "kind": "quiz",
            "title": q.title,
            "course_id": str(q.course_id),
            "module_id": str(q.module_id) if q.module_id else None,
            "lesson_id": str(q.lesson_id) if q.lesson_id else None,
            "duration_seconds": q.duration_seconds,
            "starts_at": q.starts_at.isoformat() if q.starts_at else None,
            "ends_at": q.ends_at.isoformat() if q.ends_at else None,
            "attempts_allowed": q.attempts_allowed,
            "attempts_used": attempts_used,
            # Unscoped quizzes fall back to: any enrolled student can try.
            "accessible": q.lesson_id is None or q.lesson_id in accessible_lessons,
        }

    def assignment_item(a: Assignment) -> dict:
        return {
            "id": str(a.id),
            "kind": "assignment",
            "title": a.title,
            "course_id": str(a.course_id),
            "module_id": str(a.module_id) if a.module_id else None,
            "lesson_id": str(a.lesson_id) if a.lesson_id else None,
            "due_at": a.due_at.isoformat() if a.due_at else None,
            "max_score": float(a.max_score or 0),
            "accessible": a.lesson_id is None or a.lesson_id in accessible_lessons,
        }

    return {
        "course_id": str(course_id),
        "lessons": [
            {"id": str(lid), "title": lesson_titles[lid], "accessible": lid in accessible_lessons}
            for lid in lesson_ids
        ],
        "quizzes": [quiz_item(q) for q in quizzes],
        "assignments": [assignment_item(a) for a in assignments],
    }


# ---------------------------------------------------------------------------
# Standalone solving pages: quiz questions for the student + assignment PDF
# ---------------------------------------------------------------------------


def _quiz_for_student(db: Session, quiz_id: uuid.UUID, user: CurrentUser) -> Quiz:
    quiz = db.scalar(
        select(Quiz).where(
            Quiz.id == quiz_id,
            Quiz.institution_id == user.institution_id,
            Quiz.status == QuizStatus.PUBLISHED,
        )
    )
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if user.role == UserRole.STUDENT and not _enrolled(db, user, quiz.course_id):
        raise HTTPException(status_code=403, detail="Not enrolled")
    return quiz


@router.get("/quizzes/{quiz_id}/solve")
def get_quiz_solve_view(quiz_id: uuid.UUID, user: CurrentUser, db: Db) -> dict:
    """Questions for the standalone quiz-solving page.

    Serves the published quiz's questions WITHOUT `correct_answer` — the
    correct answer is only applied server-side at submit time.
    """
    from app.services.platform_service import _as_utc, _enrolled

    quiz = db.scalar(
        select(Quiz).where(
            Quiz.id == quiz_id,
            Quiz.institution_id == user.institution_id,
            Quiz.status == QuizStatus.PUBLISHED,
        )
    )
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if user.role == UserRole.STUDENT:
        if not _enrolled(db, user, quiz.course_id):
            raise HTTPException(status_code=403, detail="Not enrolled")
        # Lesson/payment gating mirrors the assessments listing.
        if quiz.lesson_id is not None and not can_access_lesson_content(db, user, quiz.lesson_id):
            raise HTTPException(status_code=403, detail="Lesson not unlocked")
        now = datetime.now(UTC)
        if _as_utc(quiz.starts_at) and _as_utc(quiz.starts_at) > now:
            raise HTTPException(status_code=403, detail="Quiz is not open yet")
        if _as_utc(quiz.ends_at) and _as_utc(quiz.ends_at) <= now:
            raise HTTPException(status_code=403, detail="Quiz is closed")

    rows = db.execute(
        select(QuizQuestion, Question)
        .join(Question, Question.id == QuizQuestion.question_id)
        .where(QuizQuestion.quiz_id == quiz.id, Question.is_active.is_(True))
        .order_by(QuizQuestion.position)
    ).all()
    total_points = sum(qq.points for qq, _q in rows)

    # The attempt clock starts when the student opens the solving page (or
    # resumes the already-running attempt) — otherwise duration_seconds would
    # never constrain anything. The countdown must be server-authoritative.
    attempt = None
    expires_at_iso: str | None = None
    if user.role == UserRole.STUDENT:
        try:
            attempt = platform_service.start_quiz(db, user, quiz.id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if attempt.expires_at is not None:
            expires_at_iso = attempt.expires_at.isoformat()

    def _safe_options(raw: object) -> object:
        """Strip answer-revealing flags (is_correct) from stored options."""
        if not isinstance(raw, list):
            return raw
        cleaned: list = []
        for opt in raw:
            if isinstance(opt, dict):
                cleaned.append({k: v for k, v in opt.items() if k not in {"is_correct", "correct"}})
            else:
                cleaned.append(opt)
        return cleaned

    return {
        "quiz": {
            "id": str(quiz.id),
            "title": quiz.title,
            "course_id": str(quiz.course_id),
            "lesson_id": str(quiz.lesson_id) if quiz.lesson_id else None,
            "duration_seconds": quiz.duration_seconds,
            "attempts_allowed": quiz.attempts_allowed,
            "starts_at": quiz.starts_at.isoformat() if quiz.starts_at else None,
            "ends_at": quiz.ends_at.isoformat() if quiz.ends_at else None,
            "total_points": float(total_points),
        },
        "attempt": (
            {
                "id": str(attempt.id),
                "attempt_number": attempt.attempt_number,
                "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                "expires_at": expires_at_iso,
                "is_practice": bool(attempt.is_practice),
            }
            if attempt is not None
            else None
        ),
        "questions": [
            {
                "id": str(question.id),
                "question_type": question.question_type,
                "prompt": question.prompt,
                "options": _safe_options(question.options),
                "points": float(qq.points),
            }
            for qq, question in rows
        ],
    }


@router.get("/assignments/{assignment_id}/solve")
def get_assignment_solve_view(assignment_id: uuid.UUID, user: CurrentUser, db: Db) -> dict:
    """Assignment details for the standalone solving page (download + upload)."""
    from app.services.platform_service import _as_utc, _enrolled

    assignment = db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.institution_id == user.institution_id,
            Assignment.status == AssignmentStatus.PUBLISHED,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if user.role == UserRole.STUDENT:
        if not _enrolled(db, user, assignment.course_id):
            raise HTTPException(status_code=403, detail="Not enrolled")
        if assignment.lesson_id is not None and not can_access_lesson_content(db, user, assignment.lesson_id):
            raise HTTPException(status_code=403, detail="Lesson not unlocked")

    latest_submission = db.scalar(
        select(AssignmentSubmission)
        .where(
            AssignmentSubmission.assignment_id == assignment.id,
            AssignmentSubmission.student_id == user.id,
        )
        .order_by(AssignmentSubmission.version.desc())
    ) if user.role == UserRole.STUDENT else None

    return {
        "id": str(assignment.id),
        "title": assignment.title,
        "prompt": assignment.prompt,
        "course_id": str(assignment.course_id),
        "lesson_id": str(assignment.lesson_id) if assignment.lesson_id else None,
        "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        "max_score": float(assignment.max_score or 0),
        "my_latest_submission": (
            {
                "id": str(latest_submission.id),
                "version": latest_submission.version,
                "status": latest_submission.status,
                "submitted_at": latest_submission.submitted_at.isoformat() if latest_submission.submitted_at else None,
                "has_file": bool(latest_submission.object_key),
            }
            if latest_submission
            else None
        ),
    }


ALLOWED_SUBMISSION_EXT = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_SUBMISSION_BYTES = 50 * 1024 * 1024  # 50MB


@router.get("/assignments/{assignment_id}/sheet.pdf")
def download_assignment_sheet(assignment_id: uuid.UUID, user: CurrentUser, db: Db):
    """Render the assignment questions as a printable Arabic PDF sheet.

    Students download this, solve on paper, then upload photographed/scanned
    copies through the submission endpoint. Content comes only from the
    assignment record — nothing is invented.
    """
    from app.services.assignment_sheet import render_assignment_sheet_pdf

    assignment = db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.institution_id == user.institution_id,
            Assignment.status == AssignmentStatus.PUBLISHED,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if user.role == UserRole.STUDENT:
        from app.services.platform_service import _enrolled

        if not _enrolled(db, user, assignment.course_id):
            raise HTTPException(status_code=403, detail="Not enrolled")
        if assignment.lesson_id is not None and not can_access_lesson_content(db, user, assignment.lesson_id):
            raise HTTPException(status_code=403, detail="Lesson not unlocked")

    try:
        pdf_bytes = render_assignment_sheet_pdf(
            title=assignment.title,
            prompt=assignment.prompt,
            max_score=float(assignment.max_score or 0),
            due_at=assignment.due_at,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    from urllib.parse import quote

    filename = f"assignment-{assignment.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/assignments/{assignment_id}/submissions/file", status_code=201)
async def upload_assignment_submission_file(
    request: Request,
    assignment_id: uuid.UUID,
    user: Student,
    db: Db,
    file: UploadFile = File(...),
) -> dict:
    """Store the student's photographed/typed solution file (PDF or image)."""
    enforce_rate_limit(request, bucket="upload")

    from app.core.storage import generate_safe_object_key, get_storage_provider
    from app.services.platform_service import _as_utc, _enrolled, submit_assignment

    assignment = db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.institution_id == user.institution_id,
            Assignment.status == AssignmentStatus.PUBLISHED,
        )
    )
    if assignment is None or not _enrolled(db, user, assignment.course_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.lesson_id is not None and not can_access_lesson_content(db, user, assignment.lesson_id):
        raise HTTPException(status_code=403, detail="Lesson not unlocked")

    filename = os.path.basename(file.filename or "submission")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_SUBMISSION_EXT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported submission type: {ext or 'unknown'} — upload a PDF or image",
        )

    storage = get_storage_provider()
    object_key = generate_safe_object_key("assignment_submissions", filename)
    size = 0
    tmp_dir = os.path.join(os.getenv("STORAGE_DIR", "storage"), "extraction_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    staged = os.path.join(tmp_dir, f"sub_{uuid.uuid4().hex[:12]}_{filename}")
    try:
        with open(staged, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_SUBMISSION_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Submission exceeds the 50MB limit",
                    )
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        storage.save_file(staged, object_key)
    finally:
        if os.path.exists(staged):
            try:
                os.remove(staged)
            except OSError:
                pass

    try:
        submission = submit_assignment(
            db,
            user,
            assignment_id,
            AssignmentSubmissionCreateRequest(
                answer_text=f"تسليم بملف: {filename}",
                object_key=object_key,
                idempotency_key=f"file-{uuid.uuid4().hex[:24]}",
            ),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        # Roll the stored file back if the submission is not acceptable.
        try:
            if storage.exists(object_key):
                storage.delete(object_key)
        except Exception:  # pragma: no cover
            pass
        detail = str(exc) or "Submission rejected"
        code = 404 if isinstance(exc, LookupError) else (403 if isinstance(exc, PermissionError) else 422)
        raise HTTPException(status_code=code, detail=detail) from exc

    return {
        "id": str(submission.id),
        "version": submission.version,
        "object_key": submission.object_key,
        "status": submission.status,
        "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
    }


# ---------------------------------------------------------------------------
# Lesson comments (discussion under each lesson's video)
# ---------------------------------------------------------------------------


def _comment_tree(db: Session, lesson_id: uuid.UUID, user: CurrentUser) -> list[dict]:
    rows = list(
        db.scalars(
            select(LessonComment)
            .where(LessonComment.lesson_id == lesson_id)
            .order_by(LessonComment.created_at.asc())
        ).all()
    )
    author_ids = {c.student_id for c in rows}
    user_map = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(author_ids))).all()
    } if author_ids else {}

    def to_dict(c: LessonComment) -> dict:
        u = user_map.get(c.student_id)
        is_teacher = bool(u and u.role == UserRole.TEACHER)
        return {
            "id": str(c.id),
            "author": (u.display_name if u else None) or ("المعلم" if is_teacher else "طالب"),
            "is_teacher": is_teacher,
            "role": u.role.value if u else "student",
            "is_mine": c.student_id == user.id,
            "parent_id": str(c.parent_id) if c.parent_id else None,
            "body": c.body,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }

    tops = [to_dict(c) for c in rows if c.parent_id is None]
    replies = [to_dict(c) for c in rows if c.parent_id is not None]
    by_parent: dict[str, list[dict]] = {}
    for r in replies:
        by_parent.setdefault(r["parent_id"] or "", []).append(r)
    for t in tops:
        t["replies"] = by_parent.get(t["id"], [])
    tops.reverse()  # newest first, replies stay chronological
    return tops


@router.get("/lessons/{lesson_id}/comments")
def list_lesson_comments(lesson_id: uuid.UUID, user: CurrentUser, db: Db) -> dict:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    module = db.get(CourseModule, lesson.module_id) if lesson.module_id else None
    course = db.get(Course, module.course_id) if module else None
    if course is None or course.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {"comments": _comment_tree(db, lesson_id, user)}


@router.post("/lessons/{lesson_id}/comments", status_code=201)
def add_lesson_comment(
    lesson_id: uuid.UUID,
    payload: dict,
    user: CurrentUser,
    db: Db,
    request: Request,
) -> dict:
    enforce_rate_limit(request, bucket="read")
    body = (payload.get("body") or "").strip()
    parent_raw = payload.get("parent_id")
    if not body or len(body) > 2000:
        raise HTTPException(status_code=422, detail="Comment must be 1..2000 characters")
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    module = db.get(CourseModule, lesson.module_id) if lesson.module_id else None
    course = db.get(Course, module.course_id) if module else None
    if course is None or course.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Lesson not found")
    parent: LessonComment | None = None
    if parent_raw:
        parent = db.get(LessonComment, uuid.UUID(str(parent_raw)))
        if parent is None or parent.lesson_id != lesson.id:
            raise HTTPException(status_code=422, detail="Parent comment not found")
    comment = LessonComment(
        institution_id=course.institution_id,
        lesson_id=lesson.id,
        student_id=user.id,
        parent_id=parent.id if parent else None,
        body=body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    is_teacher = user.role == UserRole.TEACHER
    return {
        "id": str(comment.id),
        "author": user.display_name or ("المعلم" if is_teacher else "طالب"),
        "is_teacher": is_teacher,
        "role": user.role.value,
        "is_mine": True,
        "parent_id": str(comment.parent_id) if comment.parent_id else None,
        "body": comment.body,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "replies": [],
    }
