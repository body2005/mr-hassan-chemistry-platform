from __future__ import annotations

import abc
from typing import Any

from app.models.transcript import TranscriptionJob


class RemoteComputeProvider(abc.ABC):
    """
    Provider-agnostic interface for remote GPU / local compute transcription engines.
    Allows seamlessly swapping between Kaggle, RunPod, Modal, Local Whisper, or Mocks.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        pass

    @abc.abstractmethod
    async def submit_job(
        self,
        job: TranscriptionJob,
        media_download_url: str,
        callback_url: str,
        callback_secret: str,
    ) -> bool:
        """
        Submit a transcription job to the compute provider.
        Returns True if successfully dispatched/queued, False otherwise.
        """
        pass

    @abc.abstractmethod
    async def get_status(self, job: TranscriptionJob) -> dict[str, Any]:
        """
        Query the current status of a submitted job from the provider.
        Returns a dict with 'status', 'progress_percent', 'stage', 'error_message' if available.
        """
        pass

    @abc.abstractmethod
    async def cancel_job(self, job: TranscriptionJob) -> bool:
        """Cancel a running or queued job on the provider."""
        pass

    @abc.abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the provider endpoint / worker is online and reachable."""
        pass
