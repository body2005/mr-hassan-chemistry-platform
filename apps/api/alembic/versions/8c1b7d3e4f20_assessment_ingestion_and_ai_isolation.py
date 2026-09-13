"""assessment ingestion and ai isolation

Revision ID: 8c1b7d3e4f20
Revises: f03ae2a24ae2
Create Date: 2026-09-08 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "8c1b7d3e4f20"
down_revision = "f03ae2a24ae2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_units_records", sa.Column("embedding_json", sa.JSON(), nullable=True))
    op.add_column("assessment_sources", sa.Column("processing_status", sa.String(length=30), nullable=False, server_default="resolving"))
    op.add_column("assessment_sources", sa.Column("review_status", sa.String(length=30), nullable=False, server_default="needs_review"))
    op.add_column("assessment_sources", sa.Column("answer_key_source_id", sa.UUID(), nullable=True))
    op.create_index("ix_assessment_sources_answer_key_source_id", "assessment_sources", ["answer_key_source_id"])
    foreign_key_args = (
        "fk_assessment_sources_answer_key_source_id_knowledge_sources",
        "knowledge_sources",
        ["answer_key_source_id"],
        ["id"],
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("assessment_sources") as batch_op:
            batch_op.create_foreign_key(*foreign_key_args, ondelete="SET NULL")
    else:
        op.create_foreign_key(
            foreign_key_args[0],
            "assessment_sources",
            foreign_key_args[1],
            foreign_key_args[2],
            foreign_key_args[3],
            ondelete="SET NULL",
        )

    op.add_column("assessment_questions", sa.Column("points", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("assessment_questions", sa.Column("source_kind", sa.String(length=30), nullable=False, server_default="extracted_question"))
    op.add_column("assessment_questions", sa.Column("answer_source", sa.String(length=40), nullable=True))
    op.add_column("assessment_questions", sa.Column("answer_status", sa.String(length=40), nullable=False, server_default="needs_review"))
    op.add_column("assessment_questions", sa.Column("answer_provenance_json", sa.JSON(), nullable=True))
    op.add_column("assessment_questions", sa.Column("source_pages_json", sa.JSON(), nullable=True))
    op.add_column("assessment_questions", sa.Column("rubric_json", sa.JSON(), nullable=True))
    op.add_column("assessment_questions", sa.Column("review_status", sa.String(length=30), nullable=False, server_default="needs_review"))

    op.create_table(
        "assignment_attempts",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "student_id", "attempt_number", name="uq_assignment_attempt_number"),
    )
    op.create_index("ix_assignment_attempts_assignment_id", "assignment_attempts", ["assignment_id"])
    op.create_index("ix_assignment_attempts_institution_id", "assignment_attempts", ["institution_id"])
    op.create_index("ix_assignment_attempts_student_id", "assignment_attempts", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_assignment_attempts_student_id", table_name="assignment_attempts")
    op.drop_index("ix_assignment_attempts_institution_id", table_name="assignment_attempts")
    op.drop_index("ix_assignment_attempts_assignment_id", table_name="assignment_attempts")
    op.drop_table("assignment_attempts")

    for column in [
        "review_status",
        "rubric_json",
        "source_pages_json",
        "answer_provenance_json",
        "answer_status",
        "answer_source",
        "source_kind",
        "points",
    ]:
        op.drop_column("assessment_questions", column)

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("assessment_sources") as batch_op:
            batch_op.drop_constraint(
                "fk_assessment_sources_answer_key_source_id_knowledge_sources",
                type_="foreignkey",
            )
    else:
        op.drop_constraint("fk_assessment_sources_answer_key_source_id_knowledge_sources", "assessment_sources", type_="foreignkey")
    op.drop_index("ix_assessment_sources_answer_key_source_id", table_name="assessment_sources")
    for column in ["answer_key_source_id", "review_status", "processing_status"]:
        op.drop_column("assessment_sources", column)

    op.drop_column("knowledge_units_records", "embedding_json")
