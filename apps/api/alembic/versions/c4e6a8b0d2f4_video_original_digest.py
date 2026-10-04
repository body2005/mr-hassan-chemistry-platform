"""Retain a full original-content SHA-256 for future storage migrations."""
from alembic import op
import sqlalchemy as sa

revision = "c4e6a8b0d2f4"
down_revision = "b3d5f7a9c1e3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("video_uploads", sa.Column("sha256", sa.String(64)))


def downgrade():
    op.drop_column("video_uploads", "sha256")
