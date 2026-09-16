from __future__ import annotations

import uuid
from datetime import datetime, timezone
UTC = timezone.utc
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import os
import shutil
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_roles
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.course import Course, CourseModule, Enrollment, EnrollmentStatus, Lesson, IndexingStatus
from app.models.transcript import KnowledgeChunk, Transcript, TranscriptSegment, TranscriptionStatus
from app.services.knowledge_pipeline import generate_grounded_answer, generate_grounded_summary
from app.services.ai_access_policy import can_access_course_knowledge, enforce_ai_access
from app.services.transcript_indexer import execute_lesson_indexing, sync_lesson_rag
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
)
from app.models.progress import LessonProgress
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
from app.services.payment_service import can_access_lesson_content, student_can_use_ai_for_lesson

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
    enforce_rate_limit(request, bucket="video_upload", limit=5, window_seconds=60)
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

    upload_dir = _lesson_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{lesson_id}{ext}"
    filepath = os.path.join(upload_dir, filename)

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

    video_url = f"/api/v1/lessons/{lesson_id}/video"
    lesson.video_asset_key = video_url
    lesson.indexing_status = IndexingStatus.NOT_INDEXED
    lesson.indexing_error = None
    db.commit()
    db.refresh(lesson)

    return {
        "id": str(lesson.id),
        "video_url": video_url,
        "filename": filename,
        "message": "Video uploaded successfully as a protected playback asset.",
    }


@router.get("/lessons/{lesson_id}/video")
def stream_lesson_video(lesson_id: uuid.UUID, user: CurrentUser, db: Db) -> FileResponse:
    lesson, _ = _require_lesson_access(db, user, lesson_id)
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
def create_lesson_video_token(lesson_id: uuid.UUID, user: CurrentUser, db: Db) -> dict:
    from app.core.security import create_video_token
    lesson, _ = _require_lesson_access(db, user, lesson_id)
    token = create_video_token(user=user, lesson_id=lesson.id, expires_in_seconds=300)
    return {
        "video_token": token,
        "stream_url": f"/api/v1/lessons/{lesson.id}/stream?token={token}",
        "expires_in": 300,
    }


@router.get("/lessons/{lesson_id}/stream")
def stream_lesson_authenticated_range(
    lesson_id: uuid.UUID,
    request: Request,
    db: Db,
    token: str | None = None,
) -> FileResponse:
    from app.core.security import decode_video_token
    if token:
        payload = decode_video_token(token)
        if not payload or payload.get("lesson_id") != str(lesson_id):
            raise HTTPException(status_code=403, detail="Invalid or expired video stream token")
    else:
        raise HTTPException(status_code=401, detail="Authentication required for video stream")

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
            "status": "not_indexed" if lesson.indexing_status == IndexingStatus.NOT_INDEXED else "processing",
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


@router.post("/lessons/{lesson_id}/ai/ask")
def ask_ai_about_lesson(
    lesson_id: uuid.UUID,
    payload: dict,
    user: CurrentUser,
    request: Request,
    db: Db,
) -> dict:
    lesson, course = _require_lesson_access(db, user, lesson_id)
    course_id = course.id
    enforce_ai_access(db, user, request, {"feature": "lesson_ask", "lesson_id": str(lesson_id)})
    if user.role == UserRole.STUDENT and not student_can_use_ai_for_lesson(db, user, lesson_id):
        raise HTTPException(status_code=402, detail="An AI subscription or paid lesson entitlement is required")
    if not can_access_course_knowledge(db, user, course_id):
        raise HTTPException(status_code=403, detail="Course access denied")

    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty")

    return generate_grounded_answer(
        db=db,
        course_id=course_id,
        lesson_id=lesson_id,
        student_id=user.id,
        question=question,
    )


@router.get("/lessons/{lesson_id}/ai/summary")
def get_lesson_ai_summary(
    lesson_id: uuid.UUID,
    user: CurrentUser,
    request: Request,
    db: Db,
) -> dict:
    lesson, course = _require_lesson_access(db, user, lesson_id)
    course_id = course.id
    enforce_ai_access(db, user, request, {"feature": "lesson_summary", "lesson_id": str(lesson_id)})
    if user.role == UserRole.STUDENT and not student_can_use_ai_for_lesson(db, user, lesson_id):
        raise HTTPException(status_code=402, detail="An AI subscription or paid lesson entitlement is required")
    if not can_access_course_knowledge(db, user, course_id):
        raise HTTPException(status_code=403, detail="Course access denied")
    return generate_grounded_summary(db=db, lesson_id=lesson_id)


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
    lesson.indexing_status = IndexingStatus.NOT_INDEXED
    db.commit()

    return {
        "id": lesson.id,
        "title": lesson.title,
        "kind": lesson.kind,
        "position": lesson.position,
        "indexing_status": "not_indexed",
        "price_egp": float(lesson.price_egp or 0),
    }


@router.post("/lessons/{lesson_id}/reindex", status_code=200)
def reindex_lesson(
    lesson_id: uuid.UUID,
    db: Db,
    user: Manager,
) -> JSONResponse:
    lesson, course = _lesson_course(db, lesson_id)
    try:
        platform_service.ensure_course_manager(user, course)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    lesson.indexing_status = IndexingStatus.NOT_INDEXED
    lesson.indexing_error = None
    db.commit()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "not_indexed", "lesson_id": str(lesson.id), "message": "Video indexing is permanently disabled."},
    )


@router.get("/lessons/{lesson_id}/indexing-status")
def get_lesson_indexing_status(
    lesson_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
) -> dict:
    lesson, _ = _require_lesson_access(db, user, lesson_id)

    status_val = lesson.indexing_status.value if hasattr(lesson.indexing_status, "value") else str(lesson.indexing_status)
    return {
        "status": status_val,
        "indexed_chunks_count": lesson.indexed_chunks_count or 0,
        "error": lesson.indexing_error,
        "rag_synced": bool(getattr(lesson, "rag_synced", False)),
    }


@router.post("/lessons/{lesson_id}/sync-rag")
async def sync_lesson_rag_endpoint(
    lesson_id: uuid.UUID,
    db: Db,
    user: Manager,
) -> dict:
    lesson, course = _lesson_course(db, lesson_id)
    try:
        platform_service.ensure_course_manager(user, course)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    result = await sync_lesson_rag(str(lesson.id), max_retries=3)
    return {
        "lesson_id": str(lesson.id),
        **result,
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
