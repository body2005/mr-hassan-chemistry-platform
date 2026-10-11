"""Course-bound optional units, lesson publication, and final attempt grades."""
from alembic import op
import sqlalchemy as sa

revision = "f8d0a2c4e6b8"
down_revision = "f7c9e1a3b5d7"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("lessons", sa.Column("course_id", sa.Uuid(), nullable=True))
    op.execute(sa.text("UPDATE lessons SET course_id = (SELECT course_id FROM course_modules WHERE course_modules.id = lessons.module_id)"))
    with op.batch_alter_table("lessons") as batch:
        batch.alter_column("course_id", existing_type=sa.Uuid(), nullable=False)
        batch.create_foreign_key("fk_lessons_course_id", "courses", ["course_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_lessons_course_id", ["course_id"])
        batch.alter_column("module_id", existing_type=sa.Uuid(), nullable=True)
        batch.add_column(sa.Column("publication_status", sa.String(20), server_default="published", nullable=False))
        batch.add_column(sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("release_announced_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("release_checked_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_lessons_publish_at", ["publish_at"])
        batch.add_column(sa.Column("required_material_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("quiz_attempts", sa.Column("calculated_score", sa.Float(), nullable=True))
    op.add_column("quiz_attempts", sa.Column("final_percentage", sa.Float(), nullable=True))
    op.add_column("quiz_attempts", sa.Column("approval_notes", sa.Text(), nullable=True))
    op.execute(sa.text("UPDATE quiz_attempts SET calculated_score = score WHERE results_approved_at IS NOT NULL"))

def downgrade():
    # Never erase the course association of a lesson that has no unit.
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT COUNT(*) FROM lessons WHERE module_id IS NULL")):
        raise RuntimeError("Move unitless lessons into real units before downgrading")
    for column in ("approval_notes", "final_percentage", "calculated_score"):
        op.drop_column("quiz_attempts", column)
    with op.batch_alter_table("lessons") as batch:
        batch.drop_index("ix_lessons_publish_at")
        batch.drop_column("publish_at")
        batch.drop_column("release_announced_at")
        batch.drop_column("release_checked_at")
        batch.drop_column("publication_status")
        batch.drop_column("required_material_count")
        batch.alter_column("module_id", existing_type=sa.Uuid(), nullable=False)
        batch.drop_index("ix_lessons_course_id")
        batch.drop_constraint("fk_lessons_course_id", type_="foreignkey")
        batch.drop_column("course_id")
