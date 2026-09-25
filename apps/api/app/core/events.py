from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)

UTC = timezone.utc


@dataclass
class EventSubscription:
    id: uuid.UUID
    institution_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    queue: asyncio.Queue[dict[str, Any] | None]
    created_at: datetime


class RealTimeEventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, EventSubscription] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = asyncio.Lock()

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
        self.set_loop(asyncio.get_running_loop())
        sub_id = uuid.uuid4()
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=200)
        sub = EventSubscription(
            id=sub_id,
            institution_id=institution_id,
            user_id=user_id,
            role=str(role).lower(),
            queue=queue,
            created_at=datetime.now(UTC),
        )
        async with self._lock:
            # Enforce max 5 simultaneous SSE streams per user (retires oldest on multi-tab overflow)
            user_subs = [s for s in self._subscribers.values() if s.user_id == user_id]
            if len(user_subs) >= 5:
                oldest = min(user_subs, key=lambda s: s.created_at)
                self._subscribers.pop(oldest.id, None)
                try:
                    oldest.queue.put_nowait(None)
                except Exception:
                    pass
                logger.info("Retired oldest SSE connection %s for user %s", oldest.id, user_id)
            self._subscribers[sub_id] = sub
        logger.info(
            "Realtime subscriber registered: sub_id=%s user_id=%s role=%s total=%d",
            sub_id,
            user_id,
            role,
            len(self._subscribers),
        )
        return sub

    async def unregister(self, sub_id: uuid.UUID) -> None:
        async with self._lock:
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
        loop = self.get_loop()
        if loop is None or loop.is_closed():
            logger.debug("No active event loop for publish_event %s", event_type)
            return 0

        target_uids = (
            {uuid.UUID(str(u)) for u in target_user_ids} if target_user_ids else None
        )
        target_r = (
            {str(r).lower() for r in target_roles} if target_roles else None
        )

        payload = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        delivered = 0
        for sub in list(self._subscribers.values()):
            if sub.institution_id != institution_id:
                continue
            if target_uids is not None and sub.user_id not in target_uids:
                continue
            if target_r is not None and sub.role not in target_r:
                continue

            def _push_queue(q: asyncio.Queue, msg: dict[str, Any]) -> None:
                try:
                    if q.full():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    q.put_nowait(msg)
                except Exception as exc:
                    logger.debug("Failed to push to queue: %s", exc)

            loop.call_soon_threadsafe(_push_queue, sub.queue, payload)
            delivered += 1

        logger.debug(
            "Published event %s to %d subscribers in institution %s",
            event_type,
            delivered,
            institution_id,
        )
        return delivered


event_broker = RealTimeEventBroker()


async def sse_event_generator(
    sub: EventSubscription,
) -> AsyncGenerator[str, None]:
    """Yields SSE-formatted strings to the client with keepalive pings."""
    # Send initial connection acknowledgment
    yield (
        f"event: connected\n"
        f"data: {json.dumps({'status': 'connected', 'sub_id': str(sub.id), 'user_id': str(sub.user_id)})}\n\n"
    )

    try:
        while True:
            try:
                # Wait for next event or send ping every 15 seconds
                msg = await asyncio.wait_for(sub.queue.get(), timeout=15.0)
                if msg is None:
                    # Subscriber was unregistered
                    break
                event_type = msg.get("type", "message")
                event_id = msg.get("id", str(uuid.uuid4()))
                payload_str = json.dumps(msg.get("data", {}), ensure_ascii=False)
                yield f"id: {event_id}\nevent: {event_type}\ndata: {payload_str}\n\n"
            except asyncio.TimeoutError:
                # Keep-alive comment line (standard SSE heartbeat)
                yield ": ping\n\n"
    except asyncio.CancelledError:
        logger.debug("SSE client cancelled connection sub_id=%s", sub.id)
    finally:
        await event_broker.unregister(sub.id)
