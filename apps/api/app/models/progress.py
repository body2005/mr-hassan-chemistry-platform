from __future__ import annotations

import uuid
from datetime import datetime, timezone
UTC = timezone.utc
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass


from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_values


class VideoEventType(StrEnum):
    PLAY = "play"
    PAUSE = "pause"
    SEEK = "seek"
    RESUME = "resume"
    ENDED = "ended"
    VISIBILITY_CHANGE = "visibilitychange"
    PAGEHIDE = "pagehide"


class VideoEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "video_events"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "client_event_id", name="uq_video_events_student_client_event"
        ),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    client_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[VideoEventType] = mapped_column(
        Enum(
            VideoEventType,
            name="video_event_type",
            native_enum=False,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    position_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    watched_delta_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class LessonProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_lesson_progress_student_lesson"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    last_position_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    watched_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completion_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
