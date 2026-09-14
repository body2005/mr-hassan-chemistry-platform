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

    # Historical KNOWLEDGE/REFERENCE rows were course-wide unless a lesson was
    # attached. Preserve every row and relationship while making its scope
    # explicit for the new authorization and retrieval rules.
    bind.execute(
        sa.text(
            """
            UPDATE knowledge_sources
               SET source_role = CASE
                   WHEN lesson_id IS NOT NULL THEN 'LESSON_MATERIAL'
                   ELSE 'COURSE_KNOWLEDGE'
               END
             WHERE source_role IN ('KNOWLEDGE', 'REFERENCE', 'TEACHER_NOTE')
            """
        )
    )

    op.alter_column(
        "knowledge_sources",
        "source_role",
        existing_type=sa.String(length=30),
        server_default="COURSE_KNOWLEDGE",
        existing_nullable=False,
    )


def downgrade() -> None:
    # Role canonicalization is intentionally forward-only: reversing it would
    # discard the newly explicit course-versus-lesson scope.
    pass
