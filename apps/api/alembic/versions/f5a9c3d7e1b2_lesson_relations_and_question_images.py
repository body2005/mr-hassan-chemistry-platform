"""lesson relations and verified question images

Revision ID: f5a9c3d7e1b2
Revises: e4f8a2b6c3d4
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f5a9c3d7e1b2"
down_revision = "e4f8a2b6c3d4"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("knowledge_question_records", sa.Column("question_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("knowledge_question_records", sa.Column("metadata_json", sa.JSON(), nullable=True))
    op.add_column("questions", sa.Column("media_ids_json", sa.JSON(), nullable=True))

    op.create_table(
        "knowledge_lesson_relations",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("from_outline_node_id", sa.UUID(), nullable=False),
        sa.Column("to_outline_node_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_outline_node_id"], ["knowledge_outline_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_outline_node_id"], ["knowledge_outline_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_outline_node_id", "to_outline_node_id", "relation_type", name="uq_knowledge_lesson_relation"),
    )
    op.create_index("ix_knowledge_lesson_relations_source_id", "knowledge_lesson_relations", ["source_id"])
    op.create_index("ix_knowledge_lesson_relations_course_id", "knowledge_lesson_relations", ["course_id"])
    op.create_index("ix_knowledge_lesson_relations_from_outline_node_id", "knowledge_lesson_relations", ["from_outline_node_id"])
    op.create_index("ix_knowledge_lesson_relations_to_outline_node_id", "knowledge_lesson_relations", ["to_outline_node_id"])
    op.create_index("ix_knowledge_lesson_relations_source", "knowledge_lesson_relations", ["source_id", "relation_type"])

    op.create_table(
        "knowledge_question_image_links",
        sa.Column("question_record_id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["question_record_id"], ["knowledge_question_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["knowledge_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_record_id", "asset_id", name="uq_knowledge_question_image_link"),
    )
    op.create_index("ix_knowledge_question_image_links_question_record_id", "knowledge_question_image_links", ["question_record_id"])
    op.create_index("ix_knowledge_question_image_links_asset_id", "knowledge_question_image_links", ["asset_id"])
    op.create_index("ix_knowledge_question_image_links_question", "knowledge_question_image_links", ["question_record_id", "position"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_question_image_links_question", table_name="knowledge_question_image_links")
    op.drop_index("ix_knowledge_question_image_links_asset_id", table_name="knowledge_question_image_links")
    op.drop_index("ix_knowledge_question_image_links_question_record_id", table_name="knowledge_question_image_links")
    op.drop_table("knowledge_question_image_links")
    op.drop_index("ix_knowledge_lesson_relations_source", table_name="knowledge_lesson_relations")
    op.drop_index("ix_knowledge_lesson_relations_to_outline_node_id", table_name="knowledge_lesson_relations")
    op.drop_index("ix_knowledge_lesson_relations_from_outline_node_id", table_name="knowledge_lesson_relations")
    op.drop_index("ix_knowledge_lesson_relations_course_id", table_name="knowledge_lesson_relations")
    op.drop_index("ix_knowledge_lesson_relations_source_id", table_name="knowledge_lesson_relations")
    op.drop_table("knowledge_lesson_relations")
    op.drop_column("knowledge_question_records", "metadata_json")
    op.drop_column("knowledge_question_records", "question_order")
    op.drop_column("questions", "media_ids_json")
