import asyncio
import pytest
from app.core.exceptions import AdmissionLimitExceededException
from app.traffic.admission import AdmissionController


@pytest.mark.asyncio
async def test_admission_controller_allows_under_limit():
    controller = AdmissionController(max_concurrent=2)
    assert controller.available_slots == 2

    async with controller.acquire_slot(timeout_seconds=0.5):
        assert controller.available_slots == 1
        async with controller.acquire_slot(timeout_seconds=0.5):
            assert controller.available_slots == 0

    assert controller.available_slots == 2


@pytest.mark.asyncio
async def test_admission_controller_times_out_when_saturated():
    controller = AdmissionController(max_concurrent=1)

    async def hold_slot():
        async with controller.acquire_slot(timeout_seconds=1.0):
            await asyncio.sleep(0.4)

    # Launch holder task
    task = asyncio.create_task(hold_slot())
    await asyncio.sleep(0.05)

    # Try acquiring with shorter timeout (0.1s)
    with pytest.raises(AdmissionLimitExceededException) as exc_info:
        async with controller.acquire_slot(timeout_seconds=0.1):
            pass

    assert exc_info.value.status_code == 503
    assert "saturated" in exc_info.value.message.lower()
    assert exc_info.value.retry_after == 5

    await task
    assert controller.available_slots == 1
