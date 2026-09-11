from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_lock = threading.Lock()
_windows: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(request: Request, *, bucket: str, limit: int, window_seconds: int) -> None:
    """Bound abuse even when Redis is unavailable; Redis deployment can front this app too."""
    identity = request.client.host if request.client else "unknown"
    key = f"{bucket}:{identity}"
    now = time.monotonic()
    with _lock:
        entries = _windows[key]
        cutoff = now - window_seconds
        while entries and entries[0] <= cutoff:
            entries.popleft()
        if len(entries) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )
        entries.append(now)


def reset_rate_limits() -> None:
    """Clear in-process limiter state; intended for tests and controlled resets."""
    with _lock:
        _windows.clear()
