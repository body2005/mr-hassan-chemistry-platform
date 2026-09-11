"""Extended LMS domain models: chapters, question versioning, rubrics, grades,
notification delivery, AI jobs, analytics, reports, idempotency.

All models follow the same conventions as the core models:
UUID PKs, timezone-aware timestamps, FKs with explicit ondelete behavior.
"""
from __future__ import annotations

import uuid
from datetime import datetime
try:
    from enum import StrEnum
except ImportError:  # Python 3.10
    from enum import Enum
    class StrEnum(str, Enum):
        pass

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.course import CourseModule  # noqa: F401  (FK target)


# ---------------------------------------------------------------------------
# Curriculum: chapters + lesson assets
# ---------------------------------------------------------------------------

class Chapter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("module_id", "position", name="uq_chapter_module_position"),
    )

    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_modules.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class LessonAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lesson_assets"

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    asset_kind: Mapped[str] = mapped_column(String(40), nullable=False)  # video|pdf|document|link|attachment
    object_key: Mapped[str | None] = mapped_column(String(512))
    external_url: Mapped[str | None] = mapped_column(String(1024))
    filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# Question bank + immutable versions
# ---------------------------------------------------------------------------

class QuestionBank(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_banks"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class QuestionVersion(UUIDPrimaryKeyMixin, Base):
    """Immutable snapshot of a question at a point in time. Attempts reference
    this table so historical grading never changes retroactively."""

    __tablename__ = "question_versions"
    __table_args__ = (
        UniqueConstraint("question_id", "version", name="uq_question_version_number"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list | None] = mapped_column(JSON)
    correct_answer: Mapped[object | None] = mapped_column(JSON)
    points: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str | None] = mapped_column(String(20))
    topic: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str | None] = mapped_column(String(40))  # manual|ai_generated
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Rubrics & grade ledger
# ---------------------------------------------------------------------------

class Rubric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rubrics"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    total_points: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)


class RubricCriterion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rubric_criteria"

    rubric_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rubrics.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Grade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Final grade ledger. One row per (student, item); superseded values kept
    with is_current=False for full history."""

    __tablename__ = "grades"
    __table_args__ = (
        Index("ix_grades_current", "student_id", "item_type", "item_id", unique=True),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), index=True
    )
    item_type: Mapped[str] = mapped_column(String(40), nullable=False)  # quiz|assignment|course
    item_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text)
    graded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ---------------------------------------------------------------------------
# Notification fan-out (recipient/delivery separation)
# ---------------------------------------------------------------------------

class NotificationRecipientState(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_recipient_states"
    __table_args__ = (
        UniqueConstraint("notification_id", "recipient_id", name="uq_notif_recipient"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "event_type", "event_source_id", "recipient_id",
            name="uq_notif_delivery_dedup",
        ),
    )

    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notifications.id", ondelete="SET NULL"), index=True
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    channel: Mapped[str] = mapped_column(String(30), default="in_app", nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    event_source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)  # scheduled|queued|sent|read|failed|cancelled
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Learning objectives, mastery, risk, interventions
# ---------------------------------------------------------------------------

class LearningObjective(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_objectives"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_objectives.id", ondelete="SET NULL")
    )


class StudentMastery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_mastery"
    __table_args__ = (
        UniqueConstraint("student_id", "objective_id", name="uq_mastery_student_objective"),
        CheckConstraint("mastery BETWEEN 0 AND 1", name="ck_mastery_range"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    objective_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_objectives.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mastery: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RiskAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        Index("ix_risk_student_latest", "student_id", "created_at"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), index=True
    )
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0..1
    band: Mapped[str] = mapped_column(String(20), nullable=False)     # low|medium|high
    factors_json: Mapped[dict | list | None] = mapped_column(JSON)     # explainable contributors
    model_version: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Intervention(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "interventions"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    risk_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="SET NULL"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(60), nullable=False)  # recommended_lesson|targeted_practice|follow_up_quiz|teacher_alert
    payload_json: Mapped[dict | list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="proposed", nullable=False)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


# ---------------------------------------------------------------------------
# Async report jobs
# ---------------------------------------------------------------------------

class ReportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_jobs"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    report_kind: Mapped[str] = mapped_column(String(60), nullable=False)  # student|class|course|performance|risk
    params_json: Mapped[dict | list | None] = mapped_column(JSON)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    format: Mapped[str] = mapped_column(String(10), default="xlsx", nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# AI job queue + audit runs
# ---------------------------------------------------------------------------

class AIJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        Index("ix_ai_jobs_state", "status", "created_at"),
    )

    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), index=True
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    task: Mapped[str] = mapped_column(String(60), nullable=False)  # quiz_generation|essay_grading|document_processing|report_narrative
    payload_json: Mapped[dict | list | None] = mapped_column(JSON)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)  # queued|processing|completed|failed|cancelled
    result_json: Mapped[dict | list | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit record for every actual provider call, including fallbacks."""

    __tablename__ = "ai_runs"

    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_jobs.id", ondelete="SET NULL"), index=True
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    task: Mapped[str] = mapped_column(String(60), nullable=False)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    output_json: Mapped[dict | list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success|error|timeout|fallback|cancelled
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Idempotency ledger (generic middleware-level dedup)
# ---------------------------------------------------------------------------

class IdempotencyKey(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str | None] = mapped_column(String(64))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_json: Mapped[dict | list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
