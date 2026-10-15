"""Global operations state, readable only through the platform-admin monitor."""
from datetime import datetime
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class VideoWorkerHeartbeat(Base):
    __tablename__ = 'video_worker_heartbeats'
    worker_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
