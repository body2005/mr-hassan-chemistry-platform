"""auth foundation and password reset architecture

Revision ID: 9e1f6a9b2c3d
Revises: 7234e23ca8e5
Create Date: 2026-08-25 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e1f6a9b2c3d"
down_revision: str | None = "7234e23ca8e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The first schema used the ambiguous `admin` value. Preserve existing records
    # while moving them to the explicit institution-scoped role.
    op.execute("UPDATE users SET role = 'institution_admin' WHERE role = 'admin'")
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"], unique=False)
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_password_reset_tokens_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET role = 'admin' WHERE role IN ('institution_admin', 'platform_admin')"
    )
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "deleted_at")
