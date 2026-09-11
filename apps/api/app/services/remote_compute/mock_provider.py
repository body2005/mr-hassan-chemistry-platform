from __future__ import annotations

import asyncio
from typing import Any
import httpx

from app.models.transcript import TranscriptionJob
from app.services.remote_compute.base import RemoteComputeProvider


class MockRemoteProvider(RemoteComputeProvider):
    """
    Deterministic mock provider for automated unit and integration tests.
    Simulates remote dispatch, execution, and callback with zero external network.
    """

    def __init__(self, simulate_latency_sec: float = 0.0, should_fail: bool = False) -> None:
        self.simulate_latency_sec = simulate_latency_sec
        self.should_fail = should_fail
        self.dispatched_jobs: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "mock"

    async def submit_job(
        self,
        job: TranscriptionJob,
        media_download_url: str,
        callback_url: str,
        callback_secret: str,
    ) -> bool:
        if self.should_fail:
            return False

        record = {
            "job_id": str(job.id),
            "media_url": media_download_url,
            "callback_url": callback_url,
            "callback_secret": callback_secret,
        }
        self.dispatched_jobs.append(record)

        if self.simulate_latency_sec > 0:
            await asyncio.sleep(self.simulate_latency_sec)

        return True

    async def get_status(self, job: TranscriptionJob) -> dict[str, Any]:
        return {
            "status": "processing",
            "progress_percent": 50,
            "stage": "transcribing",
            "provider": "mock",
        }

    async def cancel_job(self, job: TranscriptionJob) -> bool:
        return True

    async def is_healthy(self) -> bool:
        return not self.should_fail
