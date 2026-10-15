"""Stage encrypted generations without enabling global DRM enforcement."""
from alembic import op
import sqlalchemy as sa

revision = 'd5f7a9b1c3e5'
down_revision = 'a1c3e5f7b9d2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('video_uploads', sa.Column('drm', sa.JSON(), nullable=True))
    op.add_column('lessons', sa.Column('video_drm_protected', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    # Removing the protection marker would re-open clear fallbacks. Require
    # an explicit, reviewed data migration rather than silently downgrading.
    raise RuntimeError('DRM protection cannot be downgraded automatically')
