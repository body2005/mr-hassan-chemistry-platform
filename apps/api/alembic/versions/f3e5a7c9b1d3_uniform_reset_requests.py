"""Uniform encrypted reset admission without account lookup in HTTP."""
from alembic import op
import sqlalchemy as sa

revision = "f3e5a7c9b1d3"
down_revision = "f2d4a6c8e0b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True)))
    op.create_table("reset_request_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("encrypted_identity", sa.Text()),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_reset_request_pending", "reset_request_outbox", ["requested_at"],
        postgresql_where=sa.text("completed_at IS NULL"),
        sqlite_where=sa.text("completed_at IS NULL"))
    op.create_index("ix_reset_request_outbox_expires_at", "reset_request_outbox", ["expires_at"])


def downgrade():
    op.drop_table("reset_request_outbox")
    op.drop_column("users", "password_changed_at")
