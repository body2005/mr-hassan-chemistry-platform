"""Transactional encrypted reset mail outbox."""
from alembic import op
import sqlalchemy as sa

revision = "f2d4a6c8e0b2"
down_revision = "f1c3e5a7b9d1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("reset_mail_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_id", sa.Uuid(), sa.ForeignKey("password_reset_tokens.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("encrypted_token", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("retry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_reset_mail_outbox_retry_at", "reset_mail_outbox", ["retry_at"])


def downgrade():
    op.drop_table("reset_mail_outbox")
