from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import time
from typing import Any

from app.models.transcript import TranscriptionJob
from app.services.remote_compute.base import RemoteComputeProvider

logger = logging.getLogger(__name__)


class LocalFallbackProvider(RemoteComputeProvider):
    """
    Local CPU Compute Provider.
    Runs Faster-Whisper Small (int8) on the host machine as an automatic fallback
    when remote cloud GPUs are offline or when configured for local-only mode.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("WHISPER_MODEL", "small")

    @property
    def name(self) -> str:
        return "local_whisper"

    async def is_healthy(self) -> bool:
        return True

    async def submit_job(
        self,
        job: TranscriptionJob,
        media_download_url: str,
        callback_url: str,
        callback_secret: str,
    ) -> bool:
        # Local execution is handled directly or via background worker task
        logger.info(f"[LocalFallbackProvider] Queued local job {job.id} on host CPU.")
        return True

    async def get_status(self, job: TranscriptionJob) -> dict[str, Any]:
        return {
            "status": "processing",
            "progress_percent": job.progress_percent,
            "stage": job.current_stage,
            "provider": "local_whisper",
        }

    async def cancel_job(self, job: TranscriptionJob) -> bool:
        return True
