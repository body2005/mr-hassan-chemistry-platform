"""Retain long lesson titles and original video filenames without truncation."""
from alembic import op
import sqlalchemy as sa

revision = "g8c0d2e4f6a8"
down_revision = "g7b9c1d3e5f7"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("lessons", "title", existing_type=sa.String(200), type_=sa.String(1000), existing_nullable=False)
    op.alter_column("video_uploads", "filename", existing_type=sa.String(200), type_=sa.String(1000), existing_nullable=False)
    # Scheduled lesson events and access notices also carry the full title.
    op.alter_column("calendar_events", "title", existing_type=sa.String(200), type_=sa.String(1000), existing_nullable=False)
    op.alter_column("notifications", "title", existing_type=sa.String(200), type_=sa.String(1200), existing_nullable=False)


def downgrade():
    # Never silently truncate names created after widening the columns.
    db = op.get_bind()
    for table, column in (("lessons", "title"), ("video_uploads", "filename"), ("calendar_events", "title"), ("notifications", "title")):
        if db.scalar(sa.text(f"SELECT COUNT(*) FROM {table} WHERE length({column}) > 200")):
            raise RuntimeError("Cannot narrow name columns while values longer than 200 characters exist")
    op.alter_column("notifications", "title", existing_type=sa.String(1200), type_=sa.String(200), existing_nullable=False)
    op.alter_column("calendar_events", "title", existing_type=sa.String(1000), type_=sa.String(200), existing_nullable=False)
    op.alter_column("video_uploads", "filename", existing_type=sa.String(1000), type_=sa.String(200), existing_nullable=False)
    op.alter_column("lessons", "title", existing_type=sa.String(1000), type_=sa.String(200), existing_nullable=False)
