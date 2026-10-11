"""Multiple lesson and unit links for assessments.

Revision ID: f6b8d0e2a4c6
Revises: f4a6c8e0b2d4
"""
from alembic import op
import sqlalchemy as sa

revision = "f6b8d0e2a4c6"
down_revision = "f4a6c8e0b2d4"
branch_labels = None
depends_on = None


def upgrade():
    for kind, parent in (("quiz", "quizzes"), ("assignment", "assignments")):
        for scope, target in (("lesson", "lessons"), ("module", "course_modules")):
            name = f"{kind}_{scope}_links"
            op.create_table(name,
                sa.Column("assessment_id", sa.Uuid(), sa.ForeignKey(f"{parent}.id", ondelete="CASCADE"), primary_key=True),
                sa.Column(f"{scope}_id", sa.Uuid(), sa.ForeignKey(f"{target}.id", ondelete="CASCADE"), primary_key=True))
            # Older editors sent a lesson and its parent module together. Preserve
            # that lesson-only scope instead of expanding it to every paid lesson.
            condition = " AND lesson_id IS NULL" if scope == "module" else ""
            op.execute(sa.text(f"INSERT INTO {name} (assessment_id, {scope}_id) SELECT id, {scope}_id FROM {parent} WHERE {scope}_id IS NOT NULL{condition}"))


def downgrade():
    for kind in ("assignment", "quiz"):
        for scope in ("module", "lesson"):
            op.drop_table(f"{kind}_{scope}_links")
