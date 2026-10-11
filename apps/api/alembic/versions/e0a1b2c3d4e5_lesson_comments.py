"""Lesson comments for the standalone video-viewing page.

Adds `lesson_comments`: students discuss each lesson under its video.
Replies reference a parent comment (single level, Facebook style).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e0a1b2c3d4e5"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_comments",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institution_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "lesson_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "student_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "parent_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lesson_comments.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_lesson_comments_parent",
            "lesson_comments",
            "lesson_comments",
            ["parent_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("fk_lesson_comments_parent", "lesson_comments", type_="foreignkey")
    op.drop_table("lesson_comments")
