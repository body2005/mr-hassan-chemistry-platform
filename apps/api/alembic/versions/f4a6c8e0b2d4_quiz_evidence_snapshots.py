"""Freeze assessment versions and weights; do not invent historical evidence."""
from alembic import op
import sqlalchemy as sa

revision = "f4a6c8e0b2d4"
down_revision = "f3e5a7c9b1d3"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("quiz_questions", "quiz_attempts", "quiz_attempt_answers"):
        op.add_column(table, sa.Column("question_snapshot", sa.JSON(), nullable=True))
    # Existing attempts deliberately remain NULL. Neither the current bank nor
    # the current exam link proves the content/weight used historically.


def downgrade():
    for table in ("quiz_attempt_answers", "quiz_attempts", "quiz_questions"):
        op.drop_column(table, "question_snapshot")
