from __future__ import annotations

import logging
import os
import threading
import time
import uuid
import ipaddress
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException, Request, status
import redis

from app.core.config import get_settings
from app.core.security import decode_session_token

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_windows: dict[str, deque[float]] = defaultdict(deque)

_redis_client: redis.Redis | None = None
_redis_script = None

LUA_SLIDING_WINDOW = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

local clearBefore = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', clearBefore)
local currentCount = redis.call('ZCARD', key)

if currentCount < limit then
    redis.call('ZADD', key, now, member)
    redis.call('PEXPIRE', key, window + 1000)
    return {1, limit - currentCount - 1, 0}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retryAfterMs = window
    if #oldest > 0 then
        local oldestScore = tonumber(oldest[2])
        retryAfterMs = math.max(0, math.ceil(oldestScore + window - now))
    end
    local retryAfterSec = math.max(1, math.ceil(retryAfterMs / 1000))
    return {0, 0, retryAfterSec}
end
"""


def _get_redis_client() -> redis.Redis | None:
    global _redis_client, _redis_script
    settings = get_settings()
    if _redis_client is not None:
        return _redis_client
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
            decode_responses=True,
        )
        client.ping()
        _redis_script = client.register_script(LUA_SLIDING_WINDOW)
        _redis_client = client
        return _redis_client
    except Exception:
        # A previous connection can become stale. Never retain it or expose
        # connection details in logs; the next request may establish a new one.
        _redis_client = None
        _redis_script = None
        logger.warning("Redis rate limiting is unavailable")
        return None


def _is_trusted(ip: str, trusted_exact: set[str], trusted_networks: list[Any]) -> bool:
    if ip in trusted_exact:
        return True
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in network for network in trusted_networks)


def resolve_client_ip(request: Request) -> str:
    settings = get_settings()
    direct_ip = request.client.host if request.client else "127.0.0.1"
    trusted_raw = getattr(settings, "trusted_proxies", "127.0.0.1,::1")
    if trusted_raw.strip() == "*":
        # Never trust an arbitrary client-controlled XFF chain. Deployments
        # must configure the actual proxy addresses or CIDRs explicitly.
        logger.error("TRUSTED_PROXIES='*' is unsafe; ignoring forwarded headers")
        return direct_ip

    trusted_exact: set[str] = set()
    trusted_networks: list[Any] = []
    for entry in trusted_raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "/" in entry:
            try:
                trusted_networks.append(ipaddress.ip_network(entry, strict=False))
                continue
            except ValueError:
                logger.warning("Ignoring invalid trusted proxy CIDR: %s", entry)
                continue
        trusted_exact.add(entry)

    if not _is_trusted(direct_ip, trusted_exact, trusted_networks):
        return direct_ip
    forwarded = request.headers.get("X-Forwarded-For")
    if not forwarded:
        return direct_ip
    hops = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
    for hop in reversed(hops):
        if not _is_trusted(hop, trusted_exact, trusted_networks):
            return hop
    return hops[0] if hops else direct_ip


def resolve_rate_limit_key(request: Request, category: str) -> str:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    if token:
        payload = decode_session_token(token)
        if payload and payload.get("sub") and payload.get("institution_id"):
            user_id = payload["sub"]
            institution_id = payload["institution_id"]
            return f"rate-limit:{category}:{institution_id}:{user_id}"

    normalized_ip = resolve_client_ip(request)
    return f"rate-limit:{category}:ip:{normalized_ip}"


def _get_category_defaults(category: str) -> tuple[int, int]:
    settings = get_settings()
    window = settings.rate_limit_window_seconds
    cat_lower = category.lower().replace("-", "_")

    if "login" in cat_lower or "auth" in cat_lower:
        return settings.rate_limit_login, window
    if "read" in cat_lower or "preview" in cat_lower:
        return settings.rate_limit_read, window
    if "ai" in cat_lower:
        return settings.rate_limit_ai, window
    if "upload" in cat_lower:
        return settings.rate_limit_upload, window
    if "quiz" in cat_lower or "exam" in cat_lower or "extract" in cat_lower:
        return settings.rate_limit_quiz_extraction, window
    if "pdf" in cat_lower or "render" in cat_lower:
        return settings.rate_limit_pdf_render, window
    return settings.rate_limit_api_default, window


def _in_memory_enforce(key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    with _lock:
        entries = _windows[key]
        cutoff = now - window_seconds
        while entries and entries[0] <= cutoff:
            entries.popleft()
        if len(entries) >= limit:
            oldest = entries[0]
            retry_after = max(1, int(oldest + window_seconds - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        entries.append(now)


def enforce_rate_limit(
    request: Request,
    *,
    bucket: str | None = None,
    category: str | None = None,
    limit: int | None = None,
    window_seconds: int | None = None,
) -> None:
    global _redis_client, _redis_script
    if os.getenv("DISABLE_RATE_LIMITING", "").lower() in {"1", "true", "yes"}:
        return

    settings = get_settings()
    effective_category = (category or bucket or "api").lower().replace("-", "_")
    categories_already_enforced = getattr(request.state, "rate_limit_categories", set())
    if effective_category in categories_already_enforced:
        return
    default_limit, default_window = _get_category_defaults(effective_category)
    final_limit = limit if limit is not None else default_limit
    final_window = window_seconds if window_seconds is not None else default_window

    key = resolve_rate_limit_key(request, effective_category)

    # Attempt Redis atomic sliding window first
    r = _get_redis_client()
    if r is not None and _redis_script is not None:
        try:
            now_ms = int(time.time() * 1000)
            window_ms = int(final_window * 1000)
            member = f"{now_ms}:{uuid.uuid4().hex[:8]}"
            result = _redis_script(keys=[key], args=[now_ms, window_ms, final_limit, member])
            allowed = bool(result[0])
            if not allowed:
                retry_after = int(result[2])
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            return
        except HTTPException:
            raise
        except Exception:
            _redis_client = None
            _redis_script = None
            logger.warning("Redis rate limiting query failed")

    if settings.redis_required or settings.app_env.lower() in {"production", "production_like"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting is temporarily unavailable.",
            headers={"Retry-After": "1"},
        )

    # Per-process fallback is deliberately restricted to development/testing.
    _in_memory_enforce(key, final_limit, final_window)


def reset_rate_limits() -> None:
    with _lock:
        _windows.clear()
    r = _get_redis_client()
    if r is not None:
        try:
            cursor = 0
            while True:
                cursor, keys = r.scan(cursor=cursor, match="rate-limit:*", count=100)
                if keys:
                    r.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            # This is a maintenance-only helper used by tests and trusted
            # operators. Avoid leaking a Redis URL while preserving evidence.
            logger.exception("Unable to clear Redis rate-limit keys")
