"""source edition current flag

Revision ID: e4f8a2b6c3d4
Revises: d3e5f7a9b1c2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "e4f8a2b6c3d4"
down_revision = "d3e5f7a9b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_sources", sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_knowledge_sources_is_current", "knowledge_sources", ["is_current"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_sources_is_current", table_name="knowledge_sources")
    op.drop_column("knowledge_sources", "is_current")
