"""Private worker heartbeat and bounded retry scheduling; no new service.

Revision ID: f6a8b0c2d4e6
Revises: d5f7a9b1c3e5
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'f6a8b0c2d4e6'
down_revision = 'd5f7a9b1c3e5'
branch_labels = None
depends_on = None


def upgrade():
    offline = context.is_offline_mode()
    if offline or 'retry_after' not in {column['name'] for column in sa.inspect(op.get_bind()).get_columns('video_uploads')}:
        op.add_column('video_uploads', sa.Column('retry_after', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_video_uploads_retry_after', 'video_uploads', ['retry_after'])
    if not offline and 'video_worker_heartbeats' in sa.inspect(op.get_bind()).get_table_names():
        # A code-only rollback intentionally retained this additive table.
        return
    op.create_table('video_worker_heartbeats',
        sa.Column('worker_id', sa.String(32), primary_key=True),
        sa.Column('seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False))
    op.create_index('ix_video_worker_heartbeats_seen_at', 'video_worker_heartbeats', ['seen_at'])


def downgrade():
    # Additive columns/history remain on code rollback. Removing them must
    # be a separately reviewed data-retention operation.
    pass
