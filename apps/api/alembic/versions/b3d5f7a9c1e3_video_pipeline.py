"""Durable direct multipart video uploads and processing jobs."""
from alembic import op
import sqlalchemy as sa

revision = "b3d5f7a9c1e3"
down_revision = "a2c4e6f8b0d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("video_uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id", ondelete="SET NULL")),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(80), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("multipart_id", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("outputs", sa.JSON(), nullable=False),
        sa.Column("manifest_key", sa.String(512)),
        sa.Column("duration_seconds", sa.Integer()))
    for column in ("lesson_id", "owner_id", "request_key", "status"):
        op.create_index(f"ix_video_uploads_{column}", "video_uploads", [column])


def downgrade():
    op.drop_table("video_uploads")
