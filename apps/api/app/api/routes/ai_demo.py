from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.course import Course, CourseModule, Lesson
from app.services.document_parsers import parse_assessment_bank, parse_knowledge_file
from app.services.exam_text_extractor import (
    classify_and_parse_question,
    extract_distant_answer_keys,
    parse_table_questions,
    sanitize_source_filename,
    strip_ui_leak_lines,
)
from app.models.platform import Assignment, Quiz
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
TeacherOrAdmin = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]

class QuestionOption(BaseModel):
    key: str = ""
    text: str = ""
    is_correct: bool = False


class GeneratedQuestion(BaseModel):
    id: int
    question_type: str
    difficulty: str
    topic: str
    question_text: str
    points: int
    correct_answer: str | None = None
    needs_review: bool = False
    answer_confidence: Literal["confirmed", "unknown"] = "confirmed"
    explanation: str
    options: list[QuestionOption] | list[dict] | None = None
    withCorrection: bool | None = None
    source_concept: str | None = None
    source_start_time: float | None = None
    source_end_time: float | None = None
    source_segment_ids: list[str] | None = None


class QuizDraftResponse(BaseModel):
    title: str
    description: str
    total_points: int
    questions: list[GeneratedQuestion]
    is_complete: bool = True
    requires_teacher_approval: bool = True
    cached: bool = False
    metadata: dict[str, Any] | None = None


class QuizDraftRequest(BaseModel):
    course_id: uuid.UUID
    lesson_ids: list[uuid.UUID] = Field(default_factory=list)
    outline_node_id: uuid.UUID | None = None
    include_prerequisite_lessons: bool = False
    lesson_contents: list[str] = Field(default_factory=list)
    question_count: int = Field(default=3, ge=1, le=100)
    allowed_types: list[str] = Field(default_factory=list)
    type_allocations: list[dict[str, Any]] = Field(default_factory=list)
    difficulty_distribution: dict[str, int] | None = None
    topics: list[str] = Field(default_factory=list)
    target_points_per_question: int | None = Field(default=None, ge=1, le=1000)
    quiz_mode: Literal["mix", "extract", "generate"] = "mix"
    exclude_stems: list[str] = Field(default_factory=list)
    title: str | None = Field(default=None, min_length=2, max_length=200)


class ManualQuizCreate(BaseModel):
    course_id: str
    title: str = Field(min_length=2, max_length=200)
    duration_minutes: int | None = Field(default=30, ge=5, le=480)
    question_text: str = Field(min_length=5, max_length=2000)
    correct_answer: str | None = None
    max_score: float = Field(default=10.0, gt=0, le=1000)


class ManualQuizResponse(BaseModel):
    id: str
    title: str
    course_id: str
    status: str = "draft"
    max_score: float
    message: str


class ManualAssignmentCreate(BaseModel):
    course_id: str
    title: str = Field(min_length=2, max_length=200)
    prompt: str = Field(min_length=5, max_length=20_000)
    max_score: float = Field(default=100.0, gt=0, le=1000)


class ManualAssignmentResponse(BaseModel):
    id: str
    title: str
    course_id: str
    status: str = "draft"
    max_score: float
    message: str


def _uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _get_manageable_course(db: Session, user: User, course_id: uuid.UUID | None) -> Course:
    course = db.get(Course, course_id) if course_id else None
    if not course or (
        user.role != UserRole.PLATFORM_ADMIN and course.institution_id != user.institution_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if user.role == UserRole.TEACHER and course.teacher_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


@router.post("/quiz/extract-from-file", response_model=QuizDraftResponse)
async def extract_quiz_from_file(
    request: Request,
    db: Db,
    user: TeacherOrAdmin,
    file: UploadFile = File(...),
    course_id: str | None = Form(None),
    lesson_id: str | None = Form(None),  # accepted for backward compatibility; extraction is file-content only
) -> QuizDraftResponse:
    """Extract questions directly from an uploaded exam / question file (PDF, Word, TXT, JSON, etc.)"""
    from app.services.extraction_staging import (
        get_extraction_temp_dir,
        resolve_course_uuid,
        resolve_lesson_uuid,
        stream_upload_to_file,
    )

    max_exam_bytes = 50 * 1024 * 1024
    filename = sanitize_source_filename(file.filename or "exam_file.txt")
    course_uuid = resolve_course_uuid(db, user, course_id) if course_id else None
    if lesson_id and not course_uuid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "COURSE_REQUIRED_FOR_LESSON",
                "message": "يلزم اختيار المقرر عند تحديد درس لاستخراج الأسئلة.",
            },
        )
    resolve_lesson_uuid(db, course_uuid, lesson_id) if lesson_id and course_uuid else None
    staging_file = os.path.join(
        get_extraction_temp_dir(), f"exam_stage_{uuid.uuid4().hex[:12]}_{filename}"
    )
    try:
        size_bytes, checksum = await stream_upload_to_file(
            uploaded=file,
            dest_path=staging_file,
            max_file_bytes=max_exam_bytes,
        )
        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="الملف المرفوع فارغ.")
        # This request-scoped identifier is returned to the UI only. It makes
        # stale responses detectable without treating a Celery task id as the
        # source of truth for a different upload.
        extraction_id = str(uuid.uuid4())

        generated_questions: list[GeneratedQuestion] = []
        q_id = 1
        extension = os.path.splitext(filename)[1].lower()
        extracted_candidates: list[dict[str, Any]] = []

        if extension in {".json", ".quiz"}:
            with open(staging_file, "rb") as staged:
                parsed_assessment = parse_assessment_bank(staged.read(), filename)
            extracted_candidates = [
                {
                    "question_text": item.question_text,
                    "question_type": item.question_type,
                    "options": item.options,
                    "correct_answer": item.correct_answer,
                    "explanation": item.explanation or "",
                    "topic": item.topic_concept or filename,
                }
                for item in parsed_assessment
            ]
        else:
            try:
                parsed_document = parse_knowledge_file(
                    filename=filename,
                    mime_type=file.content_type,
                    file_path=staging_file,
                )
                answer_keys = extract_distant_answer_keys(parsed_document)
                extracted_candidates.extend(parse_table_questions(parsed_document, answer_keys))
                for page in parsed_document.pages:
                    page.blocks = [
                        b for b in page.blocks if strip_ui_leak_lines([b.text])
                    ]
                    for block in page.blocks:
                        question_status, question = classify_and_parse_question(
                            block.text, answer_keys
                        )
                        if question_status in {"question", "uncertain"} and question:
                            extracted_candidates.append(question)
            except Exception as exc:
                if extension not in {".txt", ".text", ".csv", ".tsv"}:
                    logger.exception("Quiz extraction parser failed for %s", filename)
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "code": "QUIZ_EXTRACTION_FAILED",
                            "message": "تعذر قراءة ملف الأسئلة. تأكد من أن الملف صالح ومدعوم.",
                        },
                    ) from exc
                logger.warning("Standard parse failed for text/csv %s, falling back to line reader: %s", filename, exc)

        seen_questions: set[str] = set()
        for rec in extracted_candidates:
            question_text = str(rec.get("question_text") or "").strip()
            fingerprint = re.sub(r"\s+", "", question_text).lower()
            if not question_text or fingerprint in seen_questions:
                continue
            seen_questions.add(fingerprint)
            opts = [
                QuestionOption(
                    key=str(option.get("key", "")),
                    text=str(option.get("text", "")),
                    is_correct=bool(option.get("is_correct", False)),
                )
                for option in (rec.get("options") or [])
                if isinstance(option, dict)
            ]
            topic = str(rec.get("topic") or filename)
            points = int(rec.get("points") or 5)
            q_type = str(rec.get("question_type") or "MCQ")
            upper_type = q_type.upper()
            if upper_type in ("MCQ", "MULTIPLE_CHOICE"):
                norm_type = "MCQ"
            elif upper_type in ("TRUE_FALSE", "TRUEFALSE"):
                norm_type = "TRUE_FALSE"
            elif upper_type in ("ESSAY",):
                norm_type = "ESSAY"
            elif upper_type in ("FILL_BLANK", "FILL_IN_BLANK"):
                norm_type = "FILL_BLANK"
            else:
                norm_type = q_type

            confirmed_answer = str(rec.get("correct_answer") or "").strip() or None
            generated_questions.append(
                GeneratedQuestion(
                    id=q_id,
                    question_type=norm_type,
                    difficulty="medium",
                    topic=topic,
                    question_text=question_text,
                    options=opts if opts else None,
                    correct_answer=confirmed_answer,
                    needs_review=confirmed_answer is None,
                    answer_confidence="confirmed" if confirmed_answer else "unknown",
                    explanation=str(rec.get("explanation") or ""),
                    points=points,
                )
            )
            q_id += 1

        # Safe text-only fallback: STRICTLY for plain text documents (TXT, CSV), NEVER for binary PDFs
        is_plain_text_doc = extension in {".txt", ".text", ".csv", ".tsv"}
        if not generated_questions and is_plain_text_doc:
            try:
                lines: list[str] = []
                if os.path.exists(staging_file):
                    with open(staging_file, "r", encoding="utf-8", errors="replace") as staged_txt:
                        raw_text = staged_txt.read(1024 * 1024)
                    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

                cur_q_text = ""
                cur_opts: list[QuestionOption] = []
                cur_ans = ""
                cur_exp = ""

                def flush_q():
                    nonlocal cur_q_text, cur_opts, cur_ans, cur_exp, q_id
                    if cur_q_text:
                        q_type = "MCQ" if len(cur_opts) >= 2 else ("TRUE_FALSE" if "صح" in cur_ans or "خطأ" in cur_ans else "ESSAY")
                        generated_questions.append(
                            GeneratedQuestion(
                                id=q_id,
                                question_type=q_type,
                                difficulty="medium",
                                topic=filename,
                                question_text=cur_q_text,
                                options=cur_opts if cur_opts else None,
                                correct_answer=cur_ans or None,
                                needs_review=not bool(cur_ans),
                                answer_confidence="confirmed" if cur_ans else "unknown",
                                explanation=cur_exp or "",
                                points=5,
                            )
                        )
                        q_id += 1
                        cur_q_text = ""
                        cur_opts = []
                        cur_ans = ""
                        cur_exp = ""

                for line in lines:
                    if re.match(r"^(?:س\s*\d+|[0-9]+[\.\-\)]|\(?[0-9]+\)?|سؤال)\s*[:\.]?", line):
                        flush_q()
                        cur_q_text = re.sub(r"^(?:س\s*\d+|[0-9]+[\.\-\)]|\(?[0-9]+\)?|سؤال)\s*[:\.]?\s*", "", line)
                    elif re.match(r"^[أ-يA-Da-d][\.\-\)]\s*", line):
                        opt_key = line[0]
                        opt_text = line[2:].strip()
                        cur_opts.append(QuestionOption(key=opt_key, text=opt_text, is_correct=False))
                    elif "الإجابة الصحيحة" in line or "الاجابة الصحيحة" in line or "الإجابة النموذجية" in line:
                        cur_ans = re.sub(r"^[^:]+:\s*", "", line).strip()
                        if cur_opts and cur_ans in ["أ", "ب", "ج", "د", "A", "B", "C", "D"]:
                            for opt in cur_opts:
                                if opt.key == cur_ans:
                                    opt.is_correct = True
                    elif "التفسير" in line or "الشرح" in line:
                        cur_exp = re.sub(r"^[^:]+:\s*", "", line).strip()
                    elif not cur_opts and cur_q_text:
                        cur_q_text += " " + line
                flush_q()
            except Exception:
                pass

        if not generated_questions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "QUIZ_EXTRACTION_FAILED",
                    "message": "تعذر استخراج أسئلة واضحة من الملف. تأكد من احتواء الملف على أسئلة وبنك امتحانات.",
                },
            )

        total_points = sum(q.points for q in generated_questions)
        return QuizDraftResponse(
            title=f"اختبار مستخرج: {filename}",
            description=f"تم استخراج {len(generated_questions)} سؤالاً تلقائياً من ملف ({filename}).",
            total_points=total_points,
            questions=generated_questions,
            is_complete=True,
            requires_teacher_approval=True,
            cached=False,
            metadata={
                "extracted_from_file": filename,
                "extraction_scope": "temporary",
                "extraction_id": extraction_id,
                "source_checksum": checksum,
                "course_id": str(course_uuid) if course_uuid else None,
                "question_count": len(generated_questions),
                "generated_at": datetime.now().isoformat(),
            },
        )
    finally:
        if os.path.exists(staging_file):
            try:
                os.remove(staging_file)
            except OSError:
                pass


@router.post("/manual/quizzes", response_model=ManualQuizResponse)
async def create_manual_quiz(
    payload: ManualQuizCreate,
    user: TeacherOrAdmin,
    request: Request,
    db: Db,
) -> ManualQuizResponse:
    enforce_rate_limit(request, bucket="ai", limit=10, window_seconds=60)
    course_uuid = _uuid(payload.course_id)
    if not course_uuid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid course_id")
    _get_manageable_course(db, user, course_uuid)
    quiz = Quiz(
        institution_id=user.institution_id,
        course_id=course_uuid,
        title=payload.title,
        status="draft",
        duration_seconds=(payload.duration_minutes or 30) * 60,
        attempts_allowed=1,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return ManualQuizResponse(
        id=str(quiz.id),
        title=quiz.title,
        course_id=str(quiz.course_id),
        status=quiz.status,
        max_score=payload.max_score,
        message="تم إنشاء الكويز يدوياً بنجاح.",
    )

@router.post("/manual/assignments", response_model=ManualAssignmentResponse)
async def create_manual_assignment(
    payload: ManualAssignmentCreate,
    user: TeacherOrAdmin,
    request: Request,
    db: Db,
) -> ManualAssignmentResponse:
    enforce_rate_limit(request, bucket="ai", limit=10, window_seconds=60)
    course_uuid = _uuid(payload.course_id)
    if not course_uuid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid course_id")
    _get_manageable_course(db, user, course_uuid)
    assignment = Assignment(
        institution_id=user.institution_id,
        course_id=course_uuid,
        title=payload.title,
        prompt=payload.prompt,
        max_score=payload.max_score,
        status="draft",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return ManualAssignmentResponse(
        id=str(assignment.id),
        title=assignment.title,
        course_id=str(assignment.course_id),
        status=assignment.status,
        max_score=assignment.max_score,
        message="تم إنشاء الواجب يدوياً بنجاح.",
    )
