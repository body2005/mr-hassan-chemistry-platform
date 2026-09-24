from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import HTTPException, Request, status

from app.core.rate_limit import resolve_client_ip
from app.core.security import decode_session_token

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# Per-client active in-flight request counts: key -> count
_active_per_client: dict[str, int] = defaultdict(int)
# Per-client active heavy request counts: key -> count
_active_heavy_per_client: dict[str, int] = defaultdict(int)
# Global heavy request count (protects database connection pool)
_global_heavy_count: int = 0

# Configurable limits
MAX_CONCURRENT_PER_CLIENT = int(os.getenv("MAX_CONCURRENT_PER_CLIENT", "20"))
MAX_CONCURRENT_HEAVY_PER_CLIENT = int(os.getenv("MAX_CONCURRENT_HEAVY_PER_CLIENT", "4"))
MAX_GLOBAL_HEAVY = int(os.getenv("MAX_GLOBAL_HEAVY", "12"))


def _resolve_concurrency_key(request: Request) -> str:
    # 1. Bearer header
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    token = None
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        # 2. Cookie
        token = request.cookies.get("matgar_session")

    if token:
        try:
            payload = decode_session_token(token)
            if payload and payload.get("sub"):
                return f"user:{payload['sub']}"
        except Exception:
            pass

    # 3. Normalized IP
    return f"ip:{resolve_client_ip(request)}"


@asynccontextmanager
async def concurrency_guard(
    request: Request,
    is_heavy: bool = False,
) -> AsyncGenerator[None, None]:
    """Admission control context manager rejecting excess concurrent work before execution."""
    if os.getenv("DISABLE_RATE_LIMITING", "").lower() in {"1", "true", "yes"}:
        yield
        return

    key = _resolve_concurrency_key(request)

    with _lock:
        current_client_total = _active_per_client[key]
        if current_client_total >= MAX_CONCURRENT_PER_CLIENT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many concurrent requests. Please wait for current requests to finish.",
                headers={"Retry-After": "1"},
            )

        if is_heavy:
            global _global_heavy_count
            current_client_heavy = _active_heavy_per_client[key]
            if current_client_heavy >= MAX_CONCURRENT_HEAVY_PER_CLIENT:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many concurrent resource-heavy operations in progress.",
                    headers={"Retry-After": "2"},
                )
            if _global_heavy_count >= MAX_GLOBAL_HEAVY:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Server is under heavy load. Please retry in a moment.",
                    headers={"Retry-After": "2"},
                )
            _active_heavy_per_client[key] += 1
            _global_heavy_count += 1

        _active_per_client[key] += 1

    try:
        yield
    finally:
        with _lock:
            _active_per_client[key] = max(0, _active_per_client[key] - 1)
            if _active_per_client[key] == 0:
                _active_per_client.pop(key, None)

            if is_heavy:
                _active_heavy_per_client[key] = max(0, _active_heavy_per_client[key] - 1)
                if _active_heavy_per_client[key] == 0:
                    _active_heavy_per_client.pop(key, None)
                _global_heavy_count = max(0, _global_heavy_count - 1)


def get_concurrency_stats() -> dict[str, int]:
    with _lock:
        return {
            "active_clients": len(_active_per_client),
            "total_in_flight": sum(_active_per_client.values()),
            "global_heavy_count": _global_heavy_count,
        }
