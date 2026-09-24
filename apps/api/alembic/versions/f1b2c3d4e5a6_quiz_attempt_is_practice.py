"""Add is_practice to quiz_attempts for self-training attempts.

Practice attempts let a student keep testing themselves after the official
attempt is consumed. They are graded for the student but are excluded from
every teacher-facing listing, gradebook and analytics aggregation.

Revision ID: f1b2c3d4e5a6
Revises: e0a1b2c3d4e5
"""

from alembic import op
import sqlalchemy as sa

revision = "f1b2c3d4e5a6"
down_revision = "e0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quiz_attempts",
        sa.Column(
            "is_practice",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Teacher-facing queries filter on this constantly.
    op.create_index(
        "ix_quiz_attempts_is_practice",
        "quiz_attempts",
        ["is_practice"],
    )
    op.add_column(
        "quizzes",
        sa.Column(
            "allow_practice_attempts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("quizzes", "allow_practice_attempts")
    op.drop_index("ix_quiz_attempts_is_practice", table_name="quiz_attempts")
    op.drop_column("quiz_attempts", "is_practice")
