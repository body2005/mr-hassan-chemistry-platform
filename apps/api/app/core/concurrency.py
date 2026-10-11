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
from app.core.config import get_settings
from app.core.security import decode_session_token
from app.core.leases import ResourceLease

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
        token = request.cookies.get(get_settings().session_cookie_name)

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
    pool: str = "client",
) -> AsyncGenerator[ResourceLease | None, None]:
    """Admission control context manager rejecting excess concurrent work before execution."""
    if os.getenv("APP_ENV") == "test" and os.getenv("DISABLE_RATE_LIMITING", "").lower() in {"1", "true", "yes"}:
        yield
        return

    key = _resolve_concurrency_key(request)
    # Long-lived video/SSE responses have independent finite budgets. They
    # must not consume all the slots needed to login, solve or renew a session.
    pool_limit = {"video": 8, "realtime": 5}.get(pool, MAX_CONCURRENT_PER_CLIENT)
    resources = [(f"admission:{pool}:{key}", pool_limit)]
    if is_heavy:
        resources += [(f"admission:heavy:{key}", MAX_CONCURRENT_HEAVY_PER_CLIENT),
                      ("admission:heavy:global", MAX_GLOBAL_HEAVY)]
    lease = ResourceLease(resources, global_index=3 if is_heavy else None)
    distributed = await lease.acquire()
    if distributed:
        try:
            yield lease
        finally:
            await lease.release()
        return

    with _lock:
        local_key = f"{pool}:{key}"
        current_client_total = _active_per_client[local_key]
        if current_client_total >= pool_limit:
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

        _active_per_client[local_key] += 1

    try:
        yield
    finally:
        with _lock:
            _active_per_client[local_key] = max(0, _active_per_client[local_key] - 1)
            if _active_per_client[local_key] == 0:
                _active_per_client.pop(local_key, None)

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


class AdmissionMiddleware:
    """Pure ASGI: reservation lasts through the final byte/disconnect, not headers."""
    def __init__(self, app, classify):
        self.app = app
        self.classify = classify

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        request = Request(scope)
        category = self.classify(scope["method"], scope["path"])
        path = scope["path"].rstrip("/")
        pool = ("realtime" if path.endswith("/realtime/stream") else
                "video" if scope["method"] in {"GET", "HEAD"} and "/lessons/" in path
                and (path.endswith(("/stream", "/video")) or "/hls/" in path) else "client")
        guard = concurrency_guard(request, is_heavy=category in {"heavy_query", "upload", "quiz_extraction"}, pool=pool)
        try:
            lease = await guard.__aenter__()
        except HTTPException as exc:
            from fastapi.responses import JSONResponse
            response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
            return await response(scope, receive, send)
        try:
            if lease is not None:
                await lease.run(self.app, scope, receive, send)
            else:
                await self.app(scope, receive, send)
        finally:
            await guard.__aexit__(None, None, None)
