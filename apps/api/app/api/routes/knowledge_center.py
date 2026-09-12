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
import inspect
import os
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status

_PDF_RENDER_LOCK = threading.Lock()
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_current_user, require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.course import Course, Lesson
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
from app.services.knowledge_center_service import (
    clear_source_tracking,
    create_knowledge_source,
    delete_knowledge_source,
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
from app.services.exam_processing import relink_answer_key, validate_assessment_question

router = APIRouter(prefix="/knowledge-center", tags=["knowledge-center"], dependencies=[Depends(get_current_user)])
Db = Annotated[Session, Depends(get_db)]
TeacherOrAdmin = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]

_LOCAL_INGEST_EXECUTOR = ThreadPoolExecutor(
    max_workers=get_settings().max_concurrent_ingestions,
    thread_name_prefix="knowledge-ingestion",
)


def _run_bg_process_source(source_id: uuid.UUID) -> None:
    """Runs knowledge source indexing and OCR in a background worker task with dedicated DB session."""
    import logging
    logger = logging.getLogger(__name__)
    from app.core.database import SessionLocal

    mark_parser_active(source_id)
    try:
        with SessionLocal() as db_session:
            try:
                process_knowledge_source(db_session, source_id)
            except OperationCancelledError:
                logger.info("Background indexing cancelled cooperatively for source %s", source_id)
                try:
                    from app.models.knowledge_center import KnowledgeSource, SourceStatus
                    src = db_session.get(KnowledgeSource, source_id)
                    if src and not is_source_deleting(source_id):
                        src.status = SourceStatus.STOPPED
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


def _enqueue_source_processing(background_tasks: BackgroundTasks, source_id: uuid.UUID) -> None:
    """Use Celery/Redis when configured; keep local development functional without it."""
    if os.getenv("USE_CELERY_INGESTION", "").lower() in {"1", "true", "yes"}:
        try:
            from app.tasks.knowledge_ingestion import index_source
            index_source.delay(str(source_id))
            return
        except Exception:
            pass
    # Submission is a tiny post-response task.  CPU-heavy OCR/indexing runs in
    # a bounded executor so concurrent uploads cannot exhaust FastAPI's shared
    # thread pool and make normal API requests unresponsive.
    background_tasks.add_task(_LOCAL_INGEST_EXECUTOR.submit, _run_bg_process_source, source_id)


class KnowledgeSourceResponse(BaseModel):
    id: str
    course_id: str
    lesson_id: str | None = None
    filename: str
    file_format: str
    size_bytes: int
    source_role: str
    version: int
    checksum: str
    status: str
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


def _parse_uuid(id_str: str | None) -> uuid.UUID | None:
    if not id_str or not str(id_str).strip():
        return None
    try:
        return uuid.UUID(str(id_str))
    except Exception:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(id_str))


def _resolve_course_uuid(db: Session, user: User, course_id: str | None) -> uuid.UUID:
    course_uuid = _parse_uuid(course_id)
    if course_uuid:
        existing = db.scalar(select(Course).where(Course.id == course_uuid))
        if existing:
            return existing.id

    # Try by user's institution
    default_course = db.scalar(select(Course).where(Course.institution_id == user.institution_id))
    if default_course:
        return default_course.id

    # Try any course in system
    default_course = db.scalar(select(Course))
    if default_course:
        return default_course.id

    # Auto-create if no course exists at all
    from app.models.course import CourseStatus
    new_course = Course(
        institution_id=user.institution_id,
        teacher_id=user.id,
        code="CHEM-3SEC",
        title="الكيمياء - الصف الثالث الثانوي",
        description="منهج الكيمياء للثانوية العامة — مستر حسن شعبان",
        status=CourseStatus.PUBLISHED,
    )
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    return new_course.id



def _get_active_user(db: Session, user: User | None) -> User:
    if user:
        return user
    # Fallback demo teacher for testing without auth headers
    demo_teacher = db.query(User).filter(User.username == "demo_teacher_kc").first()
    if not demo_teacher:
        from app.models.institution import Institution
        inst = db.query(Institution).first()
        if not inst:
            inst = Institution(name="مؤسسة مركز المعرفة الذكية", slug="demo_inst_kc")
            db.add(inst)
            db.commit()
        demo_teacher = User(
            institution_id=inst.id,
            username="demo_teacher_kc",
            email="teacher_demo_kc@lms.edu",
            password_hash="hash",
            display_name="مستر حسن شعبان",
            role=UserRole.TEACHER,
        )
        db.add(demo_teacher)
        db.commit()
    return demo_teacher


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
    return source


def _source_response(source: KnowledgeSource, total_pages: int | None = None) -> KnowledgeSourceResponse:
    return KnowledgeSourceResponse(
        id=str(source.id),
        course_id=str(source.course_id),
        lesson_id=str(source.lesson_id) if source.lesson_id else None,
        filename=source.filename,
        file_format=source.file_format,
        size_bytes=source.size_bytes,
        source_role=source.source_role,
        version=source.version,
        checksum=source.checksum,
        status=source.status,
        progress_percent=source.progress_percent,
        unit_count=source.unit_count,
        image_count=source.image_count,
        table_count=source.table_count,
        question_count=source.question_count,
        total_pages=total_pages,
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
    course_id: str = Form(...),
    lesson_id: str | None = Form(None),
    source_role: str = Form(SourceRole.KNOWLEDGE),
    assessment_type: str | None = Form(None),
    answer_key_source_id: str | None = Form(None),
    file: UploadFile = File(...),
) -> KnowledgeSourceResponse:
    enforce_rate_limit(request, bucket="upload", limit=50, window_seconds=60)
    settings = get_settings()
    max_file_bytes = settings.max_file_size_mb * 1024 * 1024

    course_uuid = _resolve_course_uuid(db, user, course_id)
    lesson_uuid = _parse_uuid(lesson_id)

    tmp_dir = _get_kc_temp_dir()
    safe_name = sanitize_source_filename(file.filename or "uploaded_file")
    staging_file = os.path.join(tmp_dir, f"stage_{uuid.uuid4().hex[:12]}_{safe_name}")

    try:
        size_bytes, checksum = await _stream_upload_to_file(
            uploaded=file,
            dest_path=staging_file,
            max_file_bytes=max_file_bytes,
        )
        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="الملف المرفوع فارغ (0 بايت)")

        source = create_knowledge_source(
            db=db,
            user=user,
            course_id=course_uuid,
            lesson_id=lesson_uuid,
            filename=file.filename or safe_name,
            staged_file_path=staging_file,
            checksum=checksum,
            size_bytes=size_bytes,
            source_role=source_role,
            mime_type=file.content_type,
            metadata={
                "assessment_type": assessment_type,
                "answer_key_source_id": answer_key_source_id,
            },
        )
        source.status = SourceStatus.PROCESSING
        source.progress_percent = 10
        db.commit()
        db.refresh(source)
        _enqueue_source_processing(background_tasks, source.id)
        return _source_response(source)
    except Exception:
        if os.path.exists(staging_file):
            try:
                os.remove(staging_file)
            except OSError:
                pass
        db.rollback()
        raise


@router.post("/sources/upload-batch", response_model=list[KnowledgeSourceResponse])
async def upload_knowledge_sources_batch(
    request: Request,
    db: Db,
    user: TeacherOrAdmin,
    background_tasks: BackgroundTasks,
    course_id: str | None = Form(None),
    lesson_id: str | None = Form(None),
    source_role: str = Form(SourceRole.KNOWLEDGE),
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

    course_uuid = _resolve_course_uuid(db, user, course_id)
    lesson_uuid = _parse_uuid(lesson_id)

    # Correction 3: Atomic Staged Operation
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

        # Phase 2: Move files and create database records atomically
        created_sources: list[KnowledgeSource] = []
        newly_created_permanent_paths: list[str] = []

        try:
            for item in staged_items:
                source = create_knowledge_source(
                    db=db,
                    user=user,
                    course_id=course_uuid,
                    lesson_id=lesson_uuid,
                    filename=item["filename"],
                    staged_file_path=item["staged_path"],
                    checksum=item["checksum"],
                    size_bytes=item["size_bytes"],
                    source_role=source_role,
                    mime_type=item["mime_type"],
                    metadata={
                        "batch_upload": True,
                        "assessment_type": assessment_type,
                        "answer_key_source_id": answer_key_source_id,
                    },
                    commit=False,
                    created_storage_paths=newly_created_permanent_paths,
                )

                source.status = SourceStatus.PROCESSING
                source.progress_percent = 10
                created_sources.append(source)

            db.commit()
        except Exception:
            # Delete only newly created permanent files, never delete pre-existing deduplicated files
            for p in newly_created_permanent_paths:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            db.rollback()
            raise

        for source in created_sources:
            db.refresh(source)
            _enqueue_source_processing(background_tasks, source.id)

        return [_source_response(source) for source in created_sources]

    finally:
        # Always clean up the staging directory on success or failure
        if os.path.exists(batch_stage_dir):
            shutil.rmtree(batch_stage_dir, ignore_errors=True)



@router.get("/sources", response_model=list[KnowledgeSourceResponse])
def list_knowledge_sources(
    request: Request,
    db: Db,
    user: CurrentUser = None,
    course_id: str | None = None,
    lesson_id: str | None = None,
) -> list[KnowledgeSourceResponse]:
    if user is None:
        user = _get_active_user(db, None)
    stmt = select(KnowledgeSource)
    if user.role != UserRole.PLATFORM_ADMIN:
        stmt = stmt.where(KnowledgeSource.institution_id == user.institution_id)
    if course_id and course_id.strip():
        course_uuid = _parse_uuid(course_id)
        if course_uuid:
            stmt = stmt.where(KnowledgeSource.course_id == course_uuid)
    if lesson_id and lesson_id.strip():
        lesson_uuid = _parse_uuid(lesson_id)
        if lesson_uuid:
            stmt = stmt.where(KnowledgeSource.lesson_id == lesson_uuid)

    sources = db.scalars(stmt.order_by(KnowledgeSource.created_at.desc())).all()
    source_ids = [s.id for s in sources]
    docs = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_id.in_(source_ids))).all() if source_ids else []
    pages_map = {d.source_id: d.total_pages for d in docs}

    return [
        KnowledgeSourceResponse(
            id=str(s.id),
            course_id=str(s.course_id),
            lesson_id=str(s.lesson_id) if s.lesson_id else None,
            filename=s.filename,
            file_format=s.file_format,
            size_bytes=s.size_bytes,
            source_role=s.source_role,
            version=s.version,
            checksum=s.checksum,
            status=s.status,
            progress_percent=s.progress_percent,
            unit_count=s.unit_count,
            image_count=s.image_count,
            table_count=s.table_count,
            question_count=s.question_count,
            total_pages=pages_map.get(s.id, 1 if s.file_format != "pdf" else None),
            error_message=s.error_message,
            file_url=f"/api/v1/knowledge-center/sources/{s.id}/view",
            created_at=s.created_at.isoformat(),
        )
        for s in sources
    ]


@router.post("/sources/mark-interrupted")
async def mark_sources_interrupted(
    request: Request,
    db: Db,
) -> dict[str, Any]:
    """Marks sources in PROCESSING or QUEUED state as FAILED when site is closed or client disconnects."""
    try:
        body = await request.body()
        import json
        payload = json.loads(body.decode("utf-8")) if body else {}
        source_ids = payload.get("source_ids", [])
    except Exception:
        source_ids = []

    marked = 0
    for sid in source_ids:
        suuid = _parse_uuid(sid)
        if suuid:
            src = db.get(KnowledgeSource, suuid)
            if src and src.status in (SourceStatus.PROCESSING, SourceStatus.QUEUED):
                src.status = SourceStatus.FAILED
                src.error_message = "فشل الفهرسة: تم إغلاق الموقع أثناء المعالجة."
                marked += 1
    if marked > 0:
        db.commit()
    return {"status": "ok", "marked": marked}


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

    return {
        "id": str(source.id),
        "filename": source.filename,
        "status": source.status,
        "source_role": source.source_role,
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
    source = _get_source_for_user(db, s_uuid, user)

    source.version += 1
    source.status = SourceStatus.PROCESSING
    source.progress_percent = 10
    source.error_message = None

    # Purge old units, questions & documents before asynchronous re-parsing
    db.execute(delete(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == s_uuid))
    db.execute(delete(KnowledgeQuestionRecord).where(KnowledgeQuestionRecord.source_id == s_uuid))
    db.execute(delete(KnowledgeAsset).where(KnowledgeAsset.source_id == s_uuid))
    db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.source_id == s_uuid))
    db.execute(delete(AssessmentSource).where(AssessmentSource.source_id == s_uuid))
    db.commit()
    db.refresh(source)

    # Ingest & index source asynchronously in background
    _enqueue_source_processing(background_tasks, s_uuid)

    return KnowledgeSourceResponse(

        id=str(source.id),
        course_id=str(source.course_id),
        lesson_id=str(source.lesson_id) if source.lesson_id else None,
        filename=source.filename,
        file_format=source.file_format,
        size_bytes=source.size_bytes,
        source_role=source.source_role,
        version=source.version,
        checksum=source.checksum,
        status=source.status,
        progress_percent=source.progress_percent,
        unit_count=source.unit_count,
        image_count=source.image_count,
        table_count=source.table_count,
        question_count=source.question_count,
        error_message=source.error_message,
        created_at=source.created_at.isoformat(),
    )


@router.post("/sources/{source_id}/stop-indexing")
def stop_indexing_source(source_id: str, db: Db, user: TeacherOrAdmin = None) -> dict[str, Any]:
    """Stops source indexing gracefully without deleting the file from server storage."""
    if user is None:
        user = _get_active_user(db, None)
    s_uuid = _parse_uuid(source_id)
    if not s_uuid:
        raise HTTPException(status_code=400, detail="Invalid source ID")

    # Register in-memory cancellation immediately so any active parsing thread stops at the next page
    register_cancellation(s_uuid)

    source = db.get(KnowledgeSource, s_uuid)
    if not source:
        return {"status": "ok", "message": "المصدر غير موجود", "source_status": "NOT_FOUND"}

    if user and user.role != UserRole.PLATFORM_ADMIN and source.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Source not found")

    # Idempotent check
    if source.status in (SourceStatus.STOPPED, SourceStatus.CANCELLED, SourceStatus.FAILED):
        return {"status": "ok", "message": "تم إيقاف الفهرسة مسبقاً", "source_status": source.status}

    source.status = SourceStatus.STOPPED
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


@router.get("/sources/{source_id}/view")
def view_knowledge_source_file(source_id: str, db: Db, user: CurrentUser) -> FileResponse:
    from fastapi.responses import FileResponse
    s_uuid = _parse_uuid(source_id)
    source = _get_source_for_user(db, s_uuid, user)
    if not os.path.exists(source.storage_path):
        raise HTTPException(status_code=404, detail="Source file not found")

    ext = os.path.splitext(source.filename)[1].lower()
    media_type = source.mime_type
    if not media_type or media_type == "application/octet-stream":
        if ext == ".pdf":
            media_type = "application/pdf"
        elif ext in [".txt", ".md"]:
            media_type = "text/plain; charset=utf-8"
        elif ext in [".png", ".jpg", ".jpeg"]:
            media_type = f"image/{'jpeg' if ext in ['.jpg', '.jpeg'] else 'png'}"
        else:
            media_type = "application/pdf"

    return FileResponse(
        path=source.storage_path,
        media_type=media_type,
        content_disposition_type="inline",
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


@router.get("/sources/{source_id}/page/{page_number}")
def stream_source_page_image(
    source_id: str,
    page_number: int,
    db: Db,
    background_tasks: BackgroundTasks,
    user: CurrentUser = None,
    scale: float = 1.3,
) -> FileResponse:
    from fastapi.responses import FileResponse

    if user is None:
        user = _get_active_user(db, None)
    s_uuid = _parse_uuid(source_id)
    source = _get_source_for_user(db, s_uuid, user)
    if not os.path.exists(source.storage_path):
        raise HTTPException(status_code=404, detail="Source file not found")

    ext = os.path.splitext(source.filename)[1].lower()

    # Direct image sources
    if ext in [".png", ".jpg", ".jpeg", ".webp"]:
        media_type = f"image/{'jpeg' if ext in ['.jpg', '.jpeg'] else ('webp' if ext == '.webp' else 'png')}"
        return FileResponse(source.storage_path, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})

    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="Page streaming is supported for PDF and image sources")

    if page_number < 1:
        raise HTTPException(status_code=400, detail="Page number must be >= 1")

    cache_dir = os.path.join("storage", "knowledge_center", "page_cache", str(s_uuid))
    os.makedirs(cache_dir, exist_ok=True)
    scale_key = int(round(scale * 100))
    cached_page_file = os.path.join(cache_dir, f"page_{page_number}_{scale_key}.jpg")

    if os.path.exists(cached_page_file) and os.path.getsize(cached_page_file) > 0:
        if page_number == 1:
            background_tasks.add_task(_pre_cache_adjacent_pages, source.storage_path, cache_dir, 2, 5, scale)
        return FileResponse(
            path=cached_page_file,
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    try:
        import pypdfium2 as pdfium
        with _PDF_RENDER_LOCK:
            pdf = pdfium.PdfDocument(source.storage_path)
            total = len(pdf)
            if page_number > total:
                pdf.close()
                raise HTTPException(status_code=404, detail=f"Page {page_number} exceeds document total ({total})")

            page = pdf[page_number - 1]
            pil_img = page.render(scale=scale).to_pil()
            pdf.close()

            pil_img.save(cached_page_file, format="JPEG", quality=85, optimize=True)

        # Pre-cache next 3 pages in background
        background_tasks.add_task(_pre_cache_adjacent_pages, source.storage_path, cache_dir, page_number + 1, page_number + 3, scale)

        return FileResponse(
            path=cached_page_file,
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to render document page: {str(exc)}")


@router.get("/assets/{asset_id}/view")
def view_knowledge_asset_file(asset_id: str, db: Db, user: CurrentUser) -> FileResponse:
    from fastapi.responses import FileResponse
    a_uuid = _parse_uuid(asset_id)
    asset = db.scalar(select(KnowledgeAsset).where(KnowledgeAsset.id == a_uuid))
    if asset:
        _get_source_for_user(db, asset.source_id, user)
    if not asset or not os.path.exists(asset.storage_path):
        raise HTTPException(status_code=404, detail="Asset image not found")

    ext = os.path.splitext(asset.storage_path)[1].lower()
    media_type = "image/png"
    if ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif ext == ".webp":
        media_type = "image/webp"

    return FileResponse(
        path=asset.storage_path,
        media_type=media_type,
    )


@router.get("/search")
def search_knowledge(
    course_id: str,
    query: str,
    db: Db,
    user: CurrentUser,
    source_id: str | None = None,
    outline_node_id: str | None = None,
    include_prerequisite_lessons: bool = False,
) -> dict[str, Any]:
    c_uuid = uuid.UUID(course_id)
    enforce_ai_access(db, user, None, {"feature": "knowledge_search"})
    if not can_access_course_knowledge(db, user, c_uuid):
        raise HTTPException(status_code=403, detail="Course access denied")
    return search_knowledge_base(
        db,
        c_uuid,
        query,
        include_assessment_answers=user.role != UserRole.STUDENT,
        source_id=_parse_uuid(source_id),
        outline_node_id=_parse_uuid(outline_node_id),
        include_prerequisite_lessons=include_prerequisite_lessons,
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
