"""Payment sender details and observable video processing progress."""
from alembic import op
import sqlalchemy as sa
revision = "a1c3e5f7b9d2"
down_revision = "f9e1b3d5a7c9"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("payment_orders", sa.Column("payer_name", sa.String(200), nullable=True))
    op.add_column("video_uploads", sa.Column("processing_percent", sa.Integer(), nullable=True))
    op.add_column("video_uploads", sa.Column("processing_stage", sa.String(80), nullable=True))

def downgrade():
    op.drop_column("video_uploads", "processing_stage")
    op.drop_column("video_uploads", "processing_percent")
    op.drop_column("payment_orders", "payer_name")
