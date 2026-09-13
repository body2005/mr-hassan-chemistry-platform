"""student payments and AI entitlements

Revision ID: a6b7c8d9e0f1
Revises: f5a9c3d7e1b2
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6b7c8d9e0f1"
down_revision: str | None = "f5a9c3d7e1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column("price_egp", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "lessons",
        sa.Column("price_egp", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )

    op.create_table(
        "payment_orders",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("product_type", sa.String(length=32), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("product_name", sa.String(length=240), nullable=False),
        sa.Column("amount_egp", sa.Numeric(10, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payer_reference", sa.String(length=160), nullable=True),
        sa.Column("receipt_path", sa.String(length=512), nullable=True),
        sa.Column("student_note", sa.Text(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("institution_id", "student_id", "product_type", "product_id", "status", "reviewed_by"):
        op.create_index(f"ix_payment_orders_{column}", "payment_orders", [column])

    op.create_table(
        "student_entitlements",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("source_order_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_order_id"], ["payment_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "institution_id",
        "student_id",
        "entitlement_type",
        "resource_id",
        "source_order_id",
        "expires_at",
        "revoked_at",
    ):
        op.create_index(f"ix_student_entitlements_{column}", "student_entitlements", [column])


def downgrade() -> None:
    op.drop_table("student_entitlements")
    op.drop_table("payment_orders")
    op.drop_column("lessons", "price_egp")
    op.drop_column("courses", "price_egp")
