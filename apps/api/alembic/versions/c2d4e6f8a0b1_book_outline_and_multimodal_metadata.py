"""book outline and multimodal metadata

Revision ID: c2d4e6f8a0b1
Revises: 8c1b7d3e4f20
Create Date: 2026-09-08 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c2d4e6f8a0b1"
down_revision = "8c1b7d3e4f20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_outline_nodes",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("node_kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("heading_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_page", sa.Integer(), nullable=True),
        sa.Column("end_page", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["knowledge_outline_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_outline_nodes_source_id", "knowledge_outline_nodes", ["source_id"])
    op.create_index("ix_knowledge_outline_nodes_course_id", "knowledge_outline_nodes", ["course_id"])
    op.create_index("ix_knowledge_outline_nodes_parent_id", "knowledge_outline_nodes", ["parent_id"])
    op.create_index("ix_knowledge_outline_source_position", "knowledge_outline_nodes", ["source_id", "position"])
    op.create_index("ix_knowledge_outline_course_kind", "knowledge_outline_nodes", ["course_id", "node_kind"])

    for table in ("knowledge_assets", "knowledge_units_records", "knowledge_question_records", "assessment_questions"):
        op.add_column(table, sa.Column("outline_node_id", sa.UUID(), nullable=True))
        op.create_index(f"ix_{table}_outline_node_id", table, ["outline_node_id"])
        constraint_name = f"fk_{table}_outline_node"
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table(table) as batch_op:
                batch_op.create_foreign_key(
                    constraint_name,
                    "knowledge_outline_nodes",
                    ["outline_node_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        else:
            op.create_foreign_key(
                constraint_name,
                table,
                "knowledge_outline_nodes",
                ["outline_node_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    for table in ("assessment_questions", "knowledge_question_records", "knowledge_units_records", "knowledge_assets"):
        constraint_name = f"fk_{table}_outline_node"
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_constraint(constraint_name, type_="foreignkey")
        else:
            op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.drop_index(f"ix_{table}_outline_node_id", table_name=table)
        op.drop_column(table, "outline_node_id")

    op.drop_index("ix_knowledge_outline_course_kind", table_name="knowledge_outline_nodes")
    op.drop_index("ix_knowledge_outline_source_position", table_name="knowledge_outline_nodes")
    op.drop_index("ix_knowledge_outline_nodes_parent_id", table_name="knowledge_outline_nodes")
    op.drop_index("ix_knowledge_outline_nodes_course_id", table_name="knowledge_outline_nodes")
    op.drop_index("ix_knowledge_outline_nodes_source_id", table_name="knowledge_outline_nodes")
    op.drop_table("knowledge_outline_nodes")
