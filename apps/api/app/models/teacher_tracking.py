"""Teacher-private tracking definitions and student cell values."""

import uuid

from sqlalchemy import JSON, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TeacherTrackingColumn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teacher_tracking_columns"
    __table_args__ = (
        UniqueConstraint("id", "institution_id", "teacher_id", name="uq_tracking_column_scope"),
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    data_type: Mapped[str] = mapped_column(String(16))
    table_context: Mapped[str] = mapped_column(String(16))
    academic_year: Mapped[str] = mapped_column(String(20))


class TeacherTrackingValue(TimestampMixin, Base):
    __tablename__ = "teacher_tracking_values"
    __table_args__ = (
        ForeignKeyConstraint(
            ["column_id", "institution_id", "teacher_id"],
            [
                "teacher_tracking_columns.id",
                "teacher_tracking_columns.institution_id",
                "teacher_tracking_columns.teacher_id",
            ],
            ondelete="CASCADE",
            name="fk_tracking_value_scope",
        ),
    )
    column_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(index=True)
    teacher_id: Mapped[uuid.UUID] = mapped_column(index=True)
    value: Mapped[str | float | bool] = mapped_column(JSON, nullable=False)
