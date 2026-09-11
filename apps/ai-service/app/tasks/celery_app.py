from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "lms_ai_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes maximum for batch tasks
    worker_prefetch_multiplier=1,
)
