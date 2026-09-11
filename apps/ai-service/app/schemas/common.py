from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AsyncTaskResponse(BaseModel):
    task_id: str = Field(..., description="Unique Celery job ID")
    status: str = Field("queued", description="'queued' | 'in_progress' | 'completed' | 'failed'")
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ServiceHealthResponse(BaseModel):
    status: str
    environment: str
    version: str
    provider: Dict[str, Any]
    redis_connected: bool
