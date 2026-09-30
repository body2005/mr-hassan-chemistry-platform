"""QA-only durable probe; NOT a replacement for the removed knowledge indexer."""
import os
import time

import redis
from app.tasks.celery_app import celery_app

if os.getenv("QA_ISOLATED") != "true":
    raise RuntimeError("Worker probe may only be loaded in isolated QA")


@celery_app.task(name="qa.durable_probe")
def durable_probe(probe_id: str):
    store = redis.Redis.from_url(os.environ["REDIS_URL"])
    store.incr(f"qa:probe:{probe_id}:starts")
    time.sleep(20)
    # A recovered delivery must not duplicate the durable effect.
    store.set(f"qa:probe:{probe_id}:completed", b"once", nx=True)
    return "completed"
