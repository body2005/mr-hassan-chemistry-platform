"""Add lesson/module scoping to quizzes and assignments.

Quizzes and assignments can now be attached to a unit (course_modules) and
optionally to a single lesson, so students see them inside the lesson they
were uploaded for. Nullable everywhere: legacy rows keep working untethered.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("quizzes") as batch:
        batch.add_column(
            sa.Column("module_id", sa.Uuid(), sa.ForeignKey("course_modules.id", ondelete="SET NULL"), nullable=True)
        )
        batch.add_column(
            sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True)
        )
        batch.create_index("ix_quizzes_module_id", ["module_id"])
        batch.create_index("ix_quizzes_lesson_id", ["lesson_id"])

    with op.batch_alter_table("assignments") as batch:
        batch.add_column(
            sa.Column("module_id", sa.Uuid(), sa.ForeignKey("course_modules.id", ondelete="SET NULL"), nullable=True)
        )
        batch.add_column(
            sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True)
        )
        batch.create_index("ix_assignments_module_id", ["module_id"])
        batch.create_index("ix_assignments_lesson_id", ["lesson_id"])


def downgrade() -> None:
    with op.batch_alter_table("assignments") as batch:
        batch.drop_index("ix_assignments_lesson_id")
        batch.drop_index("ix_assignments_module_id")
        batch.drop_column("lesson_id")
        batch.drop_column("module_id")

    with op.batch_alter_table("quizzes") as batch:
        batch.drop_index("ix_quizzes_lesson_id")
        batch.drop_index("ix_quizzes_module_id")
        batch.drop_column("lesson_id")
        batch.drop_column("module_id")
