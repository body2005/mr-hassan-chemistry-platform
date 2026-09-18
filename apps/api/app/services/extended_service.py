"""Extended domain services: question versioning, chapters/assets, grades,
AI jobs, report jobs, mastery & risk analytics.

All functions are tenant-scoped by the caller's user.institution_id and raise
LookupError / PermissionError / ValueError which routes translate into the
unified error format.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

UTC = timezone.utc

from app.models.course import Course, CourseModule, Enrollment, Lesson
from app.models.extended import (
    AIJob,
    AIRun,
    Grade,
    LearningObjective,
    LessonAsset,
    QuestionBank,
    QuestionVersion,
    ReportJob,
    RiskAssessment,
    StudentMastery,
)
from app.models.platform import (
    Assignment,
    AssignmentSubmission,
    Question,
    Quiz,
    QuizAttempt,
    QuizAttemptAnswer,
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
    module = db.get(CourseModule, lesson.module_id)
    course = db.get(Course, module.course_id) if module else None
    if course is None or course.institution_id != user.institution_id:
        raise LookupError("Lesson not found")
    _ensure_manager(user)
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
    module = db.get(CourseModule, lesson.module_id)
    course = db.get(Course, module.course_id) if module else None
    if course is None or course.institution_id != user.institution_id:
        raise LookupError("Lesson not found")
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
    ai_generated: bool = False,
    explanation: str | None = None,
) -> QuestionVersion:
    _ensure_manager(user)
    question = Question(
        institution_id=user.institution_id,
        author_id=user.id,
        course_id=course_id,
        version=1,
        question_type=question_type,
        prompt=prompt,
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
        question_type=question_type,
        prompt=prompt,
        options=options,
        correct_answer=correct_answer,
        points=points,
        explanation=explanation,
        difficulty=difficulty,
        topic=topic,
        source=source,
        ai_generated=ai_generated,
    )
    db.add(version_row)

    if bank_id is not None:
        bank = db.scalar(
            select(QuestionBank).where(
                QuestionBank.id == bank_id,
                QuestionBank.institution_id == user.institution_id,
            )
        )
        if bank is None:
            raise LookupError("Question bank not found")

    db.commit()
    db.refresh(version_row)
    return version_row


def update_question_versioned(
    db: Session, user: User, question_id: uuid.UUID, **changes: object
) -> QuestionVersion:
    """Material change => new immutable version; old attempts keep the old row."""
    question = db.scalar(
        select(Question).where(
            Question.id == question_id,
            Question.institution_id == user.institution_id,
        )
    )
    if question is None:
        raise LookupError("Question not found")
    _ensure_manager(user)

    material_fields = {"prompt", "options", "correct_answer", "points", "question_type"}
    material_change = any(field in changes for field in material_fields)

    latest = db.scalar(
        select(func.max(QuestionVersion.version)).where(
            QuestionVersion.question_id == question.id
        )
    ) or 1

    new_version_number = latest + 1 if material_change else latest
    if material_change:
        question.version = new_version_number
        for field in ("prompt", "options", "correct_answer", "points", "question_type"):
            if field in changes:
                setattr(question, field, changes[field])

    current = db.scalars(
        select(QuestionVersion)
        .where(QuestionVersion.question_id == question.id)
        .order_by(QuestionVersion.version.desc())
    ).first()

    version_row = QuestionVersion(
        question_id=question.id,
        version=new_version_number,
        question_type=changes.get("question_type", current.question_type),
        prompt=changes.get("prompt", current.prompt),
        options=changes.get("options", current.options),
        correct_answer=changes.get("correct_answer", current.correct_answer),
        points=changes.get("points", current.points),
        explanation=changes.get("explanation", current.explanation),
        difficulty=changes.get("difficulty", current.difficulty),
        topic=changes.get("topic", current.topic),
        source=current.source,
        ai_generated=current.ai_generated,
    )
    db.add(version_row)
    db.commit()
    db.refresh(version_row)
    return version_row


def list_question_versions(
    db: Session, user: User, question_id: uuid.UUID
) -> list[QuestionVersion]:
    question = db.scalar(
        select(Question).where(
            Question.id == question_id,
            Question.institution_id == user.institution_id,
        )
    )
    if question is None:
        raise LookupError("Question not found")
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
    if actor.role == UserRole.STUDENT:
        raise PermissionError("Students cannot write grades")
    existing = db.scalar(
        select(Grade).where(
            Grade.student_id == student_id,
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
    if viewer.role == UserRole.STUDENT and viewer.id != student_id:
        raise PermissionError("Students can only view their own grades")
    rows = db.scalars(
        select(Grade)
        .where(
            Grade.institution_id == viewer.institution_id,
            Grade.student_id == student_id,
            Grade.is_current.is_(True),
        )
        .order_by(Grade.updated_at.desc())
    ).all()
    return list(rows)


# ---------------------------------------------------------------------------
# AI jobs + runs
# ---------------------------------------------------------------------------

ALLOWED_AI_TASKS = {
    "quiz_generation",
    "essay_grading",
    "document_processing",
    "report_narrative",
}


def enqueue_ai_job(
    db: Session,
    user: User,
    *,
    task: str,
    payload: dict,
    idempotency_key: str | None,
) -> AIJob:
    if task not in ALLOWED_AI_TASKS:
        raise ValueError("Unsupported AI task")
    if idempotency_key:
        existing = db.scalar(select(AIJob).where(AIJob.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
    job = AIJob(
        institution_id=user.institution_id,
        requested_by=user.id,
        task=task,
        payload_json=payload,
        idempotency_key=idempotency_key,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_ai_job(db: Session, user: User, job_id: uuid.UUID) -> AIJob:
    job = db.scalar(
        select(AIJob).where(
            AIJob.id == job_id,
            AIJob.institution_id == user.institution_id,
        )
    )
    if job is None:
        raise LookupError("AI job not found")
    return job


def record_ai_run(db: Session, **fields: object) -> AIRun:
    run = AIRun(**fields)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


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
    if idempotency_key:
        existing = db.scalar(
            select(ReportJob).where(ReportJob.idempotency_key == idempotency_key)
        )
        if existing is not None:
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
    job = db.scalar(
        select(ReportJob).where(
            ReportJob.id == job_id,
            ReportJob.institution_id == user.institution_id,
        )
    )
    if job is None:
        raise LookupError("Report job not found")
    return job


# ---------------------------------------------------------------------------
# Mastery & risk analytics
# ---------------------------------------------------------------------------

def compute_student_mastery(db: Session, user: User, student_id: uuid.UUID) -> list[dict]:
    """Explainable mastery per learning objective from graded quiz answers."""
    if user.role == UserRole.STUDENT and user.id != student_id:
        raise PermissionError("Students can only view their own mastery")
    objectives = db.scalars(
        select(LearningObjective).where(
            LearningObjective.institution_id == user.institution_id
        )
    ).all()
    result: list[dict] = []
    for objective in objectives:
        # Evidence: questions tagged with this objective in attempts of this student.
        rows = db.execute(
            select(QuizAttemptAnswer.awarded_points, Question.points)
            .join(QuizAttemptAnswer, QuizAttemptAnswer.question_id == Question.id)
            .join(
                QuizAttempt,
                QuizAttempt.id == QuizAttemptAnswer.attempt_id,
            )
            .where(
                QuizAttempt.student_id == student_id,
                Question.learning_objective == objective.code,
            )
        ).all()
        if not rows:
            continue
        earned = sum(float(r[0] or 0) for r in rows)
        total = sum(float(r[1] or 0) for r in rows)
        if total <= 0:
            continue
        mastery = round(min(1.0, earned / total), 3)
        result.append(
            {
                "objective_id": str(objective.id),
                "code": objective.code,
                "title": objective.title,
                "mastery": mastery,
                "evidence_count": len(rows),
            }
        )
    return result


RISK_WEIGHTS = {
    "quiz_average": 0.35,
    "video_completion": 0.25,
    "assignment_delay_ratio": 0.2,
    "recent_activity_days": 0.2,
}


def assess_student_risk(
    db: Session, viewer: User, student_id: uuid.UUID, course_id: uuid.UUID | None
) -> dict:
    """Explainable risk score: components are reported alongside the score."""
    if viewer.role == UserRole.STUDENT and viewer.id != student_id:
        raise PermissionError("Students can only view their own risk profile")

    # Quiz average (0..1)
    scores = db.scalars(
        select(QuizAttempt.score).where(
            QuizAttempt.student_id == student_id, QuizAttempt.score.is_not(None)
        )
    ).all()
    totals = db.scalars(
        select(QuizAttempt.total_points).where(
            QuizAttempt.student_id == student_id, QuizAttempt.total_points.is_not(None)
        )
    ).all()
    ratios = [s / t for s, t in zip(scores, totals) if t]
    quiz_average = sum(ratios) / len(ratios) if ratios else None

    # Assignment delay ratio
    submissions = db.scalars(
        select(AssignmentSubmission).where(AssignmentSubmission.student_id == student_id)
    ).all()
    delayed = 0
    graded = 0
    for submission in submissions:
        assignment = db.get(Assignment, submission.assignment_id)
        if assignment is None or assignment.due_at is None:
            continue
        graded += 1
        if submission.submitted_at > assignment.due_at:
            delayed += 1
    delay_ratio = delayed / graded if graded else None

    factors = {
        "quiz_average": quiz_average,
        "assignment_delay_ratio": delay_ratio,
        # video completion/activity come from progress service when available
    }

    # Weighted score where missing evidence contributes neutral 0.5
    def component(name: str, value: float | None, invert: bool = False) -> float:
        v = value if value is not None else 0.5
        if invert:
            v = 1.0 - v
        return max(0.0, min(1.0, v))

    risk = (
        RISK_WEIGHTS["quiz_average"] * component("q", quiz_average, invert=True)
        + RISK_WEIGHTS["assignment_delay_ratio"] * component("d", delay_ratio)
        + RISK_WEIGHTS["video_completion"] * 0.5  # placeholder until telemetry join lands
        + RISK_WEIGHTS["recent_activity_days"] * 0.5
    )
    risk = round(max(0.0, min(1.0, risk)), 3)
    band = "high" if risk >= 0.66 else ("medium" if risk >= 0.33 else "low")

    explanation = {
        "weights": RISK_WEIGHTS,
        "components": factors,
        "notes": [
            "Missing signals contribute a neutral 0.5 rather than being ignored.",
            "Score is deterministic and explainable; ML-based scoring augments it later.",
        ],
    }
    assessment = RiskAssessment(
        institution_id=viewer.institution_id,
        student_id=student_id,
        course_id=course_id,
        risk_score=risk,
        band=band,
        factors_json=explanation,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return {
        "student_id": str(student_id),
        "risk_score": risk,
        "band": band,
        "explanation": explanation,
    }


def _ensure_manager(user: User) -> None:
    if user.role not in {UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN}:
        raise PermissionError("Insufficient permissions")
