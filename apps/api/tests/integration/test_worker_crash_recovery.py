"""Real Celery late-ack recovery using a QA-only probe, NOT the removed indexer."""
import os
import uuid
import redis
from celery import Celery
from .live_helpers import BASE, container, session, wait_until


def test_worker_crash_and_recovery():
    worker = container("worker")
    store = redis.Redis.from_url(os.environ["REDIS_URL"])
    probe = uuid.uuid4().hex
    prefix = f"qa:probe:{probe}"
    client = Celery("qa", broker=os.environ["CELERY_BROKER_URL"], backend=os.environ["CELERY_RESULT_BACKEND"])
    client.conf.broker_transport_options = {"visibility_timeout": 10}
    with session() as teacher:
        task = client.send_task("qa.durable_probe", args=[probe], queue="analytics")
        wait_until(lambda: store.exists(f"{prefix}:starts"), 30)
        try:
            worker.kill()
            worker.stop(timeout=1)
            assert teacher.get(f"{BASE}/health", timeout=10).status_code == 200
            assert teacher.get(f"{BASE}/courses", timeout=10).status_code == 200
        finally:
            worker.start()
        # Kombu's Redis QoS restore sweep is ~90s, independent of the 10s
        # visibility timeout; allow the sweep plus the real 20s task runtime.
        wait_until(lambda: store.exists(f"{prefix}:completed"), 160)
        assert task.get(timeout=10) == "completed"
        assert int(store.get(f"{prefix}:starts")) >= 2
        assert store.get(f"{prefix}:completed") == b"once"
        assert teacher.get(f"{BASE}/courses", timeout=10).status_code == 200
    store.delete(f"{prefix}:starts", f"{prefix}:completed")
