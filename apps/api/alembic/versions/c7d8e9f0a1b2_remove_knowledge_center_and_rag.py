"""Remove AI Knowledge Center, RAG, embeddings, and indexing infrastructure.

Drops every table that exclusively served the Knowledge Center, the RAG
pipeline, Qdrant-backed vectors, or AI answer generation, and renames the
lesson columns that previously tracked AI "indexing" so the remaining
vocabulary describes transcript materialization only.

Kept: quizzes/assignments/questions, lesson transcripts and segments,
lesson_assets (materials), and all extraction staging tables.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c7d8e9f0a1b2"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None

# Tables that served ONLY the Knowledge Center / RAG / AI answering /
# AI indexing. Nothing in the kept extraction path references them.
# Drop order matters: children (and tables whose FKs point at other dropped
# tables) must go before the tables they reference.
_KC_TABLES = [
    "knowledge_question_image_links",
    "assessment_question_usages",
    "knowledge_concept_relations",
    "knowledge_concept_links",
    "knowledge_query_events",
    "knowledge_conversation_turns",
    "knowledge_assets",
    "knowledge_units_records",
    "knowledge_question_records",
    "knowledge_lesson_relations",
    "knowledge_concepts",
    "knowledge_documents",
    "assessment_questions",
    "knowledge_outline_nodes",
    "assessment_sources",
    "knowledge_chunks",
    "knowledge_sources",
]


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _column_exists(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return column in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Drop RAG-only columns on lessons.
    if _column_exists(bind, "lessons", "rag_synced"):
        op.drop_column("lessons", "rag_synced")
    if _column_exists(bind, "lessons", "indexed_chunks_count"):
        op.drop_column("lessons", "indexed_chunks_count")

    # 2) Rename AI-indexing columns to materialization (transcript pipeline).
    if _column_exists(bind, "lessons", "indexing_status"):
        op.alter_column(
            "lessons",
            "indexing_status",
            new_column_name="materialization_status",
            existing_type=sa.String(length=32),
            existing_nullable=False,
        )
    if _column_exists(bind, "lessons", "indexing_error"):
        op.alter_column(
            "lessons",
            "indexing_error",
            new_column_name="materialization_error",
            existing_type=sa.Text(),
            existing_nullable=True,
        )

    # 3) Drop the Knowledge Center world, children first.
    for table in _KC_TABLES:
        if _table_exists(bind, table):
            op.drop_table(table)


def downgrade() -> None:
    bind = op.get_bind()

    # Restore lesson columns first so dropped FK targets exist again.
    if not _column_exists(bind, "lessons", "indexing_status"):
        op.add_column(
            "lessons",
            sa.Column(
                "indexing_status",
                sa.String(length=32),
                nullable=False,
                server_default="NOT_INDEXED",
            ),
        )
    if not _column_exists(bind, "lessons", "indexing_error"):
        op.add_column(
            "lessons",
            sa.Column("indexing_error", sa.Text(), nullable=True),
        )
    if _column_exists(bind, "lessons", "materialization_status"):
        op.drop_column("lessons", "materialization_status")
    if _column_exists(bind, "lessons", "materialization_error"):
        op.drop_column("lessons", "materialization_error")
    if not _column_exists(bind, "lessons", "rag_synced"):
        op.add_column(
            "lessons",
            sa.Column("rag_synced", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _column_exists(bind, "lessons", "indexed_chunks_count"):
        op.add_column(
            "lessons",
            sa.Column("indexed_chunks_count", sa.Integer(), nullable=False, server_default="0"),
        )

    # Recreate knowledge_sources minimally (enough for FKs to resolve).
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("institution_id", sa.String(length=36), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(length=36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=True),
        sa.Column("lesson_id", sa.String(length=36), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=True),
        sa.Column("uploaded_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_role", sa.String(length=32), nullable=False),
        sa.Column("source_status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_sources_institution", "knowledge_sources", ["institution_id"])
    op.create_index("ix_knowledge_sources_course", "knowledge_sources", ["course_id"])

    # Recreate assessment tables (question-bank containers) with real FKs.
    op.create_table(
        "assessment_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_id", sa.String(length=36), sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_type", sa.String(length=30), nullable=False, server_default="quiz"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_status", sa.String(length=30), nullable=False, server_default="resolving"),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="needs_review"),
        sa.Column("answer_key_source_id", sa.String(length=36), sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "assessment_questions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("assessment_source_id", sa.String(length=36), sa.ForeignKey("assessment_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(length=36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.String(length=36), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=30), nullable=False, server_default="multiple_choice"),
        sa.Column("difficulty", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("learning_objective", sa.String(length=100), nullable=False, server_default="understanding"),
        sa.Column("topic_concept", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("points", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("source_kind", sa.String(length=30), nullable=False, server_default="extracted_question"),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("answer_source", sa.String(length=40), nullable=True),
        sa.Column("answer_status", sa.String(length=40), nullable=True, server_default="needs_review"),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.Column("normalized_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("semantic_fingerprint", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="needs_review"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_assessment_questions_source", "assessment_questions", ["assessment_source_id"])
    op.create_index("ix_assessment_questions_course", "assessment_questions", ["course_id"])
    op.create_table(
        "assessment_question_usages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("question_id", sa.String(length=36), sa.ForeignKey("assessment_questions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quiz_id", sa.String(length=36), sa.ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignment_id", sa.String(length=36), sa.ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_id", sa.String(length=36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.String(length=36), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=True),
        sa.Column("usage_context", sa.String(length=50), nullable=False, server_default="quiz_generation"),
        sa.Column("used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # knowledge_chunks used to hang off transcripts.
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("transcript_id", sa.String(length=36), sa.ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.String(length=36), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=True),
        sa.Column("course_id", sa.String(length=36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("transcript_id", "sequence", name="uq_knowledge_chunks_seq"),
    )
