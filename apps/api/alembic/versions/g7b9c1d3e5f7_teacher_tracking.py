"""Add private teacher tracking without changing existing tables or data.

Revision ID: g7b9c1d3e5f7
Revises: f6a8b0c2d4e6
"""

import sqlalchemy as sa

from alembic import op

revision = "g7b9c1d3e5f7"
down_revision = "f6a8b0c2d4e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "teacher_tracking_columns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "institution_id",
            sa.Uuid(),
            sa.ForeignKey("institutions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "teacher_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("data_type", sa.String(16), nullable=False),
        sa.Column("table_context", sa.String(16), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("id", "institution_id", "teacher_id", name="uq_tracking_column_scope"),
    )
    op.create_index(
        "ix_teacher_tracking_columns_institution_id", "teacher_tracking_columns", ["institution_id"]
    )
    op.create_index(
        "ix_teacher_tracking_columns_teacher_id", "teacher_tracking_columns", ["teacher_id"]
    )
    op.create_table(
        "teacher_tracking_values",
        sa.Column("column_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["column_id", "institution_id", "teacher_id"],
            [
                "teacher_tracking_columns.id",
                "teacher_tracking_columns.institution_id",
                "teacher_tracking_columns.teacher_id",
            ],
            ondelete="CASCADE",
            name="fk_tracking_value_scope",
        ),
    )
    op.create_index(
        "ix_teacher_tracking_values_institution_id", "teacher_tracking_values", ["institution_id"]
    )
    op.create_index(
        "ix_teacher_tracking_values_teacher_id", "teacher_tracking_values", ["teacher_id"]
    )


def downgrade():
    # Code rollback retains private teacher records. Destructive removal needs
    # a separate reviewed retention operation; no existing/user data is dropped.
    raise RuntimeError(
        "Teacher tracking contains user data: rollback application code only, "
        "retain this migration and schema head"
    )
