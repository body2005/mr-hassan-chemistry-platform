"""Separate upload/indexing progress and identify processing attempts.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-14 14:00:00.000000
"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op


revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("knowledge_sources"):
        return

    existing_cols = {c["name"] for c in inspector.get_columns("knowledge_sources")}

    def _add(column):
        if column.name not in existing_cols:
            op.add_column("knowledge_sources", column)

    _add(sa.Column("upload_percent", sa.Integer(), nullable=False, server_default="100"))
    _add(sa.Column("indexing_percent", sa.Integer(), nullable=False, server_default="0"))
    _add(sa.Column("processing_generation", sa.Integer(), nullable=False, server_default="1"))
    _add(sa.Column("processing_attempt_id", sa.Uuid(), nullable=True))
    _add(sa.Column("active_task_id", sa.String(length=255), nullable=True))

    bind.execute(
        sa.text(
            "UPDATE knowledge_sources SET indexing_percent = progress_percent, upload_percent = 100"
        )
    )
    source_ids = bind.execute(sa.text("SELECT id FROM knowledge_sources")).scalars().all()
    for source_id in source_ids:
        bind.execute(
            sa.text(
                "UPDATE knowledge_sources SET processing_attempt_id = :attempt_id WHERE id = :source_id"
            ),
            {"attempt_id": str(uuid.uuid4()), "source_id": str(source_id)},
        )
    # SQLite cannot ALTER COLUMN in place; batch mode rebuilds the table.
    with op.batch_alter_table("knowledge_sources") as batch_op:
        batch_op.alter_column(
            "processing_attempt_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )


def downgrade() -> None:
    op.drop_column("knowledge_sources", "active_task_id")
    op.drop_column("knowledge_sources", "processing_attempt_id")
    op.drop_column("knowledge_sources", "processing_generation")
    op.drop_column("knowledge_sources", "indexing_percent")
    op.drop_column("knowledge_sources", "upload_percent")
