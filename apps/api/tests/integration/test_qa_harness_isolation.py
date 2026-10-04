"""Unit fixture maintenance cannot erase the real HTTPS app's rate windows."""
import os
import uuid
from urllib.parse import urlsplit

import redis

from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limits
from .live_helpers import isolated


def test_unit_rate_reset_preserves_live_rate_counter():
    isolated()
    # Fail BEFORE invoking destructive maintenance if isolation is incorrect.
    unit = urlsplit(get_settings().redis_url)
    live = urlsplit(os.environ["REDIS_URL"])
    assert unit.path == "/15" and live.path != "/15"
    store = redis.Redis.from_url(os.environ["REDIS_URL"])
    key = "rate-limit:qa-isolation:" + uuid.uuid4().hex
    try:
        store.set(key, "unchanged", ex=120)
        reset_rate_limits()
        assert store.get(key) == b"unchanged"
    finally:
        # Only this case's unique synthetic sentinel, never a user's counter.
        store.delete(key)
