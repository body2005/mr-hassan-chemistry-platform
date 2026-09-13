from __future__ import annotations

import uuid
from datetime import datetime
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        pass

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_values


class PaymentProductType(StrEnum):
    COURSE = "course"
    LESSON = "lesson"
    AI_SUBSCRIPTION = "ai_subscription"


class PaymentMethod(StrEnum):
    INSTAPAY = "instapay"
    VODAFONE_CASH = "vodafone_cash"
    BANK_TRANSFER = "bank_transfer"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    PAID = "paid"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class EntitlementType(StrEnum):
    COURSE = "course"
    LESSON = "lesson"
    AI_GLOBAL = "ai_global"


class PaymentOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_orders"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_type: Mapped[PaymentProductType] = mapped_column(
        Enum(
            PaymentProductType,
            name="payment_product_type",
            native_enum=False,
            values_callable=enum_values,
        ),
        index=True,
        nullable=False,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    product_name: Mapped[str] = mapped_column(String(240), nullable=False)
    amount_egp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(
            PaymentMethod,
            name="payment_method",
            native_enum=False,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            values_callable=enum_values,
        ),
        default=PaymentStatus.PENDING,
        index=True,
        nullable=False,
    )
    payer_reference: Mapped[str | None] = mapped_column(String(160))
    receipt_path: Mapped[str | None] = mapped_column(String(512))
    student_note: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student = relationship("User", foreign_keys=[student_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class StudentEntitlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_entitlements"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entitlement_type: Mapped[EntitlementType] = mapped_column(
        Enum(
            EntitlementType,
            name="student_entitlement_type",
            native_enum=False,
            values_callable=enum_values,
        ),
        index=True,
        nullable=False,
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    source_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_orders.id", ondelete="SET NULL"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    student = relationship("User")
    source_order = relationship("PaymentOrder")
