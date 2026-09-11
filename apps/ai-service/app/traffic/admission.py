import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from app.config import get_settings
from app.core.exceptions import AdmissionLimitExceededException
from app.core.telemetry import telemetry
from app.core.logging import logger


class AdmissionController:
    """
    Admission Control & GPU Concurrency Gate:
    - Protects the 8GB-class GPU from VRAM exhaustion and unconstrained concurrent LLM inferences.
    - Gates interactive synchronous requests behind a strict semaphore.
    - Implements timeout-based admission: if capacity is saturated and cannot be acquired within
      SEMAPHORE_TIMEOUT_SECONDS, immediately raises an AdmissionLimitExceededException (503).
    - Synchronously maintains telemetry on active local inference threads.
    """

    def __init__(self, max_concurrent: Optional[int] = None):
        self.settings = get_settings()
        self._max_concurrent = max_concurrent or self.settings.MAX_CONCURRENT_INTERACTIVE_INFERENCES
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._lock = asyncio.Lock()

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self._semaphore

    @property
    def max_capacity(self) -> int:
        return self._max_concurrent

    @property
    def available_slots(self) -> int:
        sem = self._get_semaphore()
        return sem._value

    @asynccontextmanager
    async def acquire_slot(self, timeout_seconds: Optional[float] = None) -> AsyncGenerator[None, None]:
        sem = self._get_semaphore()
        timeout = timeout_seconds or self.settings.SEMAPHORE_TIMEOUT_SECONDS

        acquired = False
        try:
            try:
                # Wait for slot within strict timeout window
                await asyncio.wait_for(sem.acquire(), timeout=timeout)
                acquired = True
            except asyncio.TimeoutError:
                logger.warning(
                    f"Admission control saturated: Failed to acquire GPU inference slot within {timeout}s. "
                    f"Capacity: {self._max_concurrent}, Active: {self.settings.MAX_CONCURRENT_INTERACTIVE_INFERENCES - sem._value}"
                )
                raise AdmissionLimitExceededException(
                    message="GPU inference capacity is currently saturated. Please retry in a few moments.",
                    retry_after=5
                )

            telemetry.increment_active_gpu()
            yield

        finally:
            if acquired:
                sem.release()
                telemetry.decrement_active_gpu()


admission_controller = AdmissionController()
