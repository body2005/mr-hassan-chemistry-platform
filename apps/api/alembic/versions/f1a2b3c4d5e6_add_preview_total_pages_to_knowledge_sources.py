"""Add preview_total_pages to knowledge_sources.

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-09-16 11:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("knowledge_sources"):
        existing_cols = {c["name"] for c in inspector.get_columns("knowledge_sources")}
        if "preview_total_pages" not in existing_cols:
            op.add_column("knowledge_sources", sa.Column("preview_total_pages", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("knowledge_sources"):
        existing_cols = {c["name"] for c in inspector.get_columns("knowledge_sources")}
        if "preview_total_pages" in existing_cols:
            op.drop_column("knowledge_sources", "preview_total_pages")
