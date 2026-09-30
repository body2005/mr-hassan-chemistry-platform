"""Canonicalize knowledge-source roles without deleting source data.

Revision ID: c4d5e6f7a8b9
Revises: b1e2f3a4c5d6
Create Date: 2026-09-14 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b1e2f3a4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("knowledge_sources"):
        return

    # A legacy lesson_id only tells us where a source was used; it does not
    # prove that the file was a lesson attachment.  Classifying every such row
    # as LESSON_MATERIAL would silently remove historical course knowledge from
    # the Knowledge Center.  Keep KNOWLEDGE and REFERENCE course-scoped, and
    # only migrate the semantically explicit TEACHER_NOTE role to a lesson
    # attachment when it is actually lesson-scoped.
    bind.execute(
        sa.text(
            """
            UPDATE knowledge_sources
               SET source_role = CASE
                   WHEN source_role = 'TEACHER_NOTE' AND lesson_id IS NOT NULL THEN 'LESSON_MATERIAL'
                   ELSE 'COURSE_KNOWLEDGE'
               END
             WHERE source_role IN ('KNOWLEDGE', 'REFERENCE', 'TEACHER_NOTE')
            """
        )
    )

    # SQLite cannot ALTER COLUMN in place; batch mode rebuilds the table.
    with op.batch_alter_table("knowledge_sources") as batch_op:
        batch_op.alter_column(
            "source_role",
            existing_type=sa.String(length=30),
            server_default="COURSE_KNOWLEDGE",
            existing_nullable=False,
        )


def downgrade() -> None:
    # Role canonicalization is intentionally forward-only: reversing it would
    # discard the newly explicit course-versus-lesson scope.
    pass
