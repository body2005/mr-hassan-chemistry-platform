"""Optional lesson closing time and publication notification preference."""
from alembic import op
import sqlalchemy as sa

revision = "f9e1b3d5a7c9"
down_revision = "f8d0a2c4e6b8"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("lessons", sa.Column("available_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_lessons_available_until", "lessons", ["available_until"])
    op.add_column("lessons", sa.Column("announce_to_students", sa.Boolean(), server_default=sa.true(), nullable=False))

def downgrade():
    op.drop_column("lessons", "announce_to_students")
    op.drop_index("ix_lessons_available_until", table_name="lessons")
    op.drop_column("lessons", "available_until")
