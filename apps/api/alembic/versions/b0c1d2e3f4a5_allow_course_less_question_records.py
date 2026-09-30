"""Allow extracted knowledge questions without a course.

Grade-scoped knowledge-center uploads intentionally have no course. Their
questions remain tied to their source and page, but must not make ingestion
fail because an unrelated course UUID is unavailable.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot ALTER COLUMN in place; batch mode rebuilds the table.
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("knowledge_question_records") as batch_op:
            batch_op.alter_column("course_id", existing_type=sa.Uuid(), nullable=True)
    else:
        op.alter_column(
            "knowledge_question_records",
            "course_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )


def downgrade() -> None:
    op.execute("DELETE FROM knowledge_question_records WHERE course_id IS NULL")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("knowledge_question_records") as batch_op:
            batch_op.alter_column("course_id", existing_type=sa.Uuid(), nullable=False)
    else:
        op.alter_column(
            "knowledge_question_records",
            "course_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
