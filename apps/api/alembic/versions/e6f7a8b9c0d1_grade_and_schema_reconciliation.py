"""Grade and schema reconciliation.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-16 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Add grade_level to users
    if inspector.has_table("users"):
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "grade_level" not in existing_cols:
            op.add_column("users", sa.Column("grade_level", sa.String(length=32), nullable=True))
            op.create_index("ix_users_grade_level", "users", ["grade_level"])

        if is_postgres:
            op.execute(
                sa.text(
                    "DO $$ BEGIN "
                    "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_grade_level') THEN "
                    "    ALTER TABLE users ADD CONSTRAINT ck_users_grade_level "
                    "    CHECK (grade_level IS NULL OR grade_level IN ('SECONDARY_1', 'SECONDARY_2', 'SECONDARY_3')) NOT VALID; "
                    "  END IF; "
                    "END $$;"
                )
            )

        # Ensure users.role is VARCHAR(32)
        role_col = next((c for c in inspector.get_columns("users") if c["name"] == "role"), None)
        if role_col and getattr(role_col.get("type"), "length", None) != 32:
            try:
                op.alter_column("users", "role", type_=sa.String(length=32), existing_type=role_col["type"])
            except Exception:
                pass

    # 2. Add grade_level to courses
    if inspector.has_table("courses"):
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "grade_level" not in existing_cols:
            op.add_column("courses", sa.Column("grade_level", sa.String(length=32), nullable=True))
            op.create_index("ix_courses_grade_level", "courses", ["grade_level"])

        if is_postgres:
            op.execute(
                sa.text(
                    "DO $$ BEGIN "
                    "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_courses_grade_level') THEN "
                    "    ALTER TABLE courses ADD CONSTRAINT ck_courses_grade_level "
                    "    CHECK (grade_level IS NULL OR grade_level IN ('SECONDARY_1', 'SECONDARY_2', 'SECONDARY_3')) NOT VALID; "
                    "  END IF; "
                    "END $$;"
                )
            )

    # 3. Add grade_level to knowledge_sources and reconcile course_id nullability
    if inspector.has_table("knowledge_sources"):
        existing_cols = {c["name"] for c in inspector.get_columns("knowledge_sources")}
        if "grade_level" not in existing_cols:
            op.add_column("knowledge_sources", sa.Column("grade_level", sa.String(length=32), nullable=True))
            op.create_index("ix_knowledge_sources_grade_level", "knowledge_sources", ["grade_level"])

        # Make course_id nullable for grade-level COURSE_KNOWLEDGE sources
        course_id_col = next((c for c in inspector.get_columns("knowledge_sources") if c["name"] == "course_id"), None)
        if course_id_col and not course_id_col.get("nullable", True):
            op.alter_column(
                "knowledge_sources",
                "course_id",
                existing_type=course_id_col.get("type", sa.Uuid()),
                nullable=True,
            )

        if is_postgres:
            op.execute(
                sa.text(
                    "DO $$ BEGIN "
                    "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_knowledge_sources_grade_level') THEN "
                    "    ALTER TABLE knowledge_sources ADD CONSTRAINT ck_knowledge_sources_grade_level "
                    "    CHECK (grade_level IS NULL OR grade_level IN ('SECONDARY_1', 'SECONDARY_2', 'SECONDARY_3')) NOT VALID; "
                    "  END IF; "
                    "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_knowledge_sources_lesson_material_scope') THEN "
                    "    ALTER TABLE knowledge_sources ADD CONSTRAINT ck_knowledge_sources_lesson_material_scope "
                    "    CHECK (source_role != 'LESSON_MATERIAL' OR (course_id IS NOT NULL AND lesson_id IS NOT NULL)) NOT VALID; "
                    "  END IF; "
                    "END $$;"
                )
            )

    for related_table in ["knowledge_outline_nodes", "knowledge_units_records", "knowledge_lesson_relations"]:
        if inspector.has_table(related_table):
            c_col = next((c for c in inspector.get_columns(related_table) if c["name"] == "course_id"), None)
            if c_col and not c_col.get("nullable", True):
                op.alter_column(
                    related_table,
                    "course_id",
                    existing_type=c_col.get("type", sa.Uuid()),
                    nullable=True,
                )

    # 4. Ensure CURRENT_TIMESTAMP defaults on created_at
    tables_to_check = [
        "idempotency_keys",
        "ai_runs",
        "risk_assessments",
        "question_versions",
    ]
    for tbl in tables_to_check:
        if inspector.has_table(tbl):
            cols = {c["name"]: c for c in inspector.get_columns(tbl)}
            if "created_at" in cols:
                col_info = cols["created_at"]
                if col_info.get("default") is None and is_postgres:
                    op.alter_column(
                        tbl,
                        "created_at",
                        server_default=sa.text("CURRENT_TIMESTAMP"),
                        existing_type=col_info["type"],
                    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade is explicitly rejected to prevent permanent data loss of educational records, "
        "grades, and schema reconciliation integrity."
    )
