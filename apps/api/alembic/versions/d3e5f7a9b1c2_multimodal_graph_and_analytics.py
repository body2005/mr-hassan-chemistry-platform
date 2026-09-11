"""multimodal graph and retrieval analytics

Revision ID: d3e5f7a9b1c2
Revises: c2d4e6f8a0b1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d3e5f7a9b1c2"
down_revision = "c2d4e6f8a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_concepts",
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("normalized_label", sa.String(300), nullable=False),
        sa.Column("concept_type", sa.String(40), nullable=False, server_default="concept"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "normalized_label", name="uq_knowledge_concepts_course_label"),
    )
    op.create_index("ix_knowledge_concepts_course_id", "knowledge_concepts", ["course_id"])
    op.create_index("ix_knowledge_concepts_course_label", "knowledge_concepts", ["course_id", "label"])

    op.create_table(
        "knowledge_concept_links",
        sa.Column("concept_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id", "entity_type", "entity_id", name="uq_knowledge_concept_link"),
    )
    op.create_index("ix_knowledge_concept_links_concept_id", "knowledge_concept_links", ["concept_id"])
    op.create_index("ix_knowledge_concept_links_entity_id", "knowledge_concept_links", ["entity_id"])
    op.create_index("ix_knowledge_concept_links_entity", "knowledge_concept_links", ["entity_type", "entity_id"])
    op.create_index("ix_knowledge_concept_links_source_id", "knowledge_concept_links", ["source_id"])

    op.create_table(
        "knowledge_concept_relations",
        sa.Column("from_concept_id", sa.UUID(), nullable=False),
        sa.Column("to_concept_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("relation_type", sa.String(50), nullable=False, server_default="related_to"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("evidence_unit_ids_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["from_concept_id"], ["knowledge_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_concept_id"], ["knowledge_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_concept_id", "to_concept_id", "source_id", "relation_type", name="uq_knowledge_concept_relation"),
    )
    op.create_index("ix_knowledge_concept_relations_from_concept_id", "knowledge_concept_relations", ["from_concept_id"])
    op.create_index("ix_knowledge_concept_relations_to_concept_id", "knowledge_concept_relations", ["to_concept_id"])
    op.create_index("ix_knowledge_concept_relations_source_id", "knowledge_concept_relations", ["source_id"])

    op.create_table(
        "knowledge_query_events",
        sa.Column("institution_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=True),
        sa.Column("outline_node_id", sa.UUID(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["outline_node_id"], ["knowledge_outline_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("institution_id", "user_id", "course_id", "lesson_id", "outline_node_id"):
        op.create_index(f"ix_knowledge_query_events_{column}", "knowledge_query_events", [column])
    op.create_index("ix_knowledge_query_events_course_created", "knowledge_query_events", ["course_id", "created_at"])
    op.create_index("ix_knowledge_query_events_outline", "knowledge_query_events", ["outline_node_id"])

    op.create_table(
        "knowledge_conversation_turns",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.String(120), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("retrieved_unit_ids_json", sa.JSON(), nullable=True),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_conversation_turns_user_id", "knowledge_conversation_turns", ["user_id"])
    op.create_index("ix_knowledge_conversation_turns_course_id", "knowledge_conversation_turns", ["course_id"])
    op.create_index("ix_knowledge_conversation_session", "knowledge_conversation_turns", ["user_id", "course_id", "session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_conversation_session", table_name="knowledge_conversation_turns")
    op.drop_index("ix_knowledge_conversation_turns_course_id", table_name="knowledge_conversation_turns")
    op.drop_index("ix_knowledge_conversation_turns_user_id", table_name="knowledge_conversation_turns")
    op.drop_table("knowledge_conversation_turns")
    op.drop_index("ix_knowledge_query_events_outline", table_name="knowledge_query_events")
    op.drop_index("ix_knowledge_query_events_course_created", table_name="knowledge_query_events")
    for column in ("outline_node_id", "lesson_id", "course_id", "user_id", "institution_id"):
        op.drop_index(f"ix_knowledge_query_events_{column}", table_name="knowledge_query_events")
    op.drop_table("knowledge_query_events")
    op.drop_index("ix_knowledge_concept_relations_to_concept_id", table_name="knowledge_concept_relations")
    op.drop_index("ix_knowledge_concept_relations_source_id", table_name="knowledge_concept_relations")
    op.drop_index("ix_knowledge_concept_relations_from_concept_id", table_name="knowledge_concept_relations")
    op.drop_table("knowledge_concept_relations")
    for index in ("ix_knowledge_concept_links_source_id", "ix_knowledge_concept_links_entity", "ix_knowledge_concept_links_entity_id", "ix_knowledge_concept_links_concept_id"):
        op.drop_index(index, table_name="knowledge_concept_links")
    op.drop_table("knowledge_concept_links")
    op.drop_index("ix_knowledge_concepts_course_label", table_name="knowledge_concepts")
    op.drop_index("ix_knowledge_concepts_course_id", table_name="knowledge_concepts")
    op.drop_table("knowledge_concepts")
