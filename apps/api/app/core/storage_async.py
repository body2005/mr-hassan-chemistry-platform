"""Offload synchronous storage transfers without abandoning staging on cancel."""
from __future__ import annotations

import asyncio

import anyio

from app.core.storage import BaseStorageProvider


async def save_file_async(
    storage: BaseStorageProvider,
    source: str,
    key: str,
    content_type: str | None = None,
) -> str:
    # S3's SDK is synchronous. Running it on the HTTP loop starves request and
    # Redis lease heartbeats. Cancelling to_thread doesn't stop its thread:
    # wait for completion before callers delete staging or compensate S3.
    transfer = asyncio.create_task(asyncio.to_thread(storage.save_file, source, key, content_type))
    try:
        return await asyncio.shield(transfer)
    except BaseException:
        with anyio.CancelScope(shield=True):
            while not transfer.done():
                try:
                    await asyncio.shield(transfer)
                except asyncio.CancelledError:
                    # A second cancellation must not race file cleanup either.
                    continue
                except Exception:
                    break
            if transfer.done() and not transfer.cancelled():
                # Consume a late SDK exception; preserve the original failure.
                transfer.exception()
        raise
