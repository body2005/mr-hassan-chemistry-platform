"""persist student registration fields

Revision ID: a9b0c1d2e3f4
Revises: e7f8a9b0c1d2, f1a2b3c4d5e6
Create Date: 2026-09-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a9b0c1d2e3f4"
down_revision: str | tuple[str, str] | None = ("e7f8a9b0c1d2", "f1a2b3c4d5e6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("student_phone", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("guardian_phone", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("national_id", sa.String(length=14), nullable=True))
    op.add_column("users", sa.Column("governorate", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("school_name", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("religion", sa.String(length=32), nullable=True))
    # A unique index is portable to SQLite and PostgreSQL and still permits
    # any number of legacy NULL values.
    op.create_index("uq_users_institution_national_id", "users", ["institution_id", "national_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_users_institution_national_id", table_name="users")
    op.drop_column("users", "religion")
    op.drop_column("users", "gender")
    op.drop_column("users", "school_name")
    op.drop_column("users", "governorate")
    op.drop_column("users", "national_id")
    op.drop_column("users", "guardian_phone")
    op.drop_column("users", "student_phone")
