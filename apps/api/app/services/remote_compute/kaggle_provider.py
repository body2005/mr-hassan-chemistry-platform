from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

import httpx

from app.models.transcript import TranscriptionJob
from app.services.remote_compute.base import RemoteComputeProvider

logger = logging.getLogger(__name__)


class KaggleProvider(RemoteComputeProvider):
    """
    Kaggle Remote GPU Compute Provider.
    Dispatches long-video transcription jobs to a live Kaggle GPU worker instance
    running QwenCleo-ASR (or a continuous polling queue listener).
    """

    def __init__(
        self,
        worker_endpoint: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.worker_endpoint = (
            worker_endpoint
            or os.getenv("KAGGLE_ASR_URL")
            or os.getenv("REMOTE_ASR_URL")
            or ""
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "kaggle"

    async def is_healthy(self) -> bool:
        if not self.worker_endpoint:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.worker_endpoint}/health")
                return res.status_code == 200
        except Exception:
            return False

    async def submit_job(
        self,
        job: TranscriptionJob,
        media_download_url: str,
        callback_url: str,
        callback_secret: str,
    ) -> bool:
        if not self.worker_endpoint:
            logger.warning("[KaggleProvider] No worker endpoint configured.")
            return False

        # Fast Liveness Check: verify remote worker is reachable before dispatching
        is_alive = await self.is_healthy()
        if not is_alive:
            logger.warning(f"[KaggleProvider] Kaggle worker at {self.worker_endpoint} is offline or stale (health check failed).")
            return False

        payload = {
            "job_id": str(job.id),
            "video_id": str(job.video_id),
            "lesson_id": str(job.lesson_id),
            "course_id": str(job.course_id),
            "media_url": media_download_url,
            "callback_url": callback_url,
            "model": job.model_name or "QwenCleo-ASR",
            "language": "ar",
            "chunk_size": int(os.getenv("CHUNK_SIZE", "30")),
            "overlap": int(os.getenv("CHUNK_OVERLAP", "2")),
            "timestamp": int(time.time()),
        }

        # Calculate HMAC signature for dispatch payload
        canonical_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(
            callback_secret.encode("utf-8"),
            canonical_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Dispatch-Signature": signature,
            "X-Job-ID": str(job.id),
        }

        dispatch_url = f"{self.worker_endpoint}/jobs"
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(dispatch_url, json=payload, headers=headers)
                    if resp.status_code in {200, 201, 202}:
                        logger.info(f"[KaggleProvider] Dispatched job {job.id} to Kaggle successfully.")
                        return True
                    logger.warning(f"[KaggleProvider] Attempt {attempt} failed with HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as exc:
                logger.warning(f"[KaggleProvider] Attempt {attempt} failed: {exc}")

            if attempt < self.max_retries:
                await asyncio.sleep(2.0 ** attempt)

        return False

    async def get_status(self, job: TranscriptionJob) -> dict[str, Any]:
        if not self.worker_endpoint:
            return {"status": "offline", "provider": "kaggle"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.worker_endpoint}/jobs/{job.id}")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return {"status": "unknown", "provider": "kaggle"}

    async def cancel_job(self, job: TranscriptionJob) -> bool:
        if not self.worker_endpoint:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(f"{self.worker_endpoint}/jobs/{job.id}/cancel")
                return resp.status_code in {200, 204}
        except Exception:
            return False
