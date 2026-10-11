from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TranscriptionStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Transcript(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stores high-level metadata and full text for a video transcription."""

    __tablename__ = "transcripts"
    __table_args__ = (
        UniqueConstraint("lesson_id", name="uq_transcripts_lesson_id"),
        Index("ix_transcripts_status", "status"),
    )

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[TranscriptionStatus] = mapped_column(
        String(20), default=TranscriptionStatus.QUEUED, nullable=False
    )
    language: Mapped[str] = mapped_column(String(10), default="ar", nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    full_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="whisper", nullable=False)
    provider_model: Mapped[str] = mapped_column(String(50), default="base", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    segments = relationship(
        "TranscriptSegment",
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.sequence",
    )


class TranscriptSegment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Fine-grained timestamped speech segment from video transcription."""

    __tablename__ = "transcript_segments"
    __table_args__ = (
        UniqueConstraint("transcript_id", "sequence", name="uq_transcript_segments_seq"),
        Index("ix_transcript_segments_lesson", "lesson_id"),
        Index("ix_transcript_segments_time", "transcript_id", "start_time"),
    )

    transcript_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    transcript = relationship("Transcript", back_populates="segments")



class TranscriptionJobStatus(str, Enum):
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    REMOTE_QUEUED = "remote_queued"
    PROCESSING = "processing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class TranscriptionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks asynchronous remote/local transcription job lifecycle."""

    __tablename__ = "transcription_jobs"
    __table_args__ = (
        Index("ix_transcription_jobs_lesson", "lesson_id"),
        Index("ix_transcription_jobs_course", "course_id"),
        Index("ix_transcription_jobs_status", "status"),
    )

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    video_id: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[TranscriptionJobStatus] = mapped_column(
        String(30), default=TranscriptionJobStatus.QUEUED, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), default="kaggle", nullable=False)
    model_name: Mapped[str] = mapped_column(String(50), default="QwenCleo-ASR", nullable=False)
    remote_job_id: Mapped[str | None] = mapped_column(String(120))

    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(100), default="queued", nullable=False)

    signed_download_token_hash: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    signed_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    callback_secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    artifact_url: Mapped[str | None] = mapped_column(String(500))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    segment_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    coverage_ratio: Mapped[float | None] = mapped_column(Float)

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)

    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

