"""Optional contact/education fields; preserve existing student accounts."""
from alembic import op
import sqlalchemy as sa

revision = 'f0b2d4e6a8c0'
down_revision = 'e8a0c2d4f6b8'
branch_labels = depends_on = None


def upgrade():
    for name, length in [('mother_phone', 20), ('city', 100),
                         ('education_division', 16), ('specialization', 16)]:
        op.add_column('users', sa.Column(name, sa.String(length), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch:
        for name in ['specialization', 'education_division', 'city', 'mother_phone']:
            batch.drop_column(name)
