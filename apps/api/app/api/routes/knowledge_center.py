"""
=============================================================================
AI TEACHING KNOWLEDGE CENTER — API ROUTES
=============================================================================
Endpoints for teacher source uploads (PDF, DOCX, PPTX, TXT, Images, Question Banks),
source indexing status, document inspection, reindexing, deletion, and knowledge search.
=============================================================================
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from starlette.concurrency import run_in_threadpool

_PDF_RENDER_LOCK = threading.Lock()
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_current_user, require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.course import Course, CourseModule, Lesson
from app.models.platform import Question
from app.models.knowledge_center import (
    AssessmentQuestion,
    AssessmentSource,
    KnowledgeAsset,
    KnowledgeDocument,
    KnowledgeLessonRelation,
    KnowledgeOutlineNode,
    KnowledgeQueryEvent,
    KnowledgeQuestionImageLink,
    KnowledgeQuestionRecord,
    KnowledgeSource,
    KnowledgeUnitRecord,
    SourceRole,
    SourceStatus,
)
from app.models.user import User, UserRole
from app.core.errors import OperationCancelledError
from app.core.storage import get_storage_provider
from app.services.knowledge_center_service import (
    clear_source_tracking,
    create_knowledge_source,
    delete_knowledge_source,
    dispatch_source_processing,
    is_parser_active,
    is_source_deleting,
    mark_parser_active,
    mark_parser_inactive,
    process_knowledge_source,
    register_cancellation,
    register_deleting,
    reindex_knowledge_source,
    sanitize_source_filename,
)
from app.services.knowledge_retriever import search_knowledge_base
from app.services.ai_access_policy import can_access_course_knowledge, enforce_ai_access
from app.api.dependencies import CurrentUser, DbSession, PreviewAuth, get_current_user, require_roles
from app.services.payment_service import can_access_lesson_content

router = APIRouter(prefix="/knowledge-center", tags=["knowledge-center"])
Db = Annotated[Session, Depends(get_db)]
TeacherOrAdmin = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]

_LOCAL_INGEST_EXECUTOR = ThreadPoolExecutor(
    max_workers=get_settings().max_concurrent_ingestions,
    thread_name_prefix="knowledge-ingestion",
)


def _run_bg_process_source(
    source_id: uuid.UUID,
    generation: int,
    attempt_id: uuid.UUID,
) -> None:
    """Runs knowledge source indexing and OCR in a background worker task with dedicated DB session."""
    import logging
    logger = logging.getLogger(__name__)
    from app.core.database import SessionLocal

    mark_parser_active(source_id)
    try:
        with SessionLocal() as db_session:
            try:
                process_knowledge_source(
                    db_session,
                    source_id,
                    generation=generation,
                    attempt_id=attempt_id,
                )
            except OperationCancelledError:
                logger.info("Background indexing cancelled cooperatively for source %s", source_id)
                try:
                    from app.models.knowledge_center import KnowledgeSource, SourceStatus
                    src = db_session.get(KnowledgeSource, source_id)
                    if src and not is_source_deleting(source_id):
                        src.status = SourceStatus.CANCELLED
                        src.error_message = "تم إيقاف الفهرسة (الملف محفوظ بالسيرفر)"
                        db_session.commit()
                except Exception:
                    db_session.rollback()
            except Exception as exc:
                logger.exception("Background indexing failed for source %s: %s", source_id, exc)
                try:
                    from app.models.knowledge_center import KnowledgeSource, SourceStatus
                    src = db_session.get(KnowledgeSource, source_id)
                    if src and src.status != SourceStatus.INDEXED:
                        src.status = SourceStatus.FAILED
                        src.error_message = str(exc)[:1000]
                        db_session.commit()
                except Exception:
                    db_session.rollback()
    finally:
        mark_parser_inactive(source_id)
        clear_source_tracking(source_id)


def _enqueue_source_processing(background_tasks: BackgroundTasks, source: KnowledgeSource, db: Session | None = None) -> None:
    """Dispatches processing via centralized dispatch_source_processing with row lock and claim."""
    if db is not None:
        dispatch_source_processing(db, source.id, background_tasks)
    else:
        from app.core.database import SessionLocal
        with SessionLocal() as s_db:
            dispatch_source_processing(s_db, source.id, background_tasks)


class KnowledgeSourceResponse(BaseModel):
    id: str
    course_id: str | None = None
    grade_level: str | None = None
    lesson_id: str | None = None
    filename: str
    file_format: str
    size_bytes: int
    source_role: str
    version: int
    checksum: str
    status: str
    upload_percent: int
    indexing_percent: int
    processing_generation: int
    processing_attempt_id: str
    progress_percent: int
    unit_count: int
    image_count: int
    table_count: int
    question_count: int
    total_pages: int | None = None
    error_message: str | None = None
    file_url: str | None = None
    created_at: str


class AssessmentQuestionUpdate(BaseModel):
    question_text: str | None = Field(default=None, min_length=1, max_length=20_000)
    question_type: str | None = Field(default=None, max_length=30)
    options_json: list[dict[str, Any]] | None = None
    correct_answer: str | None = Field(default=None, max_length=20_000)
    explanation: str | None = Field(default=None, max_length=20_000)
    points: float | None = Field(default=None, gt=0, le=1000)
    review_status: str | None = Field(default=None, max_length=30)


class AnswerKeyLinkRequest(BaseModel):
    answer_key_source_id: str | None = None


class PreviewTokenResponse(BaseModel):
    preview_token: str
    expires_in: int
    preview_url: str
    page_preview_url_template: str


def _parse_uuid(id_str: str | None) -> uuid.UUID | None:
    if not id_str or not str(id_str).strip():
        return None
    try:
        return uuid.UUID(str(id_str))
    except (TypeError, ValueError, AttributeError):
        return None


def _resolve_course_uuid(db: Session, user: User, course_id: str | None) -> uuid.UUID:
    if not course_id or not str(course_id).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="course_id is required",
        )
    course_uuid = _parse_uuid(course_id)
    if not course_uuid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid course ID format",
        )
    stmt = select(Course).where(Course.id == course_uuid)
    if user.role != UserRole.PLATFORM_ADMIN:
        stmt = stmt.where(Course.institution_id == user.institution_id)
    existing = db.scalar(stmt)
    if not existing:
        raise HTTPException(status_code=404, detail="Course not found")
    if user.role == UserRole.TEACHER and existing.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Course not found")
    return existing.id


def _resolve_lesson_uuid(
    db: Session, course_id: uuid.UUID, lesson_id: str | None
) -> uuid.UUID | None:
    if not lesson_id:
        return None
    lesson_uuid = _parse_uuid(lesson_id)
    if not lesson_uuid:
        raise HTTPException(status_code=400, detail="Invalid lesson ID")
    lesson = db.scalar(
        select(Lesson)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .where(Lesson.id == lesson_uuid, CourseModule.course_id == course_id)
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found in this course")
    return lesson.id


_UPLOAD_SOURCE_ROLES = {
    SourceRole.COURSE_KNOWLEDGE,
    SourceRole.LESSON_MATERIAL,
}


def _validate_upload_scope(
    source_role: str,
    lesson_id: str | None,
    grade_level: str | None = None,
) -> SourceRole:
    """Validate the role/lesson contract before accepting any file bytes."""
    try:
        normalized_role = SourceRole(str(source_role).strip().upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid source_role",
        ) from exc

    if normalized_role == SourceRole.KNOWLEDGE:
        normalized_role = SourceRole.COURSE_KNOWLEDGE
    if normalized_role not in _UPLOAD_SOURCE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source_role must be COURSE_KNOWLEDGE or LESSON_MATERIAL; quiz and assessment imports use their dedicated endpoints",
        )
    if normalized_role == SourceRole.LESSON_MATERIAL and not lesson_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="lesson_id is required for LESSON_MATERIAL",
        )
    if normalized_role == SourceRole.COURSE_KNOWLEDGE and lesson_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="lesson_id is not allowed for COURSE_KNOWLEDGE",
        )
    if normalized_role == SourceRole.COURSE_KNOWLEDGE:
        if not grade_level or str(grade_level).strip() not in {"SECONDARY_1", "SECONDARY_2", "SECONDARY_3"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="grade_level must be one of SECONDARY_1, SECONDARY_2, SECONDARY_3 for COURSE_KNOWLEDGE",
            )
    return normalized_role


from contextlib import contextmanager

class _RefCountedLock:
    def __init__(self):
        self.lock = threading.Lock()
        self.ref_count = 0

_RENDER_REGISTRY_GUARD = threading.Lock()
_SOURCE_RENDER_LOCKS: dict[uuid.UUID, _RefCountedLock] = {}
_SOURCE_STAGE_LOCKS: dict[uuid.UUID, _RefCountedLock] = {}
_GLOBAL_RENDER_SEMAPHORE = threading.BoundedSemaphore(4)


@contextmanager
def _get_source_render_lock(source_id: uuid.UUID):
    with _RENDER_REGISTRY_GUARD:
        if source_id not in _SOURCE_RENDER_LOCKS:
            _SOURCE_RENDER_LOCKS[source_id] = _RefCountedLock()
        rc = _SOURCE_RENDER_LOCKS[source_id]
        rc.ref_count += 1
    try:
        with rc.lock:
            yield
    finally:
        with _RENDER_REGISTRY_GUARD:
            rc.ref_count -= 1
            if rc.ref_count <= 0:
                _SOURCE_RENDER_LOCKS.pop(source_id, None)


@contextmanager
def _get_source_stage_lock(source_id: uuid.UUID):
    with _RENDER_REGISTRY_GUARD:
        if source_id not in _SOURCE_STAGE_LOCKS:
            _SOURCE_STAGE_LOCKS[source_id] = _RefCountedLock()
        rc = _SOURCE_STAGE_LOCKS[source_id]
        rc.ref_count += 1
    try:
        with rc.lock:
            yield
    finally:
        with _RENDER_REGISTRY_GUARD:
            rc.ref_count -= 1
            if rc.ref_count <= 0:
                _SOURCE_STAGE_LOCKS.pop(source_id, None)


def _inspect_pdf_page_count_fast(file_path: str) -> int:
    """Pre-flight verification of PDF integrity and page count with bounded memory."""
    with open(file_path, "rb") as f:
        magic = f.read(5)
        if magic != b"%PDF-":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="الملف تالف أو ليس مستند PDF صالحًا",
            )
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(file_path)
        try:
            page_count = len(pdf)
            if page_count <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="مستند PDF لا يحتوي على أي صفحات",
                )
            return page_count
        finally:
            pdf.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"فشل التحقق من صحة ملف PDF: {str(exc)}",
        ) from exc


def _get_kc_temp_dir() -> str:
    storage_dir = os.getenv("STORAGE_DIR", "storage/knowledge_center")
    tmp = os.path.join(storage_dir, "tmp")
    os.makedirs(tmp, exist_ok=True)
    return tmp





async def _stream_upload_to_file(
    uploaded: UploadFile,
    dest_path: str,
    max_file_bytes: int,
    current_batch_bytes: int = 0,
    max_batch_bytes: int = 0,
) -> tuple[int, str]:
    """
    Streams an UploadFile directly to a file on disk in ~1 MiB chunks.
    Monitors file-level and batch-level size limits incrementally.
    Computes SHA-256 hash on the fly with bounded memory usage.
    Returns (bytes_written, sha256_hex).
    """
    hasher = hashlib.sha256()
    file_bytes_written = 0
    try:
        with open(dest_path, "wb") as f:
            while chunk := await uploaded.read(1024 * 1024):
                file_bytes_written += len(chunk)
                if file_bytes_written > max_file_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File exceeds the {max_file_bytes // (1024 * 1024)} MB limit",
                    )
                if max_batch_bytes > 0 and (current_batch_bytes + file_bytes_written) > max_batch_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Batch exceeds the {max_batch_bytes // (1024 * 1024)} MB total limit",
                    )
                hasher.update(chunk)
                f.write(chunk)
    except Exception:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        raise
    return file_bytes_written, hasher.hexdigest()


def _get_source_for_user(db: Session, source_id: uuid.UUID | None, user: User) -> KnowledgeSource:
    source = db.get(KnowledgeSource, source_id) if source_id else None
    if not source or (user.role != UserRole.PLATFORM_ADMIN and source.institution_id != user.institution_id):
        raise HTTPException(status_code=404, detail="Source not found")
    if user.role == UserRole.TEACHER:
        if source.course_id:
            course = db.get(Course, source.course_id)
            if not course or course.teacher_id != user.id:
                raise HTTPException(status_code=404, detail="Source not found")
        else:
            if source.teacher_id != user.id:
                raise HTTPException(status_code=404, detail="Source not found")
    if user.role == UserRole.STUDENT:
        if source.source_role in {
            SourceRole.ASSESSMENT,
            SourceRole.QUIZ_IMPORT,
            SourceRole.ANSWER_KEY,
        }:
            raise HTTPException(status_code=404, detail="Source not found")
        # Grade isolation & unclassified legacy exclusion for students (applies to COURSE_KNOWLEDGE):
        if source.source_role != SourceRole.LESSON_MATERIAL:
            if not user.grade_level or not source.grade_level or source.grade_level != user.grade_level:
                raise HTTPException(status_code=403, detail="Grade level access denied")
        if source.lesson_id:
            allowed = can_access_lesson_content(db, user, source.lesson_id)
        elif source.course_id:
            allowed = can_access_course_knowledge(db, user, source.course_id)
        else:
            allowed = True
        if not allowed:
            raise HTTPException(status_code=403, detail="Course access denied")
    return source


def _source_response(source: KnowledgeSource, total_pages: int | None = None) -> KnowledgeSourceResponse:
    eff_pages = total_pages
    if eff_pages is None:
        eff_pages = getattr(source, "preview_total_pages", None)
    if eff_pages is None:
        if source.file_format in ("png", "jpg", "jpeg", "webp", "image"):
            eff_pages = 1
        else:
            eff_pages = None

    return KnowledgeSourceResponse(
        id=str(source.id),
        course_id=str(source.course_id) if source.course_id else None,
        grade_level=source.grade_level,
        lesson_id=str(source.lesson_id) if source.lesson_id else None,
        filename=source.filename,
        file_format=source.file_format,
        size_bytes=source.size_bytes,
        source_role=source.source_role,
        version=source.version,
        checksum=source.checksum,
        status=source.status,
        upload_percent=source.upload_percent,
        indexing_percent=source.indexing_percent,
        processing_generation=source.processing_generation,
        processing_attempt_id=str(source.processing_attempt_id),
        progress_percent=source.progress_percent,
        unit_count=source.unit_count,
        image_count=source.image_count,
        table_count=source.table_count,
        question_count=source.question_count,
        total_pages=eff_pages,
        error_message=source.error_message,
        file_url=f"/api/v1/knowledge-center/sources/{source.id}/view",
        created_at=source.created_at.isoformat(),
    )


@router.post("/sources/upload", response_model=KnowledgeSourceResponse)
async def upload_knowledge_source(
    request: Request,
    db: Db,
    user: TeacherOrAdmin,
    background_tasks: BackgroundTasks,
    course_id: str | None = Form(None),
    grade_level: str | None = Form(None),
    lesson_id: str | None = Form(None),
    source_role: str = Form(SourceRole.COURSE_KNOWLEDGE),
    assessment_type: str | None = Form(None),
    answer_key_source_id: str | None = Form(None),
    file: UploadFile = File(...),
) -> KnowledgeSourceResponse:
    enforce_rate_limit(request, bucket="upload", limit=50, window_seconds=60)
    settings = get_settings()
    max_file_bytes = settings.max_file_size_mb * 1024 * 1024

    grade_level_clean = str(grade_level).strip() if grade_level else None

    # Strict Tenant Authorization Sequence (P0-4):
    # 1. Parse source role
    role_str = str(source_role).split(".")[-1].strip().upper()
    try:
        parsed_role = SourceRole(role_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source role: {source_role}")

    # 2. Resolve course using tenant and teacher ownership
    course_uuid: uuid.UUID | None = None
    lesson_uuid: uuid.UUID | None = None
    course_obj: Course | None = None
    if course_id and str(course_id).strip():
        course_uuid = _resolve_course_uuid(db, user, course_id)
        course_obj = db.get(Course, course_uuid)
        # 3. Read course.grade_level if grade_level not explicitly provided
        if not grade_level_clean and course_obj and course_obj.grade_level:
            grade_level_clean = course_obj.grade_level

    # 4. Validate upload scope
    normalized_role = _validate_upload_scope(parsed_role, lesson_id, grade_level_clean)

    if normalized_role == SourceRole.LESSON_MATERIAL:
        if not course_id or not str(course_id).strip() or not course_uuid or not course_obj:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="course_id is required for LESSON_MATERIAL",
            )
        if not course_obj.grade_level:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="المقرر غير مصنف، يرجى تحديد الصف الدراسي للمقرر أولاً",
            )
        grade_level_clean = course_obj.grade_level
        lesson_uuid = _resolve_lesson_uuid(db, course_uuid, lesson_id)

    tmp_dir = _get_kc_temp_dir()
    safe_name = sanitize_source_filename(file.filename or "uploaded_file")
    staging_file = os.path.join(tmp_dir, f"stage_{uuid.uuid4().hex[:12]}_{safe_name}")
    created_storage_keys: list[str] = []

    try:
        size_bytes, checksum = await _stream_upload_to_file(
            uploaded=file,
            dest_path=staging_file,
            max_file_bytes=max_file_bytes,
        )
        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="الملف المرفوع فارغ (0 بايت)")

        ext = os.path.splitext(file.filename or safe_name)[1].lower().lstrip(".")
        preview_pages = None
        if ext == "pdf":
            preview_pages = await run_in_threadpool(_inspect_pdf_page_count_fast, staging_file)

        result = create_knowledge_source(
            db=db,
            user=user,
            course_id=course_uuid,
            grade_level=grade_level_clean,
            lesson_id=lesson_uuid,
            filename=file.filename or safe_name,
            staged_file_path=staging_file,
            checksum=checksum,
            size_bytes=size_bytes,
            source_role=normalized_role,
            mime_type=file.content_type,
            metadata={
                "assessment_type": assessment_type,
                "answer_key_source_id": answer_key_source_id,
            },
            commit=False,
            created_storage_paths=created_storage_keys,
            preview_total_pages=preview_pages,
        )
        source = result.source
        if result.created:
            source.status = SourceStatus.QUEUED
            source.upload_percent = 100
            source.indexing_percent = 0
            source.progress_percent = 0
            if preview_pages is not None:
                source.preview_total_pages = preview_pages
            db.commit()
            db.refresh(source)
            dispatch_source_processing(db, source.id, background_tasks)
        else:
            db.commit()
            db.refresh(source)

        return _source_response(source)
    except Exception:
        db.rollback()
        storage = get_storage_provider()
        for k in created_storage_keys:
            try:
                storage.delete(k)
            except Exception:
                pass
        raise
    finally:
        if os.path.exists(staging_file):
            try:
                os.remove(staging_file)
            except OSError:
                pass


@router.post("/sources/upload-batch", response_model=list[KnowledgeSourceResponse])
async def upload_knowledge_sources_batch(
    request: Request,
    db: Db,
    user: TeacherOrAdmin,
    background_tasks: BackgroundTasks,
    course_id: str | None = Form(None),
    grade_level: str | None = Form(None),
    lesson_id: str | None = Form(None),
    source_role: str = Form(SourceRole.COURSE_KNOWLEDGE),
    assessment_type: str | None = Form(None),
    answer_key_source_id: str | None = Form(None),
    files: list[UploadFile] = File(...),
) -> list[KnowledgeSourceResponse]:
    """Create one source per uploaded book and enqueue each independently with atomic staging."""
    enforce_rate_limit(request, bucket="upload", limit=50, window_seconds=60)
    if not files:
        raise HTTPException(status_code=400, detail="يجب اختيار ملف واحد على الأقل للرفع")
    if len(files) > 25:
        raise HTTPException(status_code=400, detail="الحد الأقصى للرفع دفعة واحدة هو 25 ملفاً")

    settings = get_settings()
    max_file_bytes = settings.max_file_size_mb * 1024 * 1024
    max_batch_bytes = settings.max_batch_size_mb * 1024 * 1024

    grade_level_clean = str(grade_level).strip() if grade_level else None

    # Strict Tenant Authorization Sequence (P0-4):
    # 1. Parse source role
    role_str = str(source_role).split(".")[-1].strip().upper()
    try:
        parsed_role = SourceRole(role_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source role: {source_role}")

    # 2. Resolve course using tenant and teacher ownership
    course_uuid: uuid.UUID | None = None
    lesson_uuid: uuid.UUID | None = None
    course_obj: Course | None = None
    if course_id and str(course_id).strip():
        course_uuid = _resolve_course_uuid(db, user, course_id)
        course_obj = db.get(Course, course_uuid)
        # 3. Read course.grade_level if grade_level not explicitly provided
        if not grade_level_clean and course_obj and course_obj.grade_level:
            grade_level_clean = course_obj.grade_level

    # 4. Validate upload scope
    normalized_role = _validate_upload_scope(parsed_role, lesson_id, grade_level_clean)

    if normalized_role == SourceRole.LESSON_MATERIAL:
        if not course_id or not str(course_id).strip() or not course_uuid or not course_obj:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="course_id is required for LESSON_MATERIAL",
            )
        if not course_obj.grade_level:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="المقرر غير مصنف، يرجى تحديد الصف الدراسي للمقرر أولاً",
            )
        grade_level_clean = course_obj.grade_level
        lesson_uuid = _resolve_lesson_uuid(db, course_uuid, lesson_id)

    tmp_base = _get_kc_temp_dir()
    batch_stage_dir = tempfile.mkdtemp(prefix=f"batch_stage_{uuid.uuid4().hex[:12]}_", dir=tmp_base)

    staged_items: list[dict[str, Any]] = []
    batch_total_bytes = 0

    try:
        # Phase 1: Stream and validate all files into isolated staging directory
        for idx, uploaded in enumerate(files):
            safe_name = sanitize_source_filename(uploaded.filename or f"upload_{idx}")
            staged_path = os.path.join(batch_stage_dir, f"file_{idx}_{uuid.uuid4().hex[:8]}_{safe_name}")

            size_bytes, checksum = await _stream_upload_to_file(
                uploaded=uploaded,
                dest_path=staged_path,
                max_file_bytes=max_file_bytes,
                current_batch_bytes=batch_total_bytes,
                max_batch_bytes=max_batch_bytes,
            )
            batch_total_bytes += size_bytes
            if size_bytes == 0:
                continue

            staged_items.append({
                "staged_path": staged_path,
                "filename": uploaded.filename or safe_name,
                "mime_type": uploaded.content_type,
                "size_bytes": size_bytes,
                "checksum": checksum,
            })

        if not staged_items:
            raise HTTPException(status_code=400, detail="كافة الملفات المرفوعة فارغة (0 بايت)")

        # Pre-flight inspect all PDF files BEFORE creating DB rows or permanent storage
        preview_pages_map: dict[str, int] = {}
        for item in staged_items:
            ext = os.path.splitext(item["filename"])[1].lower().lstrip(".")
            if ext == "pdf":
                page_count = await run_in_threadpool(_inspect_pdf_page_count_fast, item["staged_path"])
                preview_pages_map[item["staged_path"]] = page_count

        # Phase 2: Move files and create database records atomically
        created_results: list[Any] = []
        newly_created_permanent_paths: list[str] = []

        try:
            for item in staged_items:
                res = create_knowledge_source(
                    db=db,
                    user=user,
                    course_id=course_uuid,
                    grade_level=grade_level_clean,
                    lesson_id=lesson_uuid,
                    filename=item["filename"],
                    staged_file_path=item["staged_path"],
                    checksum=item["checksum"],
                    size_bytes=item["size_bytes"],
                    source_role=normalized_role,
                    mime_type=item["mime_type"],
                    metadata={
                        "batch_upload": True,
                        "assessment_type": assessment_type,
                        "answer_key_source_id": answer_key_source_id,
                    },
                    commit=False,
                    created_storage_paths=newly_created_permanent_paths,
                    preview_total_pages=preview_pages_map.get(item["staged_path"]),
                )

                if res.created:
                    res.source.status = SourceStatus.QUEUED
                    res.source.upload_percent = 100
                    res.source.indexing_percent = 0
                    res.source.progress_percent = 0
                    if preview_pages_map.get(item["staged_path"]) is not None:
                        res.source.preview_total_pages = preview_pages_map[item["staged_path"]]

                created_results.append(res)

            db.commit()
        except Exception:
            db.rollback()
            storage = get_storage_provider()
            for p in newly_created_permanent_paths:
                try:
                    storage.delete(p)
                except Exception:
                    pass
            raise

        for res in created_results:
            db.refresh(res.source)
            if res.created:
                _enqueue_source_processing(background_tasks, res.source)

        return [_source_response(res.source) for res in created_results]
    finally:
        if os.path.exists(batch_stage_dir):
            shutil.rmtree(batch_stage_dir, ignore_errors=True)



@router.get("/sources", response_model=list[KnowledgeSourceResponse])
def list_knowledge_sources(
    request: Request,
    db: Db,
    user: TeacherOrAdmin,
    course_id: str | None = None,
    grade_level: str | None = None,
    lesson_id: str | None = None,
    source_role: str | None = None,
) -> list[KnowledgeSourceResponse]:
    stmt = select(KnowledgeSource)
    if user.role != UserRole.PLATFORM_ADMIN:
        stmt = stmt.where(KnowledgeSource.institution_id == user.institution_id)
    if user.role == UserRole.TEACHER:
        stmt = stmt.where(KnowledgeSource.teacher_id == user.id)
    if grade_level and grade_level.strip():
        stmt = stmt.where(KnowledgeSource.grade_level == grade_level.strip())
    if course_id and course_id.strip():
        course_uuid = _resolve_course_uuid(db, user, course_id)
        stmt = stmt.where(KnowledgeSource.course_id == course_uuid)
    if lesson_id and lesson_id.strip():
        lesson_uuid = _parse_uuid(lesson_id)
        if not lesson_uuid:
            raise HTTPException(status_code=422, detail="Invalid lesson ID format")
        lesson_course_id = db.scalar(
            select(CourseModule.course_id)
            .join(Lesson, Lesson.module_id == CourseModule.id)
            .where(Lesson.id == lesson_uuid)
        )
        if not lesson_course_id:
            raise HTTPException(status_code=404, detail="Lesson not found")
        _resolve_course_uuid(db, user, str(lesson_course_id))
        if course_id and lesson_course_id != course_uuid:
            raise HTTPException(status_code=404, detail="Lesson not found in this course")
        stmt = stmt.where(
            KnowledgeSource.lesson_id == lesson_uuid,
            KnowledgeSource.source_role == SourceRole.LESSON_MATERIAL,
        )
    elif not source_role:
        # The general Knowledge Center is intentionally course-knowledge only.
        stmt = stmt.where(
            KnowledgeSource.source_role.in_(
                [SourceRole.COURSE_KNOWLEDGE, SourceRole.KNOWLEDGE]
            )
        )

    if source_role and source_role.strip():
        requested_role = source_role.strip().upper()
        try:
            normalized_role = SourceRole(requested_role)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid source_role") from exc
        stmt = stmt.where(KnowledgeSource.source_role == normalized_role)

    sources = db.scalars(stmt.order_by(KnowledgeSource.created_at.desc())).all()
    source_ids = [s.id for s in sources]
    docs = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_id.in_(source_ids))).all() if source_ids else []
    pages_map = {d.source_id: d.total_pages for d in docs}

    return [
        _source_response(s, total_pages=pages_map.get(s.id, 1 if s.file_format != "pdf" else None))
        for s in sources
    ]


@router.post("/sources/mark-interrupted")
async def mark_sources_interrupted(
    request: Request,
    db: Db,
    user: TeacherOrAdmin,
) -> dict[str, Any]:
    """Deprecated no-op kept for old clients.

    The upload has already reached durable storage before a source is QUEUED.
    A page unload is not a worker failure and must never mutate the server-side
    processing attempt.  Workers own terminal state transitions instead.
    """
    return {"status": "ok", "marked": 0}

@router.get("/sources/{source_id}")
def get_knowledge_source_detail(source_id: str, db: Db, user: CurrentUser) -> dict[str, Any]:
    s_uuid = _parse_uuid(source_id)
    source = _get_source_for_user(db, s_uuid, user)

    doc = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.source_id == s_uuid))
    assets = db.scalars(select(KnowledgeAsset).where(KnowledgeAsset.source_id == s_uuid)).all()
    units = db.scalars(select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == s_uuid).limit(50)).all()
    assessment = db.scalar(select(AssessmentSource).where(AssessmentSource.source_id == s_uuid))
    question_records = db.scalars(
        select(KnowledgeQuestionRecord)
        .where(KnowledgeQuestionRecord.source_id == s_uuid)
        .order_by(KnowledgeQuestionRecord.page_number.asc().nullslast(), KnowledgeQuestionRecord.question_order.asc())
    ).all()
    image_links = db.scalars(
        select(KnowledgeQuestionImageLink)
        .join(KnowledgeQuestionRecord, KnowledgeQuestionImageLink.question_record_id == KnowledgeQuestionRecord.id)
        .where(KnowledgeQuestionRecord.source_id == s_uuid)
        .order_by(KnowledgeQuestionImageLink.position.asc())
    ).all()
    links_by_question: dict[uuid.UUID, list[KnowledgeQuestionImageLink]] = {}
    for image_link in image_links:
        links_by_question.setdefault(image_link.question_record_id, []).append(image_link)
    lesson_relations = db.scalars(
        select(KnowledgeLessonRelation)
        .where(KnowledgeLessonRelation.source_id == s_uuid)
        .order_by(KnowledgeLessonRelation.created_at.asc())
    ).all()
    outline = db.scalars(
        select(KnowledgeOutlineNode)
        .where(KnowledgeOutlineNode.source_id == s_uuid)
        .order_by(KnowledgeOutlineNode.position.asc())
    ).all()

    total_pages = doc.total_pages if doc else (1 if source.file_format != "pdf" else None)

    return {
        "id": str(source.id),
        "course_id": str(source.course_id) if source.course_id else None,
        "grade_level": source.grade_level,
        "lesson_id": str(source.lesson_id) if source.lesson_id else None,
        "filename": source.filename,
        "file_format": source.file_format,
        "size_bytes": source.size_bytes,
        "source_role": source.source_role,
        "version": source.version,
        "checksum": source.checksum,
        "status": source.status,
        "upload_percent": source.upload_percent,
        "indexing_percent": source.indexing_percent,
        "processing_generation": source.processing_generation,
        "processing_attempt_id": str(source.processing_attempt_id),
        "progress_percent": source.progress_percent,
        "error_message": source.error_message,
        "unit_count": source.unit_count,
        "image_count": source.image_count,
        "table_count": source.table_count,
        "question_count": source.question_count,
        "total_pages": total_pages,
        "file_url": f"/api/v1/knowledge-center/sources/{source.id}/view",
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "document": {
            "title": doc.title,
            "doc_type": doc.doc_type,
            "total_pages": doc.total_pages,
            "total_slides": doc.total_slides,
            "hierarchy": doc.hierarchy_json,
        } if doc else None,
        "images": [
            {
                "id": str(a.id),
                "asset_kind": a.asset_kind,
                "caption": a.caption,
                "page_number": a.page_number,
                "slide_number": a.slide_number,
                "storage_path": a.storage_path,
                "outline_node_id": str(a.outline_node_id) if a.outline_node_id else None,
                "ocr_text": (a.metadata_json or {}).get("ocr_text"),
            }
            for a in assets
        ],
        "units": [
            {
                "id": str(u.id),
                "concept": u.concept,
                "statement": u.statement,
                "page_number": u.page_number,
                "slide_number": u.slide_number,
                "type": u.knowledge_type,
                "outline_node_id": str(u.outline_node_id) if u.outline_node_id else None,
            }
            for u in units
        ],
        "extracted_questions": [
            {
                "id": str(question.id),
                "order": question.question_order,
                "question_text": question.question_text,
                "question_type": question.question_type,
                "correct_answer": question.correct_answer,
                "page_number": question.page_number,
                "slide_number": question.slide_number,
                "outline_node_id": str(question.outline_node_id) if question.outline_node_id else None,
                "hierarchy": (question.metadata_json or {}).get("hierarchy", {}),
                "image_asset_ids": question.image_asset_ids_json or [],
                "image_links": [
                    {"asset_id": str(link.asset_id), "relation_type": link.relation_type, "confidence": link.confidence, "evidence": link.evidence_json}
                    for link in links_by_question.get(question.id, [])
                ],
            }
            for question in question_records
        ],
        "lesson_relations": [
            {
                "from_outline_node_id": str(relation.from_outline_node_id),
                "to_outline_node_id": str(relation.to_outline_node_id),
                "relation_type": relation.relation_type,
                "confidence": relation.confidence,
                "evidence": relation.evidence_json,
            }
            for relation in lesson_relations
        ],
        "assessment": {
            "id": str(assessment.id),
            "assessment_type": assessment.assessment_type,
            "title": assessment.title,
            "total_questions": assessment.total_questions,
            "processing_status": assessment.processing_status,
            "review_status": assessment.review_status,
            "answer_key_source_id": str(assessment.answer_key_source_id) if assessment.answer_key_source_id else None,
        } if assessment else None,
        "outline": [
            {
                "id": str(node.id),
                "parent_id": str(node.parent_id) if node.parent_id else None,
                "kind": node.node_kind,
                "title": node.title,
                "position": node.position,
                "start_page": node.start_page,
                "end_page": node.end_page,
            }
            for node in outline
        ],
    }


@router.get("/sources/{source_id}/outline")
def get_source_outline(source_id: str, db: Db, user: CurrentUser) -> list[dict[str, Any]]:
    source_uuid = _parse_uuid(source_id)
    _get_source_for_user(db, source_uuid, user)
    nodes = db.scalars(
        select(KnowledgeOutlineNode)
        .where(KnowledgeOutlineNode.source_id == source_uuid)
        .order_by(KnowledgeOutlineNode.position.asc())
    ).all()
    return [
        {
            "id": str(node.id), "parent_id": str(node.parent_id) if node.parent_id else None,
            "kind": node.node_kind, "title": node.title, "position": node.position,
            "start_page": node.start_page, "end_page": node.end_page,
        }
        for node in nodes
    ]


@router.get("/sources/{source_id}/lesson-relations")
def get_source_lesson_relations(source_id: str, db: Db, user: CurrentUser) -> list[dict[str, Any]]:
    source_uuid = _parse_uuid(source_id)
    _get_source_for_user(db, source_uuid, user)
    relations = db.scalars(
        select(KnowledgeLessonRelation)
        .where(KnowledgeLessonRelation.source_id == source_uuid)
        .order_by(KnowledgeLessonRelation.created_at.asc())
    ).all()
    return [
        {
            "from_outline_node_id": str(relation.from_outline_node_id),
            "to_outline_node_id": str(relation.to_outline_node_id),
            "relation_type": relation.relation_type,
            "confidence": relation.confidence,
            "evidence": relation.evidence_json,
        }
        for relation in relations
    ]


@router.get("/analytics/query-summary")
def knowledge_query_summary(course_id: str, db: Db, user: TeacherOrAdmin) -> dict[str, Any]:
    course_uuid = _parse_uuid(course_id)
    course = db.get(Course, course_uuid)
    if not course or (user.role != UserRole.PLATFORM_ADMIN and course.institution_id != user.institution_id):
        raise HTTPException(status_code=404, detail="Course not found")
    outcome_rows = db.execute(
        select(KnowledgeQueryEvent.outcome, func.count(KnowledgeQueryEvent.id))
        .where(KnowledgeQueryEvent.course_id == course_uuid)
        .group_by(KnowledgeQueryEvent.outcome)
    ).all()
    outline_rows = db.execute(
        select(KnowledgeOutlineNode.title, func.count(KnowledgeQueryEvent.id))
        .join(KnowledgeQueryEvent, KnowledgeQueryEvent.outline_node_id == KnowledgeOutlineNode.id)
        .where(KnowledgeQueryEvent.course_id == course_uuid)
        .group_by(KnowledgeOutlineNode.title)
        .order_by(func.count(KnowledgeQueryEvent.id).desc())
        .limit(10)
    ).all()
    unanswered = db.scalars(
        select(KnowledgeQueryEvent.query_text)
        .where(KnowledgeQueryEvent.course_id == course_uuid, KnowledgeQueryEvent.outcome == "not_found")
        .order_by(KnowledgeQueryEvent.created_at.desc())
        .limit(20)
    ).all()
    return {
        "outcomes": {outcome: count for outcome, count in outcome_rows},
        "most_queried_outline_nodes": [{"title": title, "count": count} for title, count in outline_rows],
        "unanswered_queries": unanswered,
    }


@router.post("/sources/{source_id}/reindex", response_model=KnowledgeSourceResponse)
def reindex_source(source_id: str, db: Db, background_tasks: BackgroundTasks, user: TeacherOrAdmin) -> KnowledgeSourceResponse:
    s_uuid = _parse_uuid(source_id)
    if not s_uuid:
        raise HTTPException(status_code=400, detail="Invalid source ID")

    # Acquire row-level lock within the transaction to prevent concurrent race conditions
    stmt = select(KnowledgeSource).where(KnowledgeSource.id == s_uuid).with_for_update()
    if user.role != UserRole.PLATFORM_ADMIN:
        stmt = stmt.where(KnowledgeSource.institution_id == user.institution_id)
    source = db.scalar(stmt)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if user.role == UserRole.TEACHER and source.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to reindex this source")

    # Re-check status under lock
    if source.status in {SourceStatus.QUEUED, SourceStatus.PROCESSING}:
        # Active: return 200 with current active attempt without re-enqueuing
        return _source_response(source)

    # Terminal state: bump version & generation once, record previous attempt, commit and enqueue once
    source.version += 1
    previous_attempt_id = source.processing_attempt_id
    source.processing_generation += 1
    source.processing_attempt_id = uuid.uuid4()
    source.active_task_id = None
    source.status = SourceStatus.QUEUED
    source.indexing_percent = 0
    source.progress_percent = 0
    source.error_message = None
    source.metadata_json = {
        **(source.metadata_json or {}),
        "retry_of_attempt_id": str(previous_attempt_id),
    }
    db.commit()
    db.refresh(source)

    _enqueue_source_processing(background_tasks, source)
    return _source_response(source)


@router.post("/sources/{source_id}/stop-indexing")
def stop_indexing_source(source_id: str, db: Db, user: TeacherOrAdmin) -> dict[str, Any]:
    """Stops source indexing gracefully without deleting the file from server storage."""
    s_uuid = _parse_uuid(source_id)
    if not s_uuid:
        raise HTTPException(status_code=400, detail="Invalid source ID")

    # Register in-memory cancellation immediately so any active parsing thread stops at the next page
    register_cancellation(s_uuid)

    stmt = select(KnowledgeSource).where(KnowledgeSource.id == s_uuid)
    if db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()

    source = db.scalar(stmt)
    if not source:
        return {"status": "ok", "message": "المصدر غير موجود", "source_status": "NOT_FOUND"}

    if user and user.role != UserRole.PLATFORM_ADMIN and source.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Source not found")

    # Idempotent check
    if source.status in (SourceStatus.STOPPED, SourceStatus.CANCELLED, SourceStatus.FAILED):
        return {"status": "ok", "message": "تم إيقاف الفهرسة مسبقاً", "source_status": source.status}

    source.status = SourceStatus.CANCELLED
    source.processing_generation += 1
    source.processing_attempt_id = uuid.uuid4()
    source.error_message = "تم إيقاف الفهرسة (الملف محفوظ بالسيرفر)"
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"status": "ok", "message": "تم إيقاف الفهرسة وحفظ الملف بالسيرفر", "source_status": source.status}


@router.delete("/sources/{source_id}")
def delete_source(source_id: str, db: Db, user: TeacherOrAdmin) -> dict[str, Any]:
    s_uuid = _parse_uuid(source_id)
    if not s_uuid:
        raise HTTPException(status_code=400, detail="Invalid source ID")

    source = db.get(KnowledgeSource, s_uuid)
    if not source:
        # Idempotent deletion: already deleted
        clear_source_tracking(s_uuid)
        return {"success": True, "deleted_id": source_id, "status": "already_deleted"}

    if user.role != UserRole.PLATFORM_ADMIN and source.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Source not found")

    # Signal cooperative cancellation to any background worker running on this source
    register_deleting(s_uuid)

    # If the background parser is actively running, set status to DELETING, commit,
    # and wait cooperatively up to 500ms for it to exit cleanly
    if is_parser_active(s_uuid) or source.status == SourceStatus.PROCESSING:
        source.status = SourceStatus.DELETING
        try:
            db.commit()
        except Exception:
            db.rollback()
        import time
        for _ in range(10):
            if not is_parser_active(s_uuid):
                break
            time.sleep(0.05)

    delete_knowledge_source(db, s_uuid)
    return {"success": True, "deleted_id": source_id, "status": "deleted"}


def _detect_media_type(filename: str, mime_type: str | None = None) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if mime_type and mime_type != "application/octet-stream":
        return mime_type
    if ext == ".pdf":
        return "application/pdf"
    elif ext in [".txt", ".md"]:
        return "text/plain; charset=utf-8"
    elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
        return f"image/{'jpeg' if ext in ['.jpg', '.jpeg'] else ('webp' if ext == '.webp' else 'png')}"
    elif ext == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif ext == ".pptx":
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return "application/octet-stream"


def _parse_range_header(range_header: str | None, total_size: int) -> tuple[int, int] | None:
    if not range_header or not range_header.startswith("bytes="):
        return None
    range_val = range_header.replace("bytes=", "").strip()
    parts = range_val.split("-")
    if len(parts) != 2:
        return None
    start_str, end_str = parts[0].strip(), parts[1].strip()
    try:
        if start_str and end_str:
            start = int(start_str)
            end = int(end_str)
        elif start_str:
            start = int(start_str)
            end = total_size - 1
        elif end_str:
            length = int(end_str)
            start = max(0, total_size - length)
            end = total_size - 1
        else:
            return None
    except ValueError:
        return None

    if start > end or start >= total_size:
        return None
    end = min(end, total_size - 1)
    return start, end


def _serve_file_with_range(
    request: Request,
    file_path: str,
    media_type: str,
    filename: str,
    as_attachment: bool = False,
) -> Response:
    from fastapi.responses import StreamingResponse
    from urllib.parse import quote
    from app.core.storage import get_storage_provider

    storage = get_storage_provider()
    local_path = storage.get_local_path(file_path) if hasattr(storage, "get_local_path") else None
    effective_path = local_path or file_path
    if not os.path.exists(effective_path) and not storage.exists(file_path):
        raise HTTPException(status_code=404, detail="Source file not found")

    file_size = os.path.getsize(effective_path) if os.path.exists(effective_path) else storage.get_size(file_path)
    range_header = request.headers.get("range") or request.headers.get("Range")
    encoded_filename = quote(filename)
    disposition = "attachment" if as_attachment else "inline"
    content_disposition = f"{disposition}; filename*=UTF-8''{encoded_filename}"

    if range_header:
        parsed_range = _parse_range_header(range_header, file_size)
        if parsed_range:
            start, end = parsed_range
            content_length = end - start + 1
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": media_type,
                "Content-Disposition": content_disposition,
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            }
            return StreamingResponse(
                storage.open_stream(effective_path, start=start, length=content_length),
                status_code=206,
                headers=headers,
                media_type=media_type,
            )
        else:
            raise HTTPException(
                status_code=416,
                detail="Requested Range Not Satisfiable",
                headers={"Content-Range": f"bytes */{file_size}"},
            )

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": media_type,
        "Content-Disposition": content_disposition,
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(
        storage.open_stream(effective_path, start=0, length=file_size),
        status_code=200,
        headers=headers,
        media_type=media_type,
    )


@router.post("/sources/{source_id}/preview-token", response_model=PreviewTokenResponse)
def create_source_preview_token(
    source_id: str,
    db: Db,
    user: CurrentUser,
) -> PreviewTokenResponse:
    s_uuid = _parse_uuid(source_id)
    if not s_uuid:
        raise HTTPException(status_code=400, detail="Invalid source ID")
    source = _get_source_for_user(db, s_uuid, user)
    from app.core.security import create_preview_token
    token = create_preview_token(user=user, source_id=source.id, expires_in_seconds=300)
    return PreviewTokenResponse(
        preview_token=token,
        expires_in=300,
        preview_url=f"/api/v1/knowledge-center/sources/{source.id}/preview-file?token={token}",
        page_preview_url_template=f"/api/v1/knowledge-center/sources/{source.id}/preview-page/{{page_number}}?token={token}",
    )


@router.get("/sources/{source_id}/preview-file")
def preview_knowledge_source_file(
    source_id: str,
    request: Request,
    db: Db,
    auth: PreviewAuth,
) -> Response:
    s_uuid = _parse_uuid(source_id)
    if not s_uuid:
        raise HTTPException(status_code=400, detail="Invalid source ID")
    source = _get_source_for_user(db, s_uuid, auth.user)

    media_type = _detect_media_type(source.filename, source.mime_type)
    return _serve_file_with_range(
        request=request,
        file_path=source.storage_path,
        media_type=media_type,
        filename=source.filename,
        as_attachment=False,
    )


@router.get("/sources/{source_id}/download")
def download_knowledge_source_file(
    source_id: str,
    request: Request,
    db: Db,
    user: CurrentUser,
) -> Response:
    s_uuid = _parse_uuid(source_id)
    if not s_uuid:
        raise HTTPException(status_code=400, detail="Invalid source ID")
    source = _get_source_for_user(db, s_uuid, user)

    media_type = _detect_media_type(source.filename, source.mime_type)
    return _serve_file_with_range(
        request=request,
        file_path=source.storage_path,
        media_type=media_type,
        filename=source.filename,
        as_attachment=True,
    )


@router.get("/sources/{source_id}/preview-page/{page_number}")
def preview_source_page_image(
    source_id: str,
    page_number: int,
    request: Request,
    db: Db,
    background_tasks: BackgroundTasks,
    auth: PreviewAuth,
    scale: float = 1.3,
) -> Response:
    s_uuid = _parse_uuid(source_id)
    if not s_uuid:
        raise HTTPException(status_code=400, detail="Invalid source ID")
    source = _get_source_for_user(db, s_uuid, auth.user)

    return stream_source_page_image(
        source_id=source_id,
        page_number=page_number,
        db=db,
        background_tasks=background_tasks,
        user=auth.user,
        scale=scale,
    )


@router.get("/sources/{source_id}/view")
def view_knowledge_source_file(
    source_id: str,
    request: Request,
    db: Db,
    user: CurrentUser,
) -> Response:
    s_uuid = _parse_uuid(source_id)
    if not s_uuid:
        raise HTTPException(status_code=400, detail="Invalid source ID")
    source = _get_source_for_user(db, s_uuid, user)
    media_type = _detect_media_type(source.filename, source.mime_type)
    return _serve_file_with_range(
        request=request,
        file_path=source.storage_path,
        media_type=media_type,
        filename=source.filename,
        as_attachment=False,
    )


def _pre_cache_adjacent_pages(storage_path: str, cache_dir: str, start_page: int, end_page: int, scale: float = 1.3) -> None:
    try:
        import pypdfium2 as pdfium
        scale_key = int(round(scale * 100))
        with _PDF_RENDER_LOCK:
            pdf = pdfium.PdfDocument(storage_path)
            total = len(pdf)
            for p in range(start_page, min(end_page + 1, total + 1)):
                target = os.path.join(cache_dir, f"page_{p}_{scale_key}.jpg")
                if not os.path.exists(target):
                    page = pdf[p - 1]
                    pil_img = page.render(scale=scale).to_pil()
                    pil_img.save(target, format="JPEG", quality=85, optimize=True)
            pdf.close()
    except Exception:
        pass


def _stream_private_object(storage: Any, storage_key: str, media_type: str) -> Response:
    """Serve a cached object without disclosing a storage-provider URL."""
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        storage.open_stream(storage_key),
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _prune_remote_pdf_cache(cache_dir: str, max_files: int = 50, max_bytes: int = 500 * 1024 * 1024, ttl_sec: int = 900) -> None:
    """Evict expired (TTL) and LRU excess files to prevent unbounded disk usage."""
    import logging
    _log = logging.getLogger(__name__)
    try:
        now = time.time()
        file_entries: list[tuple[str, int, float]] = []
        for fname in os.listdir(cache_dir):
            fpath = os.path.join(cache_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                st = os.stat(fpath)
                if now - st.st_mtime > ttl_sec:
                    os.remove(fpath)
                else:
                    file_entries.append((fpath, st.st_size, getattr(st, "st_atime", st.st_mtime)))
            except OSError:
                pass

        total_bytes = sum(e[1] for e in file_entries)
        if len(file_entries) > max_files or total_bytes > max_bytes:
            file_entries.sort(key=lambda x: x[2])  # oldest access time first
            for fpath, size, _ in file_entries:
                if len(file_entries) <= int(max_files * 0.8) and total_bytes <= int(max_bytes * 0.8):
                    break
                try:
                    os.remove(fpath)
                    total_bytes -= size
                    file_entries.pop(0)
                except OSError:
                    pass
    except Exception as exc:
        _log.warning("Remote PDF cache pruning error: %s", exc)


def _stage_source_for_preview(storage: Any, source: KnowledgeSource) -> tuple[str, str | None]:
    """Return a local PDF path, caching remote downloads on disk with bounded TTL and LRU quota."""
    local_path = storage.get_local_path(source.storage_path)
    if local_path and os.path.exists(local_path):
        return local_path, None
    if not storage.exists(source.storage_path):
        raise HTTPException(status_code=404, detail="Source object not found in storage")

    cache_dir = os.path.join(_get_kc_temp_dir(), "remote_pdf_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cached_file = os.path.join(cache_dir, f"{source.id}_{source.checksum[:16]}.pdf")

    with _get_source_stage_lock(source.id):
        _prune_remote_pdf_cache(cache_dir)
        now = time.time()
        if os.path.exists(cached_file) and (now - os.path.getmtime(cached_file)) < 900:  # 15 min TTL
            return cached_file, None

        temp_download = f"{cached_file}.tmp_{uuid.uuid4().hex[:6]}"
        try:
            with open(temp_download, "wb") as f_out:
                for chunk in storage.open_stream(source.storage_path):
                    f_out.write(chunk)
            if os.path.exists(cached_file):
                try:
                    os.remove(cached_file)
                except OSError:
                    pass
            os.rename(temp_download, cached_file)
        finally:
            if os.path.exists(temp_download):
                try:
                    os.remove(temp_download)
                except OSError:
                    pass
    return cached_file, None


@router.get("/sources/{source_id}/page/{page_number}")
def stream_source_page_image(
    source_id: str,
    page_number: int,
    db: Db,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    scale: float = 1.3,
) -> Response:
    from app.core.storage import get_storage_provider

    if scale < 0.5 or scale > 2.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scale must be between 0.5 and 2.0",
        )

    # Quantize scale to 0.25 increments to avoid unbounded cache key proliferation
    quantized_scale = round(scale * 4) / 4

    s_uuid = _parse_uuid(source_id)
    source = _get_source_for_user(db, s_uuid, user)
    storage = get_storage_provider()
    if not storage.exists(source.storage_path):
        raise HTTPException(status_code=404, detail="Source object not found in storage")

    ext = os.path.splitext(source.filename)[1].lower()

    # Direct image sources
    if ext in [".png", ".jpg", ".jpeg", ".webp"]:
        media_type = f"image/{'jpeg' if ext in ['.jpg', '.jpeg'] else ('webp' if ext == '.webp' else 'png')}"
        return _stream_private_object(storage, source.storage_path, media_type)

    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="Page streaming is supported for PDF and image sources")

    if page_number < 1:
        raise HTTPException(status_code=400, detail="Page number must be >= 1")

    # Fast inspection: check known total pages before downloading remote PDF
    doc = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id))
    known_total = doc.total_pages if doc else source.preview_total_pages
    if known_total is not None and page_number > known_total:
        raise HTTPException(status_code=404, detail=f"Page {page_number} exceeds document total ({known_total})")

    scale_key = int(round(quantized_scale * 100))
    cached_page_key = f"knowledge_center/preview_pages/{s_uuid}/{source.checksum[:16]}_v{source.version}/page_{page_number}_{scale_key}.jpg"
    if storage.exists(cached_page_key):
        return _stream_private_object(storage, cached_page_key, "image/jpeg")

    staged_path: str | None = None
    try:
        import pypdfium2 as pdfium
        effective_source_path, staged_path = _stage_source_for_preview(storage, source)
        with _get_source_render_lock(s_uuid):
            if storage.exists(cached_page_key):
                return _stream_private_object(storage, cached_page_key, "image/jpeg")

            pdf = pdfium.PdfDocument(effective_source_path)
            total = len(pdf)
            if page_number > total:
                pdf.close()
                raise HTTPException(status_code=404, detail=f"Page {page_number} exceeds document total ({total})")

            page = pdf[page_number - 1]
            # Pre-render dimension calculation to prevent memory exhaustion BEFORE allocation
            width_pt, height_pt = page.get_size()
            eff_scale = quantized_scale
            max_dim = max(width_pt * eff_scale, height_pt * eff_scale)
            if max_dim > 3000:
                eff_scale = eff_scale * (3000.0 / max_dim)
            if (width_pt * eff_scale) * (height_pt * eff_scale) > 9_000_000:
                eff_scale = eff_scale * ((9_000_000 / ((width_pt * eff_scale) * (height_pt * eff_scale))) ** 0.5)

            with _GLOBAL_RENDER_SEMAPHORE:
                pil_img = page.render(scale=eff_scale).to_pil()
            pdf.close()

            # Bound max pixel dimensions as secondary safeguard
            if pil_img.width > 3000 or pil_img.height > 3000:
                pil_img.thumbnail((3000, 3000))

            import io
            rendered = io.BytesIO()
            pil_img.save(rendered, format="JPEG", quality=85, optimize=True)
            storage.save_bytes(rendered.getvalue(), cached_page_key, content_type="image/jpeg")

        return _stream_private_object(storage, cached_page_key, "image/jpeg")
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Failed to render document page %s for source %s: %s", page_number, source_id, exc)
        raise HTTPException(status_code=500, detail="Failed to render document page")
    finally:
        if staged_path and os.path.exists(staged_path):
            try:
                os.remove(staged_path)
            except OSError:
                pass


@router.get("/assets/{asset_id}/view")
def view_knowledge_asset_file(asset_id: str, db: Db, user: CurrentUser) -> Response:
    from fastapi.responses import StreamingResponse
    a_uuid = _parse_uuid(asset_id)
    asset = db.scalar(select(KnowledgeAsset).where(KnowledgeAsset.id == a_uuid))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset image not found")

    _get_source_for_user(db, asset.source_id, user)
    storage = get_storage_provider()
    if not storage.exists(asset.storage_path):
        raise HTTPException(status_code=404, detail="Asset image not found in storage")

    ext = os.path.splitext(asset.storage_path)[1].lower()
    media_type = "image/png"
    if ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif ext == ".webp":
        media_type = "image/webp"

    return StreamingResponse(
        storage.open_stream(asset.storage_path),
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/search")
def search_knowledge(
    query: str,
    db: Db,
    user: CurrentUser,
    course_id: str | None = None,
    grade_level: str | None = None,
    source_id: str | None = None,
    outline_node_id: str | None = None,
    include_prerequisite_lessons: bool = False,
) -> dict[str, Any]:
    c_uuid = _parse_uuid(course_id) if course_id else None
    enforce_ai_access(db, user, None, {"feature": "knowledge_search"})
    if c_uuid:
        if not can_access_course_knowledge(db, user, c_uuid):
            raise HTTPException(status_code=403, detail="Course access denied")
    eff_grade = grade_level or (user.grade_level if user.role == UserRole.STUDENT else None)
    if user.role == UserRole.STUDENT and not user.grade_level and not c_uuid:
        raise HTTPException(status_code=403, detail="Grade level access denied")

    return search_knowledge_base(
        db,
        course_id=c_uuid,
        query=query,
        include_assessment_answers=user.role != UserRole.STUDENT,
        source_id=_parse_uuid(source_id),
        outline_node_id=_parse_uuid(outline_node_id),
        include_prerequisite_lessons=include_prerequisite_lessons,
        institution_id=user.institution_id if user.role != UserRole.PLATFORM_ADMIN else None,
        grade_level=eff_grade,
        user=user,
    )


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, db: Db, user: TeacherOrAdmin) -> dict[str, Any]:
    a_uuid = _parse_uuid(assessment_id)
    assessment = db.get(AssessmentSource, a_uuid)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    source = db.get(KnowledgeSource, assessment.source_id)
    if not source or (user.role != UserRole.PLATFORM_ADMIN and source.institution_id != user.institution_id):
        raise HTTPException(status_code=404, detail="Assessment not found")
    questions = db.scalars(
        select(AssessmentQuestion)
        .where(AssessmentQuestion.assessment_source_id == assessment.id)
        .order_by(AssessmentQuestion.created_at.asc())
    ).all()
    return {
        "id": str(assessment.id),
        "source_id": str(assessment.source_id),
        "assessment_type": assessment.assessment_type,
        "title": assessment.title,
        "total_questions": assessment.total_questions,
        "processing_status": assessment.processing_status,
        "review_status": assessment.review_status,
        "questions": [
            {
                "id": str(q.id),
                "question_text": q.question_text,
                "question_type": q.question_type,
                "options_json": q.options_json,
                "correct_answer": q.correct_answer,
                "answer_source": q.answer_source,
                "answer_status": q.answer_status,
                "answer_provenance": q.answer_provenance_json,
                "source_pages": q.source_pages_json,
                "media_ids": q.media_ids_json or [],
                "hierarchy": (q.metadata_json or {}).get("hierarchy", {}),
                "question_order": (q.metadata_json or {}).get("question_order", 0),
                "points": q.points,
                "review_status": q.review_status,
                "validation_errors": validate_assessment_question(q),
            }
            for q in questions
        ],
    }


@router.patch("/assessment-questions/{question_id}")
def update_assessment_question(
    question_id: str,
    payload: AssessmentQuestionUpdate,
    db: Db,
    user: TeacherOrAdmin,
) -> dict[str, Any]:
    q_uuid = _parse_uuid(question_id)
    question = db.get(AssessmentQuestion, q_uuid)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    assessment = db.get(AssessmentSource, question.assessment_source_id)
    source = db.get(KnowledgeSource, assessment.source_id) if assessment else None
    if not source or (user.role != UserRole.PLATFORM_ADMIN and source.institution_id != user.institution_id):
        raise HTTPException(status_code=404, detail="Question not found")
    for field in ["question_text", "question_type", "options_json", "correct_answer", "explanation", "points", "review_status"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(question, field, value)
    if payload.correct_answer is not None:
        question.answer_source = "teacher_edit"
        question.answer_status = "resolved"
        question.answer_provenance_json = {"source": "teacher_edit", "teacher_id": str(user.id)}
    question.review_status = payload.review_status or ("approved" if not validate_assessment_question(question) else "needs_review")
    db.commit()
    db.refresh(question)
    return {"id": str(question.id), "review_status": question.review_status, "validation_errors": validate_assessment_question(question)}


@router.post("/assessments/{assessment_id}/answer-key")
def link_answer_key(
    assessment_id: str,
    payload: AnswerKeyLinkRequest,
    db: Db,
    user: TeacherOrAdmin,
) -> dict[str, Any]:
    assessment = db.get(AssessmentSource, _parse_uuid(assessment_id))
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    source = db.get(KnowledgeSource, assessment.source_id)
    if not source or (user.role != UserRole.PLATFORM_ADMIN and source.institution_id != user.institution_id):
        raise HTTPException(status_code=404, detail="Assessment not found")
    answer_key_id = _parse_uuid(payload.answer_key_source_id)
    new_assessment = relink_answer_key(db, assessment, answer_key_id)
    db.commit()
    return {"id": str(new_assessment.id), "answer_key_source_id": str(new_assessment.answer_key_source_id) if new_assessment.answer_key_source_id else None}


@router.post("/assessments/{assessment_id}/approve")
def approve_assessment(assessment_id: str, db: Db, user: TeacherOrAdmin) -> dict[str, Any]:
    assessment = db.get(AssessmentSource, _parse_uuid(assessment_id))
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    source = db.get(KnowledgeSource, assessment.source_id)
    if not source or (user.role != UserRole.PLATFORM_ADMIN and source.institution_id != user.institution_id):
        raise HTTPException(status_code=404, detail="Assessment not found")
    questions = db.scalars(select(AssessmentQuestion).where(AssessmentQuestion.assessment_source_id == assessment.id)).all()
    invalid = {str(q.id): validate_assessment_question(q) for q in questions if validate_assessment_question(q)}
    if invalid:
        raise HTTPException(status_code=422, detail={"invalid_questions": invalid})
    created = 0
    for q in questions:
        db.add(
            Question(
                institution_id=source.institution_id,
                author_id=user.id,
                course_id=q.course_id,
                question_type=q.question_type,
                prompt=q.question_text,
                options=q.options_json,
                correct_answer=q.correct_answer,
                media_ids_json=q.media_ids_json or [],
                points=q.points,
                learning_objective=q.learning_objective,
            )
        )
        q.review_status = "approved"
        created += 1
    assessment.review_status = "approved"
    db.commit()
    return {"assessment_id": str(assessment.id), "created_questions": created, "review_status": assessment.review_status}
