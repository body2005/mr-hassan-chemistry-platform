from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from contextlib import suppress

from fastapi import HTTPException
from redis.asyncio import Redis
from app.core.config import get_settings
from app.core.leases import ResourceLease
from app.core.rate_limit import _get_redis_client

# Inherit Uvicorn's operational handler/level; no tokens or event payloads.
logger = logging.getLogger("uvicorn.error.realtime")

UTC = timezone.utc


@dataclass
class EventSubscription:
    id: uuid.UUID
    institution_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    queue: asyncio.Queue[dict[str, Any] | None]
    created_at: datetime
    loop: asyncio.AbstractEventLoop


class RealTimeEventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, EventSubscription] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.RLock()
        # Async Redis connections and listener tasks belong to their own loop.
        # Overlapping lifespans must never cancel a different loop's Future.
        self._transport_locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}
        self._transports: dict[asyncio.AbstractEventLoop, tuple] = {}
        self._leases: dict[uuid.UUID, ResourceLease] = {}
        self._channel = "lms:events:v1"

    async def start(self):
        loop = asyncio.get_running_loop()
        self.set_loop(loop)
        lock = self._transport_locks.setdefault(loop, asyncio.Lock())
        async with lock:
            if loop in self._transports and not self._transports[loop][0].done():
                return
            client = await asyncio.to_thread(_get_redis_client)
            if client is None:
                if get_settings().redis_required or get_settings().deployment_environment:
                    raise HTTPException(503, "Event transport temporarily unavailable")
                return
            redis_async = Redis.from_url(get_settings().redis_url, decode_responses=True,
                                        socket_connect_timeout=2, socket_timeout=3)
            pubsub = redis_async.pubsub()
            try:
                await pubsub.subscribe(self._channel)
                # Subscribe acknowledgement prevents a first-event initialization race.
                await pubsub.get_message(timeout=3)
            except BaseException:
                await pubsub.aclose()
                await redis_async.aclose()
                raise
            self._transports[loop] = (asyncio.create_task(self._listen(pubsub)), pubsub, redis_async)

    async def stop(self):
        loop = asyncio.get_running_loop()
        with self._lock:
            owned = [sub.id for sub in self._subscribers.values() if sub.loop is loop]
        for sub_id in owned:
            await self.unregister(sub_id)
        transport = self._transports.pop(loop, None)
        if transport:
            listener, pubsub, redis_async = transport
            listener.cancel()
            with suppress(asyncio.CancelledError):
                await listener
            await pubsub.aclose()
            await redis_async.aclose()
        self._transport_locks.pop(loop, None)

    async def _listen(self, pubsub):
        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                if message and message.get("type") == "message":
                    self._deliver(json.loads(message["data"]))
            except (ValueError, TypeError):
                logger.warning("Malformed event transport payload discarded")
            except Exception:
                logger.warning("Event transport disconnected; persistent notifications remain in DB")
                await asyncio.sleep(1)

    def _deliver(self, envelope):
        institution_id = str(envelope["institution_id"])
        target_uids = envelope.get("target_user_ids")
        target_roles = envelope.get("target_roles")
        delivered = 0
        loop = asyncio.get_running_loop()
        with self._lock:
            subscribers = list(self._subscribers.values())
        for sub in subscribers:
            if sub.loop is not loop:
                continue
            if str(sub.institution_id) != institution_id:
                continue
            if target_uids is not None and str(sub.user_id) not in target_uids:
                continue
            if target_roles is not None and sub.role not in target_roles:
                continue
            if sub.queue.full():
                sub.queue.get_nowait()
            sub.queue.put_nowait(envelope["payload"])
            delivered += 1
        return delivered

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def get_loop(self) -> asyncio.AbstractEventLoop | None:
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        return self._loop

    async def register(
        self,
        institution_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
    ) -> EventSubscription:
        await self.start()
        self.set_loop(asyncio.get_running_loop())
        sub_id = uuid.uuid4()
        lease = ResourceLease([(f"sse:user:{institution_id}:{user_id}", 5),
                               (f"sse:institution:{institution_id}", 200)], global_index=2)
        distributed = await lease.acquire()
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=200)
        sub = EventSubscription(
            id=sub_id,
            institution_id=institution_id,
            user_id=user_id,
            role=str(role).lower(),
            queue=queue,
            created_at=datetime.now(UTC),
            loop=asyncio.get_running_loop(),
        )
        with self._lock:
            # Enforce max 5 simultaneous SSE streams per user (retires oldest on multi-tab overflow)
            user_subs = [s for s in self._subscribers.values() if s.user_id == user_id]
            if not distributed and len(user_subs) >= 5:
                oldest = min(user_subs, key=lambda s: s.created_at)
                self._subscribers.pop(oldest.id, None)
                try:
                    oldest.queue.put_nowait(None)
                except Exception:
                    pass
                logger.info("Retired oldest SSE connection %s for user %s", oldest.id, user_id)
            self._subscribers[sub_id] = sub
            if distributed:
                self._leases[sub_id] = lease
        logger.info(
            "Realtime subscriber registered: sub_id=%s user_id=%s role=%s total=%d worker_pid=" + str(os.getpid()),
            sub_id,
            user_id,
            role,
            len(self._subscribers),
        )
        return sub

    async def unregister(self, sub_id: uuid.UUID) -> None:
        lease = self._leases.pop(sub_id, None)
        if lease:
            await lease.release()
        with self._lock:
            sub = self._subscribers.pop(sub_id, None)
            if sub:
                # Wake up any waiting reader with None
                try:
                    sub.queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
        logger.info(
            "Realtime subscriber unregistered: sub_id=%s remaining=%d",
            sub_id,
            len(self._subscribers),
        )

    def publish_event(
        self,
        institution_id: uuid.UUID,
        event_type: str,
        data: dict[str, Any],
        target_user_ids: set[uuid.UUID] | list[uuid.UUID] | None = None,
        target_roles: set[str] | list[str] | None = None,
    ) -> int:
        """Thread-safe event publishing from both sync and async routes."""
        target_uids = (
            [str(u) for u in target_user_ids] if target_user_ids is not None else None
        )
        target_r = (
            [str(r).lower() for r in target_roles] if target_roles is not None else None
        )

        payload = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        envelope = {"institution_id": str(institution_id), "target_user_ids": target_uids,
                    "target_roles": target_r, "payload": payload}
        client = _get_redis_client()
        if client:
            try:
                delivered = client.publish(self._channel, json.dumps(envelope, ensure_ascii=False))
                logger.info("Realtime published: event_id=%s worker_pid=%s", payload["id"], os.getpid())
                return delivered
            except Exception:
                logger.warning("Realtime publishing unavailable; persistent notification must be fetched")
                return 0
        if get_settings().redis_required or get_settings().deployment_environment:
            return 0
        with self._lock:
            loops = {sub.loop for sub in self._subscribers.values()}
        for loop in loops:
            if not loop.is_closed():
                loop.call_soon_threadsafe(self._deliver, envelope)
        if loops:
            return len(self._subscribers)
        return 0


event_broker = RealTimeEventBroker()


async def sse_event_generator(
    sub: EventSubscription,
    authorized=None,
) -> AsyncGenerator[str, None]:
    """Yields SSE-formatted strings to the client with keepalive pings."""
    lease = event_broker._leases.get(sub.id)
    if lease:
        lease.owner = asyncio.current_task()
    try:
        # Even a disconnect immediately after headers must release admission.
        yield (
            f"event: connected\n"
            f"data: {json.dumps({'status': 'connected', 'sub_id': str(sub.id), 'user_id': str(sub.user_id)})}\n\n"
        )
        while True:
            try:
                # Wait for next event or send ping every 15 seconds
                msg = await asyncio.wait_for(sub.queue.get(), timeout=15.0)
                if authorized and not await asyncio.to_thread(authorized):
                    break
                if msg is None:
                    # Subscriber was unregistered
                    break
                event_type = msg.get("type", "message")
                event_id = msg.get("id", str(uuid.uuid4()))
                payload_str = json.dumps(msg.get("data", {}), ensure_ascii=False)
                yield f"id: {event_id}\nevent: {event_type}\ndata: {payload_str}\n\n"
            except asyncio.TimeoutError:
                if authorized and not await asyncio.to_thread(authorized):
                    break
                # Keep-alive comment line (standard SSE heartbeat)
                yield ": ping\n\n"
    except asyncio.CancelledError:
        logger.debug("SSE client cancelled connection sub_id=%s", sub.id)
    finally:
        await event_broker.unregister(sub.id)
