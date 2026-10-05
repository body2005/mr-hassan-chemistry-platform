"""Assignment start dates and retry-safe atomic quiz publication."""
from alembic import op
import sqlalchemy as sa

revision = "d5f7b9c1e3a5"
down_revision = "c4e6a8b0d2f4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("avatar_key", sa.String(512)))
    op.add_column("calendar_events", sa.Column("request_key", sa.String(100)))
    op.add_column("calendar_events", sa.Column("request_hash", sa.String(64)))
    op.create_unique_constraint("uq_calendar_request", "calendar_events", ["creator_id", "request_key"])
    op.add_column("assignments", sa.Column("starts_at", sa.DateTime(timezone=True)))
    op.add_column("quizzes", sa.Column("publication_key", sa.String(100)))
    op.add_column("quizzes", sa.Column("publication_hash", sa.String(64)))
    op.create_unique_constraint("uq_quiz_publication", "quizzes", ["creator_id", "publication_key"])


def downgrade():
    op.drop_column("users", "avatar_key")
    op.drop_constraint("uq_calendar_request", "calendar_events", type_="unique")
    op.drop_column("calendar_events", "request_hash")
    op.drop_column("calendar_events", "request_key")
    op.drop_constraint("uq_quiz_publication", "quizzes", type_="unique")
    op.drop_column("quizzes", "publication_hash")
    op.drop_column("quizzes", "publication_key")
    op.drop_column("assignments", "starts_at")
