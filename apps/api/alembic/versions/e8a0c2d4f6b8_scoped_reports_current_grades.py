"""Scoped report keys and a current-only grade ledger; preserve all history."""
from alembic import op
import sqlalchemy as sa

revision = "e8a0c2d4f6b8"
down_revision = "d5f7b9c1e3a5"
branch_labels = depends_on = None


def upgrade():
    # Reconcile nullable-key duplicates deterministically, without deleting a
    # grade. No new score is invented. Latest timestamp + UUID breaks ties.
    op.execute(sa.text("""UPDATE grades SET is_current = false WHERE id IN (
        SELECT id FROM (SELECT id, row_number() OVER (
            PARTITION BY institution_id, student_id, course_id, item_type, item_id
            ORDER BY updated_at DESC, id DESC) AS rn
            FROM grades WHERE is_current = true) ranked WHERE rn > 1)"""))
    op.drop_index("ix_grades_current", table_name="grades")
    op.create_index("ix_grades_current", "grades", ["institution_id", "student_id",
        sa.text("coalesce(CAST(course_id AS VARCHAR(36)), 'none')"), "item_type",
        sa.text("coalesce(CAST(item_id AS VARCHAR(36)), 'none')")], unique=True,
        postgresql_where=sa.text("is_current IS TRUE"), sqlite_where=sa.text("is_current IS TRUE"))
    constraints = sa.inspect(op.get_bind()).get_unique_constraints("report_jobs")
    with op.batch_alter_table("report_jobs") as batch:
        for constraint in constraints:
            if constraint["column_names"] == ["idempotency_key"]:
                batch.drop_constraint(constraint["name"], type_="unique")
        batch.create_unique_constraint("uq_report_requester_key", ["institution_id", "requested_by", "idempotency_key"])


def downgrade():
    # Restoring either old unique constraint can discard valid history or
    # scoped reports. Refuse a destructive rollback; use a reviewed backup.
    raise RuntimeError("This data-preserving ledger migration cannot be downgraded safely")
