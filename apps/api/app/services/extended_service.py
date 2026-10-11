"""Extended domain services: question versioning, chapters/assets, grades,
AI jobs, report jobs, mastery & risk analytics.

All functions are tenant-scoped by the caller's user.institution_id and raise
LookupError / PermissionError / ValueError which routes translate into the
unified error format.
"""
from __future__ import annotations

import uuid
import math
from types import SimpleNamespace
from datetime import datetime, timezone

from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session, aliased
from app.core.question_policy import validate_question_content

UTC = timezone.utc

from app.models.course import Course, CourseModule, Enrollment, EnrollmentStatus, Lesson
from app.models.extended import (
    Grade,
    LearningObjective,
    LessonAsset,
    QuestionBank,
    QuestionVersion,
    ReportJob,
    StudentMastery,
)
from app.models.platform import (
    Assignment,
    AssignmentSubmission,
    Question,
    Quiz,
    QuizAttempt,
    QuizAttemptAnswer,
    AttemptStatus,
)
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Chapters & lesson assets
# ---------------------------------------------------------------------------

def create_chapter(
    db: Session, user: User, module_id: uuid.UUID, title: str, position: int | None
) -> object:
    from app.models.extended import Chapter

    module = db.scalar(
        select(CourseModule).where(CourseModule.id == module_id)
    )
    if module is None:
        raise LookupError("Module not found")
    course = db.get(Course, module.course_id)
    if course is None or course.institution_id != user.institution_id:
        raise LookupError("Module not found")
    _ensure_manager(user)
    if position is None:
        position = (
            db.scalar(select(func.max(Chapter.position)).where(Chapter.module_id == module.id))
            or 0
        ) + 1
    chapter = Chapter(module_id=module.id, title=title.strip(), position=position)
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


def create_lesson_asset(
    db: Session,
    user: User,
    lesson_id: uuid.UUID,
    *,
    asset_kind: str,
    object_key: str | None,
    external_url: str | None,
    filename: str | None,
    mime_type: str | None,
    size_bytes: int | None,
    duration_seconds: int | None,
) -> LessonAsset:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise LookupError("Lesson not found")
    course = db.get(Course, lesson.course_id)
    if course is None or course.institution_id != user.institution_id:
        raise LookupError("Lesson not found")
    _ensure_manager(user)
    if user.role == UserRole.TEACHER and course.teacher_id != user.id:
        raise LookupError("Lesson not found")
    if object_key:
        raise ValueError("Object keys must be created by the authenticated material-upload endpoint")
    asset = LessonAsset(
        lesson_id=lesson.id,
        institution_id=user.institution_id,
        asset_kind=asset_kind,
        object_key=object_key,
        external_url=external_url,
        filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        duration_seconds=duration_seconds,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def list_lesson_assets(db: Session, user: User, lesson_id: uuid.UUID) -> list[LessonAsset]:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise LookupError("Lesson not found")
    course = db.get(Course, lesson.course_id)
    if course is None or course.institution_id != user.institution_id:
        raise LookupError("Lesson not found")
    from app.services.payment_service import can_access_lesson_content
    if user.role == UserRole.TEACHER and course.teacher_id != user.id:
        raise LookupError("Lesson not found")
    if user.role == UserRole.STUDENT and not can_access_lesson_content(db, user, lesson.id):
        raise PermissionError("Lesson access required")
    return list(
        db.scalars(select(LessonAsset).where(LessonAsset.lesson_id == lesson.id)).all()
    )


# ---------------------------------------------------------------------------
# Question banks + versioning
# ---------------------------------------------------------------------------

def create_question_versioned(
    db: Session,
    user: User,
    *,
    course_id: uuid.UUID | None,
    bank_id: uuid.UUID | None,
    question_type: str,
    prompt: str,
    options: list | None,
    correct_answer: object | None,
    points: float,
    learning_objective: str | None,
    difficulty: str | None,
    topic: str | None,
    source: str = "manual",
    explanation: str | None = None,
) -> QuestionVersion:
    _ensure_manager(user)
    if course_id is not None:
        _managed_course(db, user, course_id)
    validate_question_content(SimpleNamespace(question_type=question_type, prompt=prompt,
        options=options, correct_answer=correct_answer, points=points,
        learning_objective=learning_objective))
    if bank_id is not None:
        bank = db.scalar(select(QuestionBank).where(QuestionBank.id == bank_id,
            QuestionBank.institution_id == user.institution_id))
        if bank is None:
            raise LookupError("Question bank not found")
    question = Question(
        institution_id=user.institution_id,
        author_id=user.id,
        course_id=course_id,
        version=1,
        question_type=question_type.strip().lower(),
        prompt=prompt.strip(),
        options=options,
        correct_answer=correct_answer,
        points=points,
        learning_objective=learning_objective,
    )
    db.add(question)
    db.flush()

    version_row = QuestionVersion(
        question_id=question.id,
        version=1,
        question_type=question_type.strip().lower(),
        prompt=prompt.strip(),
        options=options,
        correct_answer=correct_answer,
        points=points,
        explanation=explanation,
        difficulty=difficulty,
        topic=topic,
        source=source,
    )
    db.add(version_row)

    db.commit()
    db.refresh(version_row)
    return version_row


def update_question_versioned(
    db: Session, user: User, question_id: uuid.UUID, **changes: object
) -> QuestionVersion:
    """Validate the merged content first; every accepted edit creates a revision."""
    question = db.scalar(
        select(Question).where(
            Question.id == question_id,
            Question.institution_id == user.institution_id,
        ).with_for_update()
    )
    if question is None:
        raise LookupError("Question not found")
    _ensure_manager(user)
    _ensure_question_manager(db, user, question)

    current = db.scalars(
        select(QuestionVersion)
        .where(QuestionVersion.question_id == question.id)
        .order_by(QuestionVersion.version.desc())
    ).first()
    content_fields = ("prompt", "options", "correct_answer", "points", "question_type")
    allowed = {*content_fields, "explanation", "difficulty", "topic"}
    if not changes or not set(changes).issubset(allowed):
        raise ValueError("Invalid question update fields")
    merged = {field: changes.get(field, getattr(question, field)) for field in content_fields}
    merged["learning_objective"] = question.learning_objective
    validate_question_content(SimpleNamespace(**merged))
    for field, maximum in (("explanation", 10_000), ("difficulty", 20), ("topic", 200)):
        value = changes.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > maximum):
            raise ValueError(f"Invalid {field}")
    new_version_number = max(question.version, current.version if current else 0) + 1
    version_row = QuestionVersion(
        question_id=question.id,
        version=new_version_number,
        question_type=merged["question_type"].strip().lower(),
        prompt=merged["prompt"].strip(),
        options=merged["options"],
        correct_answer=merged["correct_answer"],
        points=merged["points"],
        explanation=changes.get("explanation", current.explanation if current else None),
        difficulty=changes.get("difficulty", current.difficulty if current else None),
        topic=changes.get("topic", current.topic if current else None),
        source=current.source if current else "manual",
    )
    # No mapped state was modified before the complete policy passed.
    question.version = new_version_number
    for field in content_fields:
        setattr(question, field, getattr(version_row, field))
    db.add(version_row)
    db.commit()
    db.refresh(version_row)
    return version_row


def list_question_versions(
    db: Session, user: User, question_id: uuid.UUID
) -> list[QuestionVersion]:
    _ensure_manager(user)
    question = db.scalar(
        select(Question).where(
            Question.id == question_id,
            Question.institution_id == user.institution_id,
        )
    )
    if question is None:
        raise LookupError("Question not found")
    _ensure_question_manager(db, user, question)
    return list(
        db.scalars(
            select(QuestionVersion)
            .where(QuestionVersion.question_id == question.id)
            .order_by(QuestionVersion.version.asc())
        ).all()
    )


# ---------------------------------------------------------------------------
# Grades ledger
# ---------------------------------------------------------------------------

def record_grade(
    db: Session,
    actor: User,
    *,
    student_id: uuid.UUID,
    course_id: uuid.UUID | None,
    item_type: str,
    item_id: uuid.UUID | None,
    score: float,
    max_score: float,
    feedback: str | None,
) -> Grade:
    _ensure_manager(actor)
    # Lock an existing parent, not only the grade: the first grade has no row
    # to lock. All updates for this student serialize across API workers.
    student = db.scalar(select(User).where(
        User.id == student_id, User.institution_id == actor.institution_id,
        User.role == UserRole.STUDENT, User.deleted_at.is_(None),
    ).with_for_update())
    if student is None:
        raise LookupError("Student not found")
    if item_type not in {"course", "quiz", "assignment"}:
        raise ValueError("Unsupported grade item type")
    if not (0 <= score <= max_score and max_score > 0):
        raise ValueError("Score must be between zero and maximum score")
    if item_type in {"quiz", "assignment"}:
        model = Quiz if item_type == "quiz" else Assignment
        item = db.get(model, item_id) if item_id else None
        if item is None or item.institution_id != actor.institution_id:
            raise LookupError("Assessment not found")
        if course_id is not None and course_id != item.course_id:
            raise ValueError("Assessment does not belong to the supplied course")
        course_id = item.course_id
    elif item_id is not None:
        if course_id is not None and item_id != course_id:
            raise ValueError("Course grade item does not match course")
        course_id = item_id
    if course_id is not None:
        _managed_course(db, actor, course_id)
        if db.scalar(select(Enrollment.id).where(
            Enrollment.student_id == student_id, Enrollment.course_id == course_id,
            Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        )) is None:
            raise LookupError("Student enrollment not found")
    elif actor.role == UserRole.TEACHER:
        raise PermissionError("Teachers can only grade their own course enrollments")
    existing = db.scalar(
        select(Grade).where(
            Grade.institution_id == actor.institution_id,
            Grade.student_id == student_id,
            Grade.course_id == course_id,
            Grade.item_type == item_type,
            Grade.item_id == item_id,
            Grade.is_current.is_(True),
        )
    )
    now = datetime.now(UTC)
    if existing is not None:
        existing.is_current = False
        existing.updated_at = now
        db.add(existing)
        # Retire the old row before inserting under the current-only index.
        db.flush()
    grade = Grade(
        institution_id=actor.institution_id,
        student_id=student_id,
        course_id=course_id,
        item_type=item_type,
        item_id=item_id,
        score=score,
        max_score=max_score,
        feedback=feedback,
        graded_by=actor.id,
        is_current=True,
    )
    db.add(grade)
    db.commit()
    db.refresh(grade)
    return grade


def student_grades(db: Session, viewer: User, student_id: uuid.UUID) -> list[Grade]:
    scope = _student_read_course_scope(db, viewer, student_id)
    query = (select(Grade)
        .where(
            Grade.institution_id == viewer.institution_id,
            Grade.student_id == student_id,
            Grade.is_current.is_(True),
        )
        .order_by(Grade.updated_at.desc())
    )
    if scope is not None:
        query = query.where(Grade.course_id.in_(scope))
    rows = db.scalars(query).all()
    return list(rows)


# ---------------------------------------------------------------------------
# Report jobs
# ---------------------------------------------------------------------------

ALLOWED_REPORT_KINDS = {
    "student",
    "class",
    "course",
    "performance",
    "risk",
}


def create_report_job(
    db: Session,
    user: User,
    *,
    report_kind: str,
    params: dict,
    fmt: str,
    idempotency_key: str | None,
) -> ReportJob:
    if user.role == UserRole.STUDENT:
        raise PermissionError("Reports require staff role")
    if report_kind not in ALLOWED_REPORT_KINDS:
        raise ValueError("Unsupported report kind")
    if fmt not in {"xlsx", "pdf"}:
        raise ValueError("Unsupported report format")
    _ensure_manager(user)
    # Serializes first-use as well as replay; the composite DB constraint is
    # a second line of defence, not a replacement for payload validation.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    if idempotency_key:
        existing = db.scalar(
            select(ReportJob).where(ReportJob.idempotency_key == idempotency_key,
                                   ReportJob.institution_id == user.institution_id,
                                   ReportJob.requested_by == user.id)
        )
        if existing is not None:
            if (existing.report_kind, existing.params_json, existing.format) != (report_kind, params, fmt):
                raise ValueError("IDEMPOTENCY_KEY_REUSED")
            return existing
    job = ReportJob(
        institution_id=user.institution_id,
        requested_by=user.id,
        report_kind=report_kind,
        params_json=params,
        format=fmt,
        idempotency_key=idempotency_key,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_report_job(db: Session, user: User, job_id: uuid.UUID) -> ReportJob:
    _ensure_manager(user)
    job = db.scalar(
        select(ReportJob).where(
            ReportJob.id == job_id,
            ReportJob.institution_id == user.institution_id,
            ReportJob.requested_by == user.id,
        )
    )
    if job is None:
        raise LookupError("Report job not found")
    return job


# ---------------------------------------------------------------------------
# Mastery analytics
# ---------------------------------------------------------------------------

def compute_student_mastery(db: Session, user: User, student_id: uuid.UUID) -> list[dict]:
    return compute_student_mastery_report(db, user, student_id)["items"]


def compute_student_mastery_report(db: Session, user: User, student_id: uuid.UUID) -> dict:
    """Latest official, submitted and fully graded evidence, with frozen weights.

    Legacy evidence is reported, not guessed from a question's current weight.
    Two batched reads replace mutable-bank aggregation; no per-answer query.
    """
    scope = _student_read_course_scope(db, user, student_id)
    pending = select(QuizAttemptAnswer.id).where(QuizAttemptAnswer.attempt_id == QuizAttempt.id,
        QuizAttemptAnswer.graded_at.is_(None)).exists()
    query = (select(QuizAttempt, Quiz.course_id, pending.label("pending"))
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .join(Course, Course.id == Quiz.course_id)
        .where(QuizAttempt.institution_id == user.institution_id,
               Quiz.institution_id == user.institution_id,
               Course.institution_id == user.institution_id,
               QuizAttempt.student_id == student_id,
               QuizAttempt.is_practice.is_(False),
               QuizAttempt.status == AttemptStatus.SUBMITTED,
               QuizAttempt.submitted_at.is_not(None))
        .order_by(QuizAttempt.attempt_number.desc(), QuizAttempt.submitted_at.desc(), QuizAttempt.id))
    if scope is not None:
        query = query.where(Quiz.course_id.in_(scope))
    if user.role == UserRole.STUDENT:
        query = query.where(QuizAttempt.results_approved_at.is_not(None))
    latest = {}
    for attempt, course_id, is_pending in db.execute(query):
        latest.setdefault(attempt.quiz_id, (attempt, course_id, is_pending))
    selected = {attempt.id: (attempt, course_id) for attempt, course_id, is_pending in latest.values() if not is_pending}
    legacy = sum(1 for attempt, _ in selected.values() if attempt.question_snapshot is None)
    invalid = 0
    totals = {}
    answers = db.scalars(select(QuizAttemptAnswer).where(
        QuizAttemptAnswer.attempt_id.in_(selected), QuizAttemptAnswer.graded_at.is_not(None))).all() if selected else []
    for answer in answers:
        attempt, course_id = selected[answer.attempt_id]
        if attempt.question_snapshot is None:
            continue
        snapshot = answer.question_snapshot
        if snapshot is None:
            invalid += 1
            continue
        try:
            earned, total = float(answer.awarded_points), float(snapshot["points"])
            if (snapshot["question_id"] != str(answer.question_id)
                    or snapshot["course_id"] != str(course_id)
                    or not math.isfinite(earned) or not math.isfinite(total)
                    or total <= 0 or not 0 <= earned <= total):
                raise ValueError("Invalid frozen evidence")
        except (KeyError, TypeError, ValueError):
            invalid += 1
            continue
        objective_id = snapshot.get("objective_id")
        if objective_id is None:
            continue
        entry = totals.setdefault(objective_id, dict(objective_id=objective_id,
            code=snapshot["learning_objective"], title=snapshot["objective_title"],
            earned=0.0, total=0.0, evidence_count=0))
        entry["earned"] += earned
        entry["total"] += total
        entry["evidence_count"] += 1
    items = [dict(objective_id=e["objective_id"], code=e["code"], title=e["title"],
                  mastery=round(e["earned"] / e["total"], 3), evidence_count=e["evidence_count"])
             for e in sorted(totals.values(), key=lambda e: (e["code"], e["objective_id"]))]
    return dict(items=items, evidence_policy="frozen/latest-submitted-official/fully-graded/v1",
        legacy_unverified_count=legacy, invalid_evidence_count=invalid,
        pending_attempt_count=sum(1 for _, _, is_pending in latest.values() if is_pending))


def _student_read_course_scope(db: Session, viewer: User, student_id: uuid.UUID):
    if viewer.role == UserRole.STUDENT and viewer.id != student_id:
        raise PermissionError("Students can only view their own academic data")
    student = db.scalar(select(User.id).where(User.id == student_id,
        User.institution_id == viewer.institution_id, User.role == UserRole.STUDENT,
        User.deleted_at.is_(None)))
    if student is None:
        raise LookupError("Student not found")
    if viewer.role != UserRole.TEACHER:
        return None
    scope = select(Course.id).join(Enrollment, Enrollment.course_id == Course.id).where(
        Course.institution_id == viewer.institution_id, Course.teacher_id == viewer.id,
        Enrollment.student_id == student_id,
        Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]))
    if db.scalar(scope.limit(1)) is None:
        raise LookupError("Student not found")
    return scope



def _ensure_manager(user: User) -> None:
    if user.role not in {UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN}:
        raise PermissionError("Insufficient permissions")


def _managed_course(db: Session, user: User, course_id: uuid.UUID) -> Course:
    course = db.get(Course, course_id)
    if (course is None or course.institution_id != user.institution_id
            or (user.role == UserRole.TEACHER and course.teacher_id != user.id)):
        raise LookupError("Course not found")
    return course


def _ensure_question_manager(db: Session, user: User, question: Question) -> None:
    if user.role != UserRole.TEACHER:
        return  # staff role and tenant were checked by the caller
    if question.course_id is not None:
        _managed_course(db, user, question.course_id)
    elif question.author_id != user.id:
        raise LookupError("Question not found")
