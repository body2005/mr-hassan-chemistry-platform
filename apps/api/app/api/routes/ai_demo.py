from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import re
import urllib.request
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_roles
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.course import Course, CourseModule, Enrollment, EnrollmentStatus, Lesson
from app.models.knowledge_center import (
    KnowledgeAsset,
    KnowledgeQuestionImageLink,
    KnowledgeQuestionRecord,
    KnowledgeSource,
    SourceRole,
    SourceStatus,
)
from app.models.platform import (
    AIRefusalLog,
    Assignment,
    AssignmentSubmission,
    Quiz,
    QuizAttempt,
)
from app.models.progress import LessonProgress
from app.models.user import User, UserRole
from app.services.ai_access_policy import can_access_course_knowledge, enforce_ai_access
from app.services.knowledge_center_service import (
    create_knowledge_source,
    process_knowledge_source,
    sanitize_source_filename,
)
from app.services.transcript_indexer import index_lesson_video
from app.services.payment_service import student_can_use_ai_for_lesson

logger = logging.getLogger(__name__)

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
TeacherOrAdmin = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001").rstrip("/")
AI_SERVICE_TIMEOUT = min(float(os.getenv("AI_SERVICE_TIMEOUT", "2.0")), 5.0)

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
    explanation: str
    options: list[QuestionOption] | list[dict] | None = None
    withCorrection: bool | None = None
    source_concept: str | None = None
    source_start_time: float | None = None
    source_end_time: float | None = None
    source_segment_ids: list[str] | None = None
    image_asset_ids: list[str] | None = None
    image_asset_url: str | None = None

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
    lesson_ids: list[uuid.UUID] = []
    outline_node_id: uuid.UUID | None = None
    include_prerequisite_lessons: bool = False
    lesson_contents: list[str] = []
    question_count: int = Field(default=3, ge=1, le=100)
    allowed_types: list[str] = []
    type_allocations: list[dict[str, Any]] = []
    difficulty_distribution: dict[str, int] | None = None
    topics: list[str] = []
    target_points_per_question: int | None = Field(default=None, ge=1, le=1000)
    quiz_mode: Literal["mix", "extract", "generate"] = "mix"
    exclude_stems: list[str] = []
    title: str | None = Field(default=None, min_length=2, max_length=200)

class EssayGradingResponse(BaseModel):
    total_score: float
    max_score: float
    percentage: float
    criteria_breakdown: list[dict[str, Any]]
    feedback_summary: str
    confidence_score: float = Field(ge=0, le=1)
    flagged_for_human_review: bool = True
    requires_teacher_approval: bool = True
    cached: bool = False

class TutorChatResponse(BaseModel):
    answer: str
    session_id: str
    is_grounded: bool = False
    refusal: bool = False
    citations: list[dict[str, Any]] = []

class BatchRiskResponse(BaseModel):
    predictions: list[dict[str, Any]]
    total_students: int
    at_risk_count: int
    model_metadata: dict[str, Any]

class IndexCourseResponse(BaseModel):
    course_id: str
    indexed_chunks_count: int
    message: str

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

async def try_rag_service(course_id: str, message: str, session_id: str) -> TutorChatResponse | None:
    """Attempt primary RAG microservice with semantic embeddings and bounded memory."""
    payload = _json.dumps({
        "course_id": course_id,
        "message": message,
        "session_id": session_id,
        "temperature": 0.5,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{AI_SERVICE_URL}/tutor/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=AI_SERVICE_TIMEOUT) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            return TutorChatResponse(**data)
    except Exception:
        return None


def _parse_llm_json(raw_text: str) -> dict[str, Any] | None:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.IGNORECASE)
    try:
        value = _json.loads(cleaned)
    except _json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            return None
        try:
            value = _json.loads(match.group(0))
        except _json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _request_grading_from_provider(prompt: str) -> dict[str, Any] | None:
    """Call only an explicitly configured provider; never fabricate a grade."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key and not groq_key.startswith("your_"):
        payload = {
            "model": os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strict chemistry assessment grader. Return one JSON object only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            request = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=_json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=25) as response:
                body = _json.loads(response.read().decode("utf-8"))
                return _parse_llm_json(str(body["choices"][0]["message"]["content"]))
        except Exception:
            logger.exception("Groq essay grading request failed")

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key and not gemini_key.startswith(("your_", "AQ.")):
        model = os.getenv("QA_MODEL", "gemini-2.5-flash")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        try:
            request = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}",
                data=_json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=25) as response:
                body = _json.loads(response.read().decode("utf-8"))
                raw = body["candidates"][0]["content"]["parts"][0]["text"]
                return _parse_llm_json(str(raw))
        except Exception:
            logger.exception("Gemini essay grading request failed")
    return None

def _get_live_analytics(db: Session, user: User) -> dict[str, Any]:
    teacher_course_ids: list[uuid.UUID] | None = None
    if user.role == UserRole.TEACHER:
        teacher_course_ids = db.scalars(
            select(Course.id).where(
                Course.institution_id == user.institution_id,
                Course.teacher_id == user.id,
            )
        ).all()

    if teacher_course_ids is not None:
        enrolled_student_ids = db.scalars(
            select(Enrollment.student_id).where(
                Enrollment.course_id.in_(teacher_course_ids),
                Enrollment.status == EnrollmentStatus.ACTIVE,
            ).distinct()
        ).all()
        students_query = select(User).where(
            User.institution_id == user.institution_id,
            User.role == UserRole.STUDENT,
            User.id.in_(enrolled_student_ids) if enrolled_student_ids else False,
        )
    else:
        students_query = select(User).where(
            User.institution_id == user.institution_id,
            User.role == UserRole.STUDENT,
        )
    students = db.execute(students_query).scalars().all()
    total_students = len(students)

    lessons_query = (
        select(Lesson, CourseModule, Course)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .join(Course, CourseModule.course_id == Course.id)
        .where(Course.institution_id == user.institution_id)
        .order_by(Lesson.created_at.desc())
    )
    if teacher_course_ids is not None:
        lessons_query = lessons_query.where(Course.id.in_(teacher_course_ids))

    lesson_rows = db.execute(lessons_query).all()
    total_lessons = len(lesson_rows)

    quiz_attempts_query = select(QuizAttempt).where(
        QuizAttempt.institution_id == user.institution_id
    )
    if teacher_course_ids is not None:
        quiz_attempts_query = (
            quiz_attempts_query.join(Quiz, QuizAttempt.quiz_id == Quiz.id)
            .where(Quiz.course_id.in_(teacher_course_ids))
        )
    quiz_attempts = db.execute(quiz_attempts_query).scalars().all()
    submitted_attempts = [a for a in quiz_attempts if a.submitted_at and a.score is not None]
    avg_quiz_score = (
        round(sum(a.score for a in submitted_attempts) / len(submitted_attempts), 1)
        if submitted_attempts
        else None
    )

    sub_query = select(AssignmentSubmission).where(
        AssignmentSubmission.institution_id == user.institution_id
    )
    if teacher_course_ids is not None:
        sub_query = (
            sub_query.join(Assignment, AssignmentSubmission.assignment_id == Assignment.id)
            .where(Assignment.course_id.in_(teacher_course_ids))
        )
    submissions = db.execute(sub_query).scalars().all()
    scored_subs = [s for s in submissions if s.final_score is not None or s.ai_score is not None]
    avg_assignment_score = (
        round(
            sum((s.final_score if s.final_score is not None else s.ai_score or 0) for s in scored_subs)
            / len(scored_subs),
            1,
        )
        if scored_subs
        else None
    )

    progress_query = select(LessonProgress).where(
        LessonProgress.institution_id == user.institution_id
    )
    if teacher_course_ids is not None:
        teacher_lesson_ids = [row[0].id for row in lesson_rows]
        progress_query = progress_query.where(
            LessonProgress.lesson_id.in_(teacher_lesson_ids) if teacher_lesson_ids else False
        )
    progress_rows = db.execute(progress_query).scalars().all()
    avg_progress = (
        round(sum(p.completion_percent for p in progress_rows) / len(progress_rows), 1)
        if progress_rows
        else None
    )

    # A student is counted as "present/active" when the platform has a real
    # lesson-progress event for them. This is intentionally labelled as
    # attendance/engagement in the tutor response: the current schema tracks
    # learning activity, not classroom roll-call attendance.
    progress_active_ids = {p.student_id for p in progress_rows if p.last_event_at or p.watched_duration_seconds > 0 or p.completion_percent > 0}
    active_ids = progress_active_ids.union({a.student_id for a in quiz_attempts}).union({s.student_id for s in submissions})
    inactive_students = [s for s in students if s.id not in active_ids]
    attendance_percent = round((len(progress_active_ids) / total_students) * 100, 1) if total_students else None

    return {
        "total_students": total_students,
        "students": students,
        "total_lessons": total_lessons,
        "lesson_rows": lesson_rows,
        "quiz_attempts_count": len(submitted_attempts),
        "avg_quiz_score": avg_quiz_score,
        "assignment_submissions_count": len(submissions),
        "avg_assignment_score": avg_assignment_score,
        "avg_progress": avg_progress,
        "inactive_students": inactive_students,
        "active_student_count": len(progress_active_ids),
        "attendance_percent": attendance_percent,
    }

def _find_matching_citations(lesson_rows: list[Any], query: str) -> list[dict[str, Any]]:
    if not lesson_rows:
        return []

    q = query.strip().lower()
    casual_words = {
        "مرحب", "مرحبا", "اهلا", "أهلا", "hello", "hi", "ازيك", "شكرا",
        "صباح", "مساء", "تقرير", "تحليل", "احصائيات", "إحصائيات",
        "نسب", "استيعاب", "درجات", "المعدل", "النجاح", "نجاح",
    }
    tokens = [t for t in re.split(r"[\s\?\!\.\،]+", q) if len(t) >= 3 and t not in casual_words]
    if not tokens:
        return []

    scored: list[dict[str, Any]] = []
    for l_row in lesson_rows:
        lesson, module, course = l_row[0], l_row[1], l_row[2]
        title = lesson.title or ""
        content = (lesson.transcript_text or lesson.content or "").strip()

        if not content:
            continue

        combined = f"{title} {content}".lower()
        matches = sum(1 for t in tokens if t in combined)
        if matches == 0:
            continue

        snippet_source = content.lower()
        hit_positions = [snippet_source.find(t) for t in tokens if snippet_source.find(t) >= 0]
        hit_pos = min(hit_positions) if hit_positions else 0
        start = max(0, hit_pos - 80)
        excerpt = content[start : start + 220].replace("\n", " ").strip()
        if start > 0:
            excerpt = "… " + excerpt
        if start + 220 < len(content):
            excerpt += " …"

        citation: dict[str, Any] = {
            "chunk_id": str(lesson.id),
            "lesson_id": str(lesson.id),
            "lesson_title": f"{course.title} - {title}",
            "snippet": excerpt,
            "similarity_score": round(min(0.98, matches / len(tokens)), 2),
        }

        meta = getattr(lesson, "transcript_metadata", None) or {}
        if isinstance(meta, dict) and meta.get("time_range"):
            citation["lesson_title"] += f" [{meta['time_range']}]"

        scored.append(citation)

    return sorted(scored, key=lambda c: c["similarity_score"], reverse=True)[:3]

def _build_tutor_answer(
    db: Session,
    user: User,
    message: str,
    user_role: str = "",
    user_name: str = "",
) -> tuple[str, bool, list[dict[str, Any]]]:
    message_clean = message.strip()
    message_lower = message_clean.lower()
    analytics = _get_live_analytics(db, user)
    lesson_rows = analytics["lesson_rows"]
    # Never trust a role supplied by the browser.  The authenticated database
    # user is the sole authority for teacher-only analytics.
    is_teacher = user.role in {
        UserRole.TEACHER,
        UserRole.INSTITUTION_ADMIN,
        UserRole.PLATFORM_ADMIN,
    }
    display_name = user_name or user.display_name or (
        "مستر حسن شعبان" if is_teacher else user.username
    )

    # 1. Greetings
    if any(word in message_lower for word in ["مرحب", "اهلا", "أهلا", "سلام", "hello", "hi", "ازيك", "صباح", "مساء"]):
        if is_teacher:
            ans = (
                f"أهلاً بك يا مستر {display_name}.\n"
                "أنا المساعد الذكي لمقرراتك التعليمية.\n"
                "يمكنك سؤالي عن: التحليلات الحية للطلاب، كشف نسب الإنجاز، أو مراجعة وشرح أي مفهوم من فيديوهات ومذكرات الدروس المرفوعة وصياغة الكويزات."
            )
            return ("".join(ans), False, [])
        ans = (
            f"أهلاً بك يا {display_name} في المنصة التعليمية.\n"
            "اسألني عن أي جزئية أو مفهوم مشروح في دروسك وسأشرحها لك خطوة بخطوة بالاستناد المباشر لنص الشرح والفيديو."
        )
        return ("".join(ans), False, [])

    # 2. Live Analytics & Student Comprehension Report
    if any(
        word in message_lower
        for word in [
            "تقرير", "تحليل", "إحصائيات", "احصائيات", "نسب نجاح", "استيعاب", "درجات",
            "معدلات", "انجاز", "إنجاز", "report", "analytics",
        ]
    ):
        if is_teacher:
            lines = [
                "تقرير تحليلي واقعي ومستخرج مباشرة من قاعدة البيانات:",
                f"• عدد الطلاب المسجلين في المنصة: {analytics['total_students']} طالب",
                f"• إجمالي الدروس المنشورة في المنهج: {analytics['total_lessons']} درس",
            ]

            if analytics["quiz_attempts_count"] > 0:
                lines.append(f"• محاولات الكويزات المسلمة: {analytics['quiz_attempts_count']} محاولة")
                lines.append(f"• متوسط درجات الطلاب في الكويزات: {analytics['avg_quiz_score']}%")
            else:
                lines.append("• الكويزات: لا توجد تسليمات كويزات مسجلة بعد في قاعدة البيانات.")

            if analytics["assignment_submissions_count"] > 0:
                lines.append(f"• تسليمات الواجبات المرصودة: {analytics['assignment_submissions_count']} تسليم")
                if analytics["avg_assignment_score"] is not None:
                    lines.append(f"• متوسط درجات الواجبات: {analytics['avg_assignment_score']}%")
            else:
                lines.append("• الواجبات: لا توجد تسليمات واجبات مرصودة حتى الآن.")

            if analytics["avg_progress"] is not None:
                lines.append(f"• متوسط نسبة مشاهدة وإنجاز الفيديوهات للطلاب: {analytics['avg_progress']}%")
            else:
                lines.append("• مشاهدات الفيديو: لم تسجل بيانات مشاهدة مكتملة بعد.")

            if analytics["attendance_percent"] is not None:
                lines.append(
                    f"• نسبة الحضور/التفاعل المسجلة: {analytics['attendance_percent']}% "
                    f"({analytics['active_student_count']} من {analytics['total_students']} طالب لديهم نشاط مشاهدة مسجل)"
                )
            else:
                lines.append("• نسبة الحضور/التفاعل: لا توجد بيانات مشاهدة مسجلة بعد.")

            inactive = analytics["inactive_students"]
            if inactive:
                inactive_names = [s.display_name or s.username for s in inactive[:5]]
                lines.append(
                    f"• طلاب مسجلون لم يسجلوا أي تسليمات حتى الآن ({len(inactive)} طلاب): "
                    + "، ".join(inactive_names)
                )
            elif analytics["total_students"] > 0:
                lines.append("• جميع الطلاب المسجلين متفاعلون ولديهم نشاط مسجل في المنصة.")
            else:
                lines.append("• ملاحظة: لم يتم تسجيل طلاب في النظام بعد.")

            return ("\n".join(lines), True, [])

        ans = (
            f"تقرير تقدمك الدراسي يا {display_name}:\n"
            f"• الدروس المتاحة في المقرر: {analytics['total_lessons']} درس\n"
            "يمكنك متابعة مذاكرة الدروس وحل الواجبات والكويزات من حسابك لرفع معدل تحصيلك."
        )
        return ("".join(ans), True, [])

    # 3. Teacher-only recommendations.  Keep this branch before knowledge
    # retrieval so a teacher can ask for operational advice even when the
    # uploaded course documents do not contain the word "اقتراح".
    if is_teacher and any(
        word in message_lower
        for word in ["اقتراح", "نصيحة", "توصية", "تحسين", "خطة", "recommend", "suggest", "advice"]
    ):
        attendance = analytics["attendance_percent"]
        avg_progress = analytics["avg_progress"]
        recommendations = [
            "قسّم الدروس الطويلة إلى مقاطع قصيرة مع هدف واضح لكل مقطع.",
            "أنشئ اختباراً قصيراً بعد كل درس، ثم راجع الأسئلة التي يخطئ فيها معظم الطلاب.",
        ]
        if attendance is not None and attendance < 60:
            recommendations.insert(0, "ابدأ برسائل تذكير وجدول متابعة للطلاب غير النشطين لأن نسبة الحضور/التفاعل الحالية منخفضة.")
        if avg_progress is not None and avg_progress < 60:
            recommendations.insert(0, "أضف شرحاً تمهيدياً وأمثلة محلولة قبل الأجزاء التي ينخفض فيها إكمال الفيديو.")
        return (
            "اقتراحات مخصصة للمدرس، مبنية على البيانات الحالية فقط:\n" +
            "\n".join(f"• {item}" for item in recommendations),
            True,
            [],
        )

    # 4. Grounded Refusal when no authorized Knowledge Center sources match
    ans = "يجب أن يكون السؤال في إطار المادة."
    return (ans, False, [])

@router.post("/tutor/chat", response_model=TutorChatResponse)
async def tutor_chat(
    payload: dict[str, Any],
    user: CurrentUser,
    request: Request,
    db: Db,
) -> TutorChatResponse:
    enforce_rate_limit(request, bucket="ai", limit=60, window_seconds=60)
    enforce_ai_access(db, user, request, {"feature": "tutor_chat"})
    message = payload.get("message", "") if isinstance(payload, dict) else ""
    session_id = (
        payload.get("session_id") or f"sess_{uuid.uuid4().hex}"
        if isinstance(payload, dict)
        else f"sess_{uuid.uuid4().hex}"
    )
    course_id = payload.get("course_id", "") if isinstance(payload, dict) else ""
    lesson_id = payload.get("lesson_id", "") if isinstance(payload, dict) else ""
    if not message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    c_uuid = _uuid(str(course_id))
    if not c_uuid:
        raise HTTPException(status_code=422, detail="A valid course_id is required")
    lesson_uuid = _uuid(str(lesson_id)) if lesson_id else None
    if user.role == UserRole.STUDENT:
        if not lesson_uuid:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Choose an accessible lesson or activate an AI subscription",
            )
        lesson_row = db.scalar(
            select(Lesson)
            .join(CourseModule, Lesson.module_id == CourseModule.id)
            .where(Lesson.id == lesson_uuid, CourseModule.course_id == c_uuid)
        )
        if not lesson_row:
            raise HTTPException(status_code=404, detail="Lesson not found")
        if not student_can_use_ai_for_lesson(db, user, lesson_uuid):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="AI access is not active for this lesson",
            )
    elif not can_access_course_knowledge(db, user, c_uuid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Course access denied")

    teacher_ops_query = user.role in {
        UserRole.TEACHER,
        UserRole.INSTITUTION_ADMIN,
        UserRole.PLATFORM_ADMIN,
    } and any(
        word in message.lower()
        for word in [
            "تقرير", "تحليل", "إحصائيات", "احصائيات", "نسب", "درجات", "معدلات",
            "انجاز", "إنجاز", "حضور", "حضورهم", "اقتراح", "نصيحة", "توصية",
            "تحسين", "خطة", "report", "analytics", "recommend", "suggest", "advice",
        ]
    )

    # Operational teacher requests are answered from protected analytics below;
    # do not send them through the student/course RAG path first.
    if c_uuid and not teacher_ops_query:
        try:
            from app.services.knowledge_retriever import check_grounding_and_answer
            from app.services.conversation_memory import remember_turn, rewrite_followup_query
            retrieval_message = rewrite_followup_query(db, user.id, c_uuid, str(session_id), message)
            kc_ans, is_g, is_ref, kc_cits = check_grounding_and_answer(
                db, user, c_uuid, retrieval_message, lesson_id=lesson_uuid
            )
            remember_turn(
                db, user.id, c_uuid, str(session_id), message,
                "supported" if is_g else ("not_found" if is_ref else "partial"), kc_cits,
            )
            db.commit()
            if is_g or is_ref:
                if is_ref:
                    db.add(
                        AIRefusalLog(
                            user_id=user.id,
                            institution_id=user.institution_id,
                            course_id=c_uuid,
                            question_text=message.strip(),
                            reason="no_matching_coverage",
                        )
                    )
                    db.commit()
                return TutorChatResponse(
                    answer=kc_ans,
                    session_id=session_id,
                    is_grounded=is_g,
                    refusal=is_ref,
                    citations=kc_cits,
                )
        except HTTPException:
            raise
        except (ValueError, LookupError) as exc:
            logger.info("Knowledge Center lookup rejected", extra={"course_id": str(course_id), "user_id": str(user.id), "reason": str(exc)})
        except Exception as exc:
            logger.exception("Knowledge Center retrieval failed", extra={"course_id": str(course_id), "user_id": str(user.id)})
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "RAG_UNAVAILABLE", "message": "Knowledge retrieval is temporarily unavailable"},
            ) from exc

    answer, is_grounded, citations = _build_tutor_answer(
        db, user, message, user_role=user.role.value, user_name=user.display_name or user.username
    )

    # Record refusal in audit log if tutor refused the query
    if not is_grounded and not citations and "لم أجد له تغطية" in answer:
        refusal_entry = AIRefusalLog(
            user_id=user.id,
            institution_id=user.institution_id,
            course_id=c_uuid,
            question_text=message.strip(),
            reason="no_matching_coverage",
        )
        db.add(refusal_entry)
        db.commit()

    return TutorChatResponse(
        answer=answer,
        session_id=session_id,
        is_grounded=is_grounded,
        refusal=not is_grounded and not citations,
        citations=citations,
    )


@router.get("/ai/refusal-log")
def list_ai_refusal_logs(
    user: CurrentUser,
    db: Db,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Retrieve AI refusal logs. Admins see all logs; teachers see only logs for their courses."""
    if user.role in {UserRole.PLATFORM_ADMIN, UserRole.INSTITUTION_ADMIN}:
        query = select(AIRefusalLog).where(AIRefusalLog.institution_id == user.institution_id)
    elif user.role == UserRole.TEACHER:
        teacher_course_ids = db.scalars(
            select(Course.id).where(Course.teacher_id == user.id)
        ).all()
        query = select(AIRefusalLog).where(
            AIRefusalLog.institution_id == user.institution_id,
            (AIRefusalLog.course_id.in_(teacher_course_ids)) | (AIRefusalLog.user_id == user.id),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="صلاحية الوصول لسجل الرفض مقتصرة على المعلمين والمسؤولين فقط.",
        )

    logs = db.scalars(query.order_by(AIRefusalLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id),
            "course_id": str(log.course_id) if log.course_id else None,
            "question_text": log.question_text,
            "reason": log.reason,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.post("/quiz/draft", response_model=QuizDraftResponse)
async def generate_quiz_draft(
    payload: QuizDraftRequest,
    user: TeacherOrAdmin,
    request: Request,
    db: Db,
) -> QuizDraftResponse:
    enforce_rate_limit(request, bucket="ai", limit=10, window_seconds=60)
    enforce_ai_access(db, user, request, {"feature": "quiz_draft"})
    payload_data = payload.model_dump(mode="json")
    course_id = payload_data["course_id"]
    lesson_contents = payload_data["lesson_contents"]
    question_count = payload_data["question_count"]
    type_allocations = payload_data["type_allocations"]
    topics = payload_data["topics"]

    from app.services.educational_normalizer import (
        KnowledgeUnit,
        extract_knowledge_units,
        clean_spoken_noise,
    )
    from app.services.quiz_engine import generate_quiz
    from app.models.knowledge_center import KnowledgeQuestionRecord, KnowledgeUnitRecord

    quiz_mode = payload_data["quiz_mode"]
    exclude_stems = payload_data["exclude_stems"]

    def _stem_sim(s1: str, s2: str) -> float:
        t1 = set(re.findall(r"\w+", (s1 or "").lower()))
        t2 = set(re.findall(r"\w+", (s2 or "").lower()))
        if not t1 or not t2:
            return 0.0
        return len(t1 & t2) / max(len(t1), len(t2))

    def _is_excluded(stem: str, exclusions: list[str]) -> bool:
        for ex in exclusions:
            if _stem_sim(stem, ex) > 0.7:
                return True
        return False

    knowledge_units: list[KnowledgeUnit] = []
    extracted_questions: list[GeneratedQuestion] = []
    primary_lesson_id = "default_lesson"
    c_uuid = _uuid(course_id) if course_id else None
    if not c_uuid:
        raise HTTPException(status_code=422, detail="A valid course_id is required")
    _get_manageable_course(db, user, c_uuid)
    outline_uuid = _uuid(str(payload_data.get("outline_node_id", "")))
    include_prerequisites = payload_data["include_prerequisite_lessons"]
    selected_lesson_uuids = [
        item for item in (_uuid(str(value)) for value in payload_data["lesson_ids"])
        if item is not None
    ]

    # 1. Fetch pre-existing verbatim exam questions if in 'extract' or 'mix' mode
    if c_uuid and quiz_mode in ("extract", "mix"):
        q_stmt = select(KnowledgeQuestionRecord).where(KnowledgeQuestionRecord.course_id == c_uuid)
        if selected_lesson_uuids:
            q_stmt = q_stmt.where(KnowledgeQuestionRecord.lesson_id.in_(selected_lesson_uuids))
        if outline_uuid:
            q_stmt = q_stmt.where(KnowledgeQuestionRecord.outline_node_id == outline_uuid)
        q_records = db.scalars(q_stmt.order_by(KnowledgeQuestionRecord.question_order.asc(), KnowledgeQuestionRecord.created_at.asc())).all()

        for rec in q_records:
            if _is_excluded(rec.question_text, exclude_stems):
                continue
            q_type = rec.question_type or "multiple_choice"
            points = 10 if q_type == "essay" else 5
            extracted_questions.append(
                GeneratedQuestion(
                    id=len(extracted_questions) + 1,
                    question_type=q_type,
                    difficulty="medium",
                    topic=topics[0] if (topics and topics[0]) else "مذكرات الدرس",
                    question_text=rec.question_text,
                    points=points,
                    correct_answer=rec.correct_answer or "",
                    explanation=rec.explanation or "سؤال مستخرج نصياً من وثائق ومذكرات الدرس الأصلية.",
                    options=rec.options_json,
                    image_asset_ids=rec.image_asset_ids_json or [],
                )
            )

    # 2. Pull indexed units from Knowledge Center sources for this course (document-only)
    if c_uuid:
        ku_stmt = select(KnowledgeUnitRecord).where(
            KnowledgeUnitRecord.course_id == c_uuid,
            KnowledgeUnitRecord.source_type == "document",
            KnowledgeUnitRecord.needs_review == False,
        )
        if selected_lesson_uuids:
            ku_stmt = ku_stmt.where(KnowledgeUnitRecord.lesson_id.in_(selected_lesson_uuids))
        if outline_uuid:
            if include_prerequisites:
                from app.services.book_outline import related_outline_node_ids
                ku_stmt = ku_stmt.where(KnowledgeUnitRecord.outline_node_id.in_(related_outline_node_ids(db, outline_uuid)))
            else:
                ku_stmt = ku_stmt.where(KnowledgeUnitRecord.outline_node_id == outline_uuid)
        kc_records = db.scalars(ku_stmt).all()
        for rec in kc_records:
            knowledge_units.append(
                KnowledgeUnit(
                    id=str(rec.id),
                    lesson_id=str(rec.lesson_id or primary_lesson_id),
                    concept=rec.concept,
                    statement=rec.statement,
                    raw_text=rec.details or rec.statement,
                    start_time=0.0,
                    end_time=0.0,
                    page_number=rec.page_number,
                    category=rec.knowledge_type,
                    semantic_confidence=rec.semantic_confidence,
                    image_asset_ids=rec.source_media_ids_json or [],
                )
            )

    # Fallback to lesson_contents if no KnowledgeUnitRecords exist yet
    if not knowledge_units and lesson_contents:
        all_segments: list[Any] = []
        for c_idx, c in enumerate(lesson_contents):
            if isinstance(c, str) and len(c.strip()) >= 15:
                raw_parts = [s.strip() for s in re.split(r"[\.\!\?\n\؛]+", c) if len(s.strip()) >= 15]
                for idx, p in enumerate(raw_parts):
                    all_segments.append({"id": f"cnt_{c_idx}_{idx}", "start_time": 0.0, "end_time": 0.0, "text": p})
        if all_segments:
            knowledge_units = extract_knowledge_units(all_segments, primary_lesson_id)

    # Assemble final questions based on quiz_mode
    final_questions: list[GeneratedQuestion] = []
    current_stems: list[str] = list(exclude_stems)

    # Derive main topic dynamically
    if topics and topics[0] and len(str(topics[0]).strip()) >= 3:
        cleaned_topic = clean_spoken_noise(str(topics[0]))
        main_topic = cleaned_topic if len(cleaned_topic) >= 3 else (knowledge_units[0].concept if knowledge_units else "محتوى الدرس")
    elif knowledge_units:
        main_topic = knowledge_units[0].concept
    else:
        main_topic = "محتوى الدرس"

    allocations = []
    if isinstance(type_allocations, list) and any(
        isinstance(a, dict) and a.get("count", 0) > 0 for a in type_allocations
    ):
        allocations = [a for a in type_allocations if isinstance(a, dict) and a.get("count", 0) > 0]
    else:
        allocations = [
            {"id": "multiple_choice", "label": "اختيار من متعدد", "count": max(1, question_count - 1)},
            {"id": "essay", "label": "سؤال مقالي", "count": 1},
        ]

    if quiz_mode == "extract":
        final_questions = extracted_questions[:question_count]
    elif quiz_mode == "mix":
        if len(extracted_questions) >= question_count:
            final_questions = extracted_questions[:question_count]
        else:
            final_questions = list(extracted_questions)
            for q in final_questions:
                current_stems.append(q.question_text)
            deficit = question_count - len(final_questions)
            if deficit > 0 and knowledge_units:
                quiz_questions, _ = generate_quiz(knowledge_units, allocations, deficit)
                for q_data in quiz_questions:
                    q_text = q_data.get("question_text", "")
                    if _is_excluded(q_text, current_stems):
                        continue
                    q_type = q_data.get("question_type", "multiple_choice")
                    points = 10 if q_type == "essay" else 5
                    final_questions.append(
                        GeneratedQuestion(
                            id=len(final_questions) + 1,
                            question_type=q_type,
                            difficulty=q_data.get("difficulty", "medium"),
                            topic=q_data.get("source_concept", main_topic),
                            question_text=q_text,
                            points=points,
                            correct_answer=q_data.get("correct_answer"),
                            explanation=q_data.get("explanation", ""),
                            options=q_data.get("options"),
                            withCorrection=q_data.get("withCorrection"),
                            source_concept=q_data.get("source_concept"),
                            image_asset_ids=q_data.get("image_asset_ids") or [],
                        )
                    )
                    current_stems.append(q_text)
                    if len(final_questions) >= question_count:
                        break
    else:  # "generate"
        if knowledge_units:
            quiz_questions, _ = generate_quiz(knowledge_units, allocations, question_count)
            for q_data in quiz_questions:
                q_text = q_data.get("question_text", "")
                if _is_excluded(q_text, current_stems):
                    continue
                q_type = q_data.get("question_type", "multiple_choice")
                points = 10 if q_type == "essay" else 5
                final_questions.append(
                    GeneratedQuestion(
                        id=len(final_questions) + 1,
                        question_type=q_type,
                        difficulty=q_data.get("difficulty", "medium"),
                        topic=q_data.get("source_concept", main_topic),
                        question_text=q_text,
                        points=points,
                        correct_answer=q_data.get("correct_answer"),
                        explanation=q_data.get("explanation", ""),
                        options=q_data.get("options"),
                        withCorrection=q_data.get("withCorrection"),
                        source_concept=q_data.get("source_concept"),
                        image_asset_ids=q_data.get("image_asset_ids") or [],
                    )
                )
                current_stems.append(q_text)
                if len(final_questions) >= question_count:
                    break

    # Re-index questions sequentially
    for idx, q in enumerate(final_questions, start=1):
        q.id = idx

    is_complete = len(final_questions) >= question_count

    if not final_questions:
        return QuizDraftResponse(
            title="تعذر توليد الاختبار",
            description="لم يتم العثور على مذكرات أو أسئلة كافية في هذا الدرس لصياغة اختبار موثوق.",
            total_points=0,
            questions=[
                GeneratedQuestion(
                    id=1,
                    question_type="essay",
                    difficulty="medium",
                    topic="محتوى غير كافٍ",
                    points=0,
                    question_text=(
                        "⚠️ تعذّر توليد اختبار آلي: محتوى الدرس أو المستندات المرفوعة لا تتضمن مادة علمية كافية لصياغة أسئلة تربوية موثوقة. "
                        "يرجى رفع مذكرات أو ملفات أسئلة للدرس وإعادة الفهرسة."
                    ),
                    correct_answer=None,
                    explanation="حارس الجودة والموثوقية العلمية والتربوية.",
                )
            ],
            is_complete=False,
            requires_teacher_approval=True,
            cached=False,
            metadata={"status": "insufficient_content", "quiz_mode": quiz_mode},
        )

    total_points = sum(q.points for q in final_questions)
    return QuizDraftResponse(
        title=payload_data.get("title") or f"اختبار تقييمي: {main_topic}",
        description=f"اختبار تقييمي شامل مبني بدقة تربوية على مذكرات ومستندات درس ({main_topic}).",
        total_points=total_points,
        questions=final_questions,
        is_complete=is_complete,
        requires_teacher_approval=True,
        cached=False,
        metadata={
            "generated_at": datetime.utcnow().isoformat(),
            "mode": f"quiz-intelligence-engine-{quiz_mode}",
            "source": main_topic,
            "quiz_mode": quiz_mode,
            "knowledge_units_count": len(knowledge_units),
            "extracted_count": len([q for q in final_questions if "وثائق ومذكرات الدرس الأصلية" in (q.explanation or "")]),
            "generated_count": len([q for q in final_questions if "وثائق ومذكرات الدرس الأصلية" not in (q.explanation or "")]),
            "is_complete": is_complete,
            "outline_node_id": str(outline_uuid) if outline_uuid else None,
            "include_prerequisite_lessons": include_prerequisites,
        },
    )


@router.post("/quiz/extract-from-file", response_model=QuizDraftResponse)
async def extract_quiz_from_file(
    request: Request,
    db: Db,
    user: TeacherOrAdmin,
    file: UploadFile = File(...),
    course_id: str = Form(...),
    lesson_id: str | None = Form(None),
) -> QuizDraftResponse:
    """Extract questions directly from an uploaded exam / question file (PDF, Word, TXT, JSON, etc.)"""
    from app.api.routes.knowledge_center import (
        _get_kc_temp_dir,
        _resolve_course_uuid,
        _resolve_lesson_uuid,
        _stream_upload_to_file,
    )

    max_exam_bytes = 50 * 1024 * 1024
    filename = sanitize_source_filename(file.filename or "exam_file.txt")
    course_uuid = _resolve_course_uuid(db, user, course_id)
    lesson_uuid = _resolve_lesson_uuid(db, course_uuid, lesson_id)
    staging_file = os.path.join(
        _get_kc_temp_dir(), f"exam_stage_{uuid.uuid4().hex[:12]}_{filename}"
    )
    try:
        size_bytes, checksum = await _stream_upload_to_file(
            uploaded=file,
            dest_path=staging_file,
            max_file_bytes=max_exam_bytes,
        )
        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="الملف المرفوع فارغ.")
        source = create_knowledge_source(
            db=db,
            user=user,
            course_id=course_uuid,
            lesson_id=lesson_uuid,
            filename=filename,
            staged_file_path=staging_file,
            checksum=checksum,
            size_bytes=size_bytes,
            source_role=SourceRole.QUIZ_IMPORT,
            mime_type=file.content_type,
            metadata={"assessment_type": "exam", "extracted_in_quiz_maker": True},
        )
    except Exception:
        if os.path.exists(staging_file):
            try:
                os.remove(staging_file)
            except OSError:
                pass
        db.rollback()
        raise

    process_knowledge_source(db, source.id)
    db.refresh(source)

    extracted_records = db.scalars(
        select(KnowledgeQuestionRecord)
        .where(KnowledgeQuestionRecord.source_id == source.id)
        .order_by(KnowledgeQuestionRecord.question_order.asc(), KnowledgeQuestionRecord.created_at.asc())
    ).all()

    generated_questions: list[GeneratedQuestion] = []
    q_id = 1

    for rec in extracted_records:
        opts: list[QuestionOption] = []
        if rec.options_json and isinstance(rec.options_json, list):
            for opt in rec.options_json:
                if isinstance(opt, dict):
                    opts.append(
                        QuestionOption(
                            key=str(opt.get("key", "")),
                            text=str(opt.get("text", "")),
                            is_correct=bool(opt.get("is_correct", False)),
                        )
                    )

        image_asset_url = None
        asset_link = db.scalars(
            select(KnowledgeQuestionImageLink)
            .where(KnowledgeQuestionImageLink.question_record_id == rec.id)
        ).first()
        if asset_link:
            asset = db.scalars(
                select(KnowledgeAsset)
                .where(KnowledgeAsset.id == asset_link.asset_id)
            ).first()
            if asset:
                image_asset_url = asset.file_path or f"/api/v1/knowledge-center/assets/{asset.id}/view"

        topic = filename
        points = 5
        if rec.metadata_json and isinstance(rec.metadata_json, dict):
            topic = rec.metadata_json.get("topic") or filename
            points = rec.metadata_json.get("points") or 5

        q_type = rec.question_type or "MCQ"
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

        generated_questions.append(
            GeneratedQuestion(
                id=q_id,
                question_type=norm_type,
                difficulty="medium",
                topic=topic,
                question_text=rec.question_text,
                options=opts if opts else None,
                correct_answer=rec.correct_answer or "",
                explanation=rec.explanation or "",
                points=points,
                image_asset_url=image_asset_url,
                image_asset_ids=rec.image_asset_ids_json,
            )
        )
        q_id += 1

    # Safe text-only fallback: STRICTLY for plain text documents (TXT, CSV), NEVER for binary PDFs (Requirement 7)
    is_plain_text_doc = filename.lower().endswith((".txt", ".text", ".csv"))
    if not generated_questions and is_plain_text_doc:
        try:
            with open(source.storage_path, "r", encoding="utf-8", errors="ignore") as source_file:
                lines = [line.strip() for line in source_file if line.strip()]
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
                            correct_answer=cur_ans or (cur_opts[0].text if cur_opts else "إجابة نموذجية"),
                            explanation=cur_exp or f"مستخرج من ملف {filename}",
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
        raise HTTPException(status_code=422, detail="تعذر استخراج أسئلة واضحة من الملف. تأكد من احتواء الملف على أسئلة وبنك امتحانات.")

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
            "source_id": str(source.id),
            "question_count": len(generated_questions),
            "generated_at": datetime.utcnow().isoformat(),
        },
    )


@router.post("/grading/essay", response_model=EssayGradingResponse)
async def grade_essay(
    payload: dict[str, Any],
    user: TeacherOrAdmin,
    request: Request,
    db: Db,
) -> EssayGradingResponse:
    enforce_rate_limit(request, bucket="ai", limit=10, window_seconds=60)
    enforce_ai_access(db, user, request, {"feature": "essay_grading"})
    max_score = float(payload.get("max_score", 10.0)) if isinstance(payload, dict) else 10.0
    if max_score <= 0 or max_score > 1000:
        raise HTTPException(status_code=422, detail="max_score must be between 0 and 1000")
    question_prompt = str(payload.get("question_prompt", "")) if isinstance(payload, dict) else ""
    student_submission = str(payload.get("student_submission", "")) if isinstance(payload, dict) else ""
    rubric = payload.get("rubric", []) if isinstance(payload, dict) else []
    if not student_submission.strip():
        return EssayGradingResponse(
            total_score=0,
            max_score=max_score,
            percentage=0,
            criteria_breakdown=[],
            feedback_summary="لم يكتب الطالب إجابة.",
            confidence_score=1,
            flagged_for_human_review=False,
        )
    if not question_prompt.strip() or not isinstance(rubric, list) or not rubric:
        raise HTTPException(status_code=422, detail="question_prompt and a non-empty rubric are required")
    prompt = (
        "Grade the student answer only against the question and rubric below. Do not infer missing facts. "
        "Return JSON with keys criteria_breakdown, feedback_summary, confidence_score, "
        "flagged_for_human_review. Each breakdown item must contain criterion_id, criterion_name, "
        "score_awarded, max_points, feedback.\n\n"
        f"QUESTION:\n{question_prompt[:20_000]}\n\n"
        f"RUBRIC:\n{_json.dumps(rubric, ensure_ascii=False)[:30_000]}\n\n"
        f"STUDENT ANSWER:\n{student_submission[:30_000]}"
    )
    result = await asyncio.to_thread(_request_grading_from_provider, prompt)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AI_PROVIDER_UNAVAILABLE", "message": "Essay grading provider is unavailable"},
        )
    raw_breakdown = result.get("criteria_breakdown", [])
    if not isinstance(raw_breakdown, list):
        raise HTTPException(status_code=502, detail="AI provider returned an invalid grading schema")
    breakdown: list[dict[str, Any]] = []
    for index, item in enumerate(raw_breakdown):
        if not isinstance(item, dict):
            continue
        criterion = rubric[index] if index < len(rubric) and isinstance(rubric[index], dict) else {}
        criterion_max = min(max_score, max(0.0, float(criterion.get("max_points", item.get("max_points", 0)) or 0)))
        awarded = min(criterion_max, max(0.0, float(item.get("score_awarded", 0) or 0)))
        breakdown.append({
            "criterion_id": str(criterion.get("id", item.get("criterion_id", index))),
            "criterion_name": str(criterion.get("name", item.get("criterion_name", "Criterion"))),
            "score_awarded": round(awarded, 2),
            "max_points": round(criterion_max, 2),
            "feedback": str(item.get("feedback", ""))[:2000],
        })
    total_score = min(max_score, round(sum(item["score_awarded"] for item in breakdown), 2))
    confidence = min(0.9, max(0.0, float(result.get("confidence_score", 0.5) or 0.5)))
    return EssayGradingResponse(
        total_score=total_score,
        max_score=max_score,
        percentage=round((total_score / max_score) * 100, 2),
        criteria_breakdown=breakdown,
        feedback_summary=str(result.get("feedback_summary", "Requires teacher review"))[:4000],
        confidence_score=confidence,
        flagged_for_human_review=bool(result.get("flagged_for_human_review", confidence < 0.7)),
        requires_teacher_approval=True,
    )

@router.post("/lessons/{lesson_id}/reindex")
async def reindex_lesson(
    lesson_id: str,
    user: TeacherOrAdmin,
    db: Db,
) -> dict[str, Any]:
    lesson_uuid = _uuid(lesson_id)
    if not lesson_uuid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid lesson_id")
    lesson_stmt = (
        select(Lesson)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .join(Course, CourseModule.course_id == Course.id)
        .where(Lesson.id == lesson_uuid)
    )
    if user.role != UserRole.PLATFORM_ADMIN:
        lesson_stmt = lesson_stmt.where(Course.institution_id == user.institution_id)
    if user.role == UserRole.TEACHER:
        lesson_stmt = lesson_stmt.where(Course.teacher_id == user.id)
    lesson = db.scalar(lesson_stmt)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    from app.models.knowledge_center import KnowledgeSource
    from app.services.knowledge_center_service import reindex_knowledge_source

    sources = db.scalars(
        select(KnowledgeSource).where(KnowledgeSource.lesson_id == lesson_uuid)
    ).all()

    reindexed_count = 0
    for s in sources:
        try:
            reindex_knowledge_source(db, s.id)
            reindexed_count += 1
        except Exception:
            logger.exception("Failed to reindex source %s for lesson %s", s.id, lesson_uuid)

    return {
        "lesson_id": str(lesson.id),
        "reindexed_sources_count": reindexed_count,
        "message": f"Successfully reindexed {reindexed_count} Knowledge Center sources for lesson.",
    }

@router.post("/risk/predict", response_model=BatchRiskResponse)
async def predict_risk(
    payload: dict[str, Any],
    user: TeacherOrAdmin,
    request: Request,
    db: Db,
) -> BatchRiskResponse:
    enforce_rate_limit(request, bucket="ai", limit=10, window_seconds=60)
    students = payload.get("students", []) if isinstance(payload, dict) else []
    if not isinstance(students, list) or len(students) > 500:
        raise HTTPException(status_code=422, detail="students must be a list of at most 500 items")
    predictions: list[dict[str, Any]] = []
    at_risk_count = 0
    for index, raw_student in enumerate(students):
        if not isinstance(raw_student, dict):
            raise HTTPException(status_code=422, detail=f"Invalid student record at index {index}")

        def bounded(name: str, lower: float, upper: float, default: float) -> float:
            try:
                return min(upper, max(lower, float(raw_student.get(name, default))))
            except (TypeError, ValueError):
                return default

        assignment_ratio = bounded("assignments_submitted_ratio", 0, 1, 0)
        quiz_score = bounded("average_quiz_score", 0, 100, 0)
        completion_ratio = bounded("video_watch_completion_ratio", 0, 1, 0)
        logins = bounded("login_frequency_weekly", 0, 14, 0)
        study_hours = bounded("time_spent_hours_weekly", 0, 40, 0)
        late = bounded("late_submissions_count", 0, 20, 0)
        inactive_days = bounded("days_since_last_activity", 0, 60, 0)
        components = {
            "assignments_submitted_ratio": (1 - assignment_ratio) * 0.25,
            "average_quiz_score": (1 - quiz_score / 100) * 0.25,
            "video_watch_completion_ratio": (1 - completion_ratio) * 0.15,
            "login_frequency_weekly": (1 - min(logins / 5, 1)) * 0.10,
            "time_spent_hours_weekly": (1 - min(study_hours / 6, 1)) * 0.10,
            "late_submissions_count": min(late / 5, 1) * 0.05,
            "days_since_last_activity": min(inactive_days / 14, 1) * 0.10,
        }
        risk_score = round(sum(components.values()), 4)
        risk_level = (
            "critical" if risk_score >= 0.75 else
            "high" if risk_score >= 0.50 else
            "moderate" if risk_score >= 0.30 else
            "low"
        )
        if risk_level in {"high", "critical"}:
            at_risk_count += 1
        top_factors = sorted(components.items(), key=lambda item: item[1], reverse=True)[:3]
        predictions.append({
            "student_id": str(raw_student.get("student_id") or index),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "top_risk_factors": [
                {
                    "feature": feature,
                    "impact": "high" if contribution >= 0.15 else "moderate" if contribution >= 0.08 else "low",
                    "description": f"Risk contribution from {feature}: {contribution:.0%}",
                }
                for feature, contribution in top_factors if contribution > 0
            ],
            "confidence_interval": {
                "lower": max(0.0, round(risk_score - 0.10, 4)),
                "upper": min(1.0, round(risk_score + 0.10, 4)),
            },
            "model_version": "transparent-rules-v1",
        })
    return BatchRiskResponse(
        predictions=predictions,
        total_students=len(predictions),
        at_risk_count=at_risk_count,
        model_metadata={
            "model_type": "transparent_weighted_rules",
            "trained_model": False,
            "requires_human_review": True,
        },
    )

@router.post("/risk/train")
async def train_risk(
    payload: dict[str, Any],
    user: TeacherOrAdmin,
    request: Request,
    db: Db,
) -> dict[str, str]:
    enforce_rate_limit(request, bucket="ai", limit=5, window_seconds=60)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Model training requires the dedicated AI service and persistent model storage.",
    )

@router.post("/tutor/index-course", response_model=IndexCourseResponse)
async def index_course(
    payload: dict[str, Any],
    user: TeacherOrAdmin,
    request: Request,
    db: Db,
) -> IndexCourseResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Direct client-side indexing is disabled; upload sources through Knowledge Center.",
    )

@router.post("/manual/quizzes", response_model=ManualQuizResponse)
async def create_manual_quiz(
    payload: ManualQuizCreate,
    user: TeacherOrAdmin,
    request: Request,
    db: Db,
) -> ManualQuizResponse:
    enforce_rate_limit(request, bucket="manual", limit=10, window_seconds=60)
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
    enforce_rate_limit(request, bucket="manual", limit=10, window_seconds=60)
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
