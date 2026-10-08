"""Atomic cross-process resource reservations with crash-expiring leases."""
import asyncio
import anyio
import logging
import uuid
from contextlib import suppress

from fastapi import HTTPException

from app.core.config import get_settings
from app.core.rate_limit import _get_redis_client

logger = logging.getLogger(__name__)
LEASE_SECONDS = 120
RENEW_INTERVAL_SECONDS = 30
ACQUIRE = """
local t = redis.call('TIME'); local now = tonumber(t[1]) + tonumber(t[2])/1000000
for i,key in ipairs(KEYS) do
  redis.call('ZREMRANGEBYSCORE', key, '-inf', now)
  if redis.call('ZCARD', key) >= tonumber(ARGV[i+2]) then return i end
end
for _,key in ipairs(KEYS) do
  redis.call('ZADD', key, now + tonumber(ARGV[2]), ARGV[1])
  redis.call('EXPIRE', key, tonumber(ARGV[2]) + 5)
end
return 0
"""
RENEW = """
local t = redis.call('TIME'); local now = tonumber(t[1]) + tonumber(t[2])/1000000
for _,key in ipairs(KEYS) do
  local score = redis.call('ZSCORE', key, ARGV[1])
  if not score or tonumber(score) <= now then return 0 end
end
for _,key in ipairs(KEYS) do
  redis.call('ZADD', key, now + tonumber(ARGV[2]), ARGV[1])
  redis.call('EXPIRE', key, tonumber(ARGV[2]) + 5)
end
return 1
"""
RELEASE = "for _,key in ipairs(KEYS) do redis.call('ZREM', key, ARGV[1]) end return 1"


class ResourceLease:
    def __init__(self, resources: list[tuple[str, int]], *, global_index: int | None = None):
        self.keys = [key for key, _ in resources]
        self.limits = [limit for _, limit in resources]
        self.token = uuid.uuid4().hex
        self.global_index = global_index
        self.client = None
        self.renew_task = None
        self.owner = None
        self.lost = False

    async def acquire(self) -> bool:
        self.client = await asyncio.to_thread(_get_redis_client)
        if self.client is None:
            if get_settings().redis_required:
                raise HTTPException(503, "Admission service temporarily unavailable", headers={"Retry-After": "2"})
            return False
        try:
            denied = await asyncio.to_thread(self.client.eval, ACQUIRE, len(self.keys), *self.keys,
                                             self.token, LEASE_SECONDS, *self.limits)
        except Exception as exc:
            # Never multiply local budgets during a production Redis outage.
            raise HTTPException(503, "Admission service temporarily unavailable", headers={"Retry-After": "2"}) from exc
        if denied:
            raise HTTPException(503 if denied == self.global_index else 429,
                                "Concurrent resource limit reached", headers={"Retry-After": "2"})
        self.owner = asyncio.current_task()
        self.renew_task = asyncio.create_task(self._renew())
        return True

    async def _renew(self):
        while True:
            await asyncio.sleep(RENEW_INTERVAL_SECONDS)
            failure = None
            try:
                alive = await asyncio.to_thread(self.client.eval, RENEW, len(self.keys), *self.keys,
                                               self.token, LEASE_SECONDS)
            except Exception as exc:
                alive = False
                failure = type(exc).__name__
            if not alive:
                self.lost = True
                logger.warning("Resource lease lost; closing reserved work (reason=%s)",
                               failure or "reservation_missing_or_expired")
                if self.owner and not self.owner.done():
                    self.owner.cancel()
                return

    async def run(self, app, scope, receive, send):
        """Fail closed on OUR cancellation, without rewriting client disconnects.

        Once headers are sent, close the stream instead of emitting a second
        status or a successful tail. No resource budget or renewal is relaxed.
        """
        started = False

        async def guarded_send(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
            await send(message)

        try:
            return await app(scope, receive, guarded_send)
        except asyncio.CancelledError:
            if not self.lost or started:
                raise
            from fastapi.responses import JSONResponse
            with anyio.CancelScope(shield=True):
                return await JSONResponse(
                    {'detail': 'Admission service temporarily unavailable'},
                    status_code=503, headers={'Retry-After': '2'},
                )(scope, receive, send)

    async def release(self):
        # Streaming disconnect cancels the ASGI task. Cleanup must run outside
        # that cancellation scope or Redis reservations renew indefinitely.
        with anyio.CancelScope(shield=True):
            await self._release()

    async def _release(self):
        if self.renew_task:
            self.renew_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.renew_task
            self.renew_task = None
        if self.client:
            try:
                await asyncio.to_thread(self.client.eval, RELEASE, len(self.keys), *self.keys, self.token)
            except Exception:
                # Crash/connection loss is recovered by the bounded lease TTL.
                logger.warning("Resource lease release deferred until expiry")
