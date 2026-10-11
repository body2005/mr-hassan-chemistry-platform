"""Require teacher release for official quiz results, preserving all old scores.

Revision ID: f7c9e1a3b5d7
Revises: f6b8d0e2a4c6
"""
from alembic import op
import sqlalchemy as sa

revision = "f7c9e1a3b5d7"
down_revision = "f6b8d0e2a4c6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("quiz_attempts", sa.Column("results_approved_at", sa.DateTime(timezone=True)))
    op.add_column("quiz_attempts", sa.Column("results_approved_by", sa.Uuid()))
    with op.batch_alter_table("quiz_attempts") as batch:
        batch.create_foreign_key("fk_quiz_result_approver", "users", ["results_approved_by"], ["id"], ondelete="SET NULL")


def downgrade():
    with op.batch_alter_table("quiz_attempts") as batch:
        batch.drop_constraint("fk_quiz_result_approver", type_="foreignkey")
        batch.drop_column("results_approved_by")
        batch.drop_column("results_approved_at")
