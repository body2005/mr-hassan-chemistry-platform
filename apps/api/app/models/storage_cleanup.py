"""Durable storage deletion outbox; intentionally independent of lesson FKs."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class StorageCleanup(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "storage_cleanup"

    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True,
                                            default=lambda: datetime.now(timezone.utc))
