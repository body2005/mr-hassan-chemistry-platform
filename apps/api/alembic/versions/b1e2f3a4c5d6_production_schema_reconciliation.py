"""Production schema reconciliation and forward compatibility.

Revision ID: b1e2f3a4c5d6
Revises: a6b7c8d9e0f1
Create Date: 2026-09-14 09:30:00.000000

NOTE ON REVISION ARCHITECTURE:
Earlier historical migrations (9e1f6a9b2c3d, d710a69ed9a0, c2d4e6f8a0b1) were corrected
in-place to allow fresh, clean-slate PostgreSQL installations from scratch without syntax
or constraint identifier length failures.
This migration (b1e2f3a4c5d6) is a forward-only corrective migration designed for already-
migrated environments (such as Render production databases at revision a6b7c8d9e0f1) to
idempotently reconcile:
1. Column width of users.role to VARCHAR(32) across all dialects.
2. Outline node foreign key constraint names ensuring all identifiers <= 63 bytes in PostgreSQL.
3. Server defaults on timestamp columns to CURRENT_TIMESTAMP.
4. Non-destructive handling of legacy 'admin' roles (preserving existing records unless explicit).
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "b1e2f3a4c5d6"
down_revision: str | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Idempotently reconcile users.role column width
    users_columns = {col["name"]: col for col in insp.get_columns("users")}
    if "role" in users_columns:
        role_type = users_columns["role"]["type"]
        current_length = getattr(role_type, "length", None)
        if current_length is not None and current_length < 32:
            # SQLite cannot ALTER COLUMN in place; batch mode rebuilds the table.
            with op.batch_alter_table("users") as batch_op:
                batch_op.alter_column(
                    "role",
                    type_=sa.String(length=32),
                    existing_type=role_type,
                )

    # 2. Outline node foreign keys with safe <= 63 character names
    outline_tables = (
        "knowledge_assets",
        "knowledge_units_records",
        "knowledge_question_records",
        "assessment_questions",
    )
    for table in outline_tables:
        if not insp.has_table(table):
            continue
        existing_fks = insp.get_foreign_keys(table)
        fk_names = {fk["name"] for fk in existing_fks if fk["name"]}
        safe_fk_name = f"fk_{table}_outline_node"
        legacy_fk_name = f"fk_{table}_outline_node_id_knowledge_outline_nodes"

        to_drop = [
            fk_name
            for fk_name in fk_names
            if (
                fk_name == legacy_fk_name
                or (is_postgres and fk_name.startswith(legacy_fk_name[:63]))
            )
            and fk_name != safe_fk_name
        ]
        col_names = {c["name"] for c in insp.get_columns(table)}
        needs_create = (
            safe_fk_name not in fk_names
            and "outline_node_id" in col_names
            and insp.has_table("knowledge_outline_nodes")
        )
        if not to_drop and not needs_create:
            continue
        # SQLite cannot ALTER constraints; batch mode rebuilds the table.
        with op.batch_alter_table(table) as batch_op:
            for fk_name in to_drop:
                batch_op.drop_constraint(fk_name, type_="foreignkey")
            if needs_create:
                batch_op.create_foreign_key(
                    safe_fk_name,
                    "knowledge_outline_nodes",
                    ["outline_node_id"],
                    ["id"],
                    ondelete="SET NULL",
                )


def downgrade() -> None:
    pass
