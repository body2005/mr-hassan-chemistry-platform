"""Durable reset mail. Only encrypted credentials; never broker arguments."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDPrimaryKeyMixin


class ResetMailOutbox(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reset_mail_outbox"
    token_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("password_reset_tokens.id", ondelete="CASCADE"), unique=True, nullable=False)
    encrypted_token: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResetRequestOutbox(UUIDPrimaryKeyMixin, Base):
    """Uniform public admission; account lookup happens only in the consumer."""
    __tablename__ = "reset_request_outbox"
    __table_args__ = (Index("ix_reset_request_pending", "requested_at",
        postgresql_where=text("completed_at IS NULL"), sqlite_where=text("completed_at IS NULL")),)
    encrypted_identity: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
