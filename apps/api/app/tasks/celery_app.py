from __future__ import annotations

import os

from celery import Celery

celery_app = Celery(
    "knowledge_center",
    broker=os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/1")),
    backend=os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/2")),
    include=["app.tasks.knowledge_ingestion"],
)
visibility_timeout = int(os.getenv("CELERY_VISIBILITY_TIMEOUT", "30"))
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": visibility_timeout},
)
