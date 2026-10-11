"""Unique objective identity, preserving conflicting data for operator review.

Revision ID: f1c3e5a7b9d1
Revises: f0b2d4e6a8c0
"""
from alembic import op
import sqlalchemy as sa

revision = "f1c3e5a7b9d1"
down_revision = "f0b2d4e6a8c0"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    conflicts = bind.execute(sa.text("""
        SELECT institution_id, course_id, code, COUNT(*) AS n
        FROM learning_objectives GROUP BY institution_id, course_id, code
        HAVING COUNT(*) > 1
    """)).fetchall()
    if conflicts:
        # Never merge/delete rows, parent/mastery references or history.
        raise RuntimeError(
            f"Objective identity migration blocked: {len(conflicts)} duplicate scopes. "
            "Inventory learning_objectives GROUP BY institution_id, course_id, code "
            "HAVING COUNT(*) > 1; resolve with an approved data migration."
        )
    for name, columns, predicate in [
        ("uq_objective_scoped_code", ["institution_id", "course_id", "code"], "course_id IS NOT NULL"),
        ("uq_objective_global_code", ["institution_id", "code"], "course_id IS NULL"),
    ]:
        op.create_index(name, "learning_objectives", columns, unique=True,
                        postgresql_where=sa.text(predicate), sqlite_where=sa.text(predicate))


def downgrade():
    op.drop_index("uq_objective_global_code", table_name="learning_objectives")
    op.drop_index("uq_objective_scoped_code", table_name="learning_objectives")
