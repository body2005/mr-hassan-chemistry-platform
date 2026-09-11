"""video telemetry and lesson progress

Revision ID: a4b5c6d7e8f9
Revises: 9e1f6a9b2c3d
Create Date: 2026-08-25 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4b5c6d7e8f9"
down_revision: str | None = "9e1f6a9b2c3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_events",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("client_event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("position_seconds", sa.Float(), nullable=False),
        sa.Column("watched_delta_seconds", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_video_events"),
        sa.UniqueConstraint("student_id", "client_event_id", name="uq_video_events_student_client_event"),
    )
    op.create_index("ix_video_events_institution_id", "video_events", ["institution_id"])
    op.create_index("ix_video_events_student_id", "video_events", ["student_id"])
    op.create_index("ix_video_events_lesson_id", "video_events", ["lesson_id"])

    op.create_table(
        "lesson_progress",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("last_position_seconds", sa.Float(), nullable=False),
        sa.Column("watched_duration_seconds", sa.Float(), nullable=False),
        sa.Column("completion_percent", sa.Float(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_lesson_progress"),
        sa.UniqueConstraint("student_id", "lesson_id", name="uq_lesson_progress_student_lesson"),
    )
    op.create_index("ix_lesson_progress_institution_id", "lesson_progress", ["institution_id"])
    op.create_index("ix_lesson_progress_student_id", "lesson_progress", ["student_id"])
    op.create_index("ix_lesson_progress_lesson_id", "lesson_progress", ["lesson_id"])


def downgrade() -> None:
    op.drop_index("ix_lesson_progress_lesson_id", table_name="lesson_progress")
    op.drop_index("ix_lesson_progress_student_id", table_name="lesson_progress")
    op.drop_index("ix_lesson_progress_institution_id", table_name="lesson_progress")
    op.drop_table("lesson_progress")
    op.drop_index("ix_video_events_lesson_id", table_name="video_events")
    op.drop_index("ix_video_events_student_id", table_name="video_events")
    op.drop_index("ix_video_events_institution_id", table_name="video_events")
    op.drop_table("video_events")
