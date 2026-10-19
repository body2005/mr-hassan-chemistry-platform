from __future__ import annotations

import logging
import anyio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import CurrentUser, DbSession, session_is_current
from app.core.database import SessionLocal, close_request_session
from app.core.config import get_settings
from app.core.events import event_broker, sse_event_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/realtime", tags=["realtime"])


class RealtimeResponse(StreamingResponse):
    def __init__(self, *args, subscription_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscription_id = subscription_id

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Covers failure/disconnect while sending headers, before the
            # generator starts and its own finally can release the SSE slot.
            with anyio.CancelScope(shield=True):
                await event_broker.unregister(self.subscription_id)


@router.get("/stream")
async def realtime_event_stream(
    user: CurrentUser,
    request: Request,
    db: DbSession,
) -> StreamingResponse:
    """Server-Sent Events endpoint streaming real-time notifications and updates.

    Authenticated via user session cookie or token. Yields keep-alives and targeted
    events for the logged-in user and their institution.
    """
    # Release BEFORE the first async broker/lease wait. Otherwise a burst can
    # hold every DB connection while waiting for Redis work queued behind SSE
    # revalidation threads that themselves need those connections.
    await close_request_session(db)
    sub = await event_broker.register(
        institution_id=user.institution_id,
        user_id=user.id,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
    )
    def still_authorized():
        with SessionLocal() as fresh:
            try:
                return session_is_current(request, fresh)
            except Exception:
                return False

    return RealtimeResponse(
        sse_event_generator(sub, still_authorized),
        subscription_id=sub.id,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable proxy buffering (Nginx, Render)
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )
