import pytest
from app.core.exceptions import RateLimitExceededException
from app.traffic.rate_limiter import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_and_blocks():
    limiter = SlidingWindowRateLimiter()
    client_id = "test_student_123"

    # Allow 3 requests
    for _ in range(3):
        await limiter.check_rate_limit(client_id, limit=3, window_seconds=60)

    # 4th request must raise RateLimitExceededException
    with pytest.raises(RateLimitExceededException) as exc_info:
        await limiter.check_rate_limit(client_id, limit=3, window_seconds=60)

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 60
