"""Durable cleanup outbox and manual quiz grading feedback."""
from alembic import op
import sqlalchemy as sa

revision = "a2c4e6f8b0d2"
down_revision = "f1b2c3d4e5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("storage_cleanup",
                    sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("object_key", sa.Text(), nullable=False),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("retry_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_storage_cleanup_retry_at", "storage_cleanup", ["retry_at"])
    op.add_column("quiz_attempt_answers", sa.Column("feedback", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("quiz_attempt_answers", "feedback")
    op.drop_index("ix_storage_cleanup_retry_at", table_name="storage_cleanup")
    op.drop_table("storage_cleanup")
