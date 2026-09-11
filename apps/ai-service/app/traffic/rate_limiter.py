import time
from collections import defaultdict, deque
from typing import Dict, Optional
import redis.asyncio as aioredis
from app.config import get_settings
from app.core.exceptions import RateLimitExceededException
from app.core.logging import logger


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter:
    - Protects the service from client bursts.
    - Uses Redis sorted sets when available; falls back to an in-memory deque per client.
    """

    def __init__(self):
        self.settings = get_settings()
        self._redis: Optional[aioredis.Redis] = None
        self._in_memory_windows: Dict[str, deque] = defaultdict(deque)

    async def get_redis_client(self) -> Optional[aioredis.Redis]:
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    self.settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=1.0,
                    socket_timeout=1.0
                )
            except Exception as e:
                logger.warning(f"Rate limiter could not connect to Redis at {self.settings.REDIS_URL}: {e}")
                self._redis = None
        return self._redis

    async def check_rate_limit(self, client_id: str, limit: Optional[int] = None, window_seconds: int = 60) -> None:
        """
        Validates whether the given client_id has exceeded limit requests in the last window_seconds.
        Raises RateLimitExceededException if limit is violated.
        """
        max_reqs = limit or self.settings.RATE_LIMIT_PER_MINUTE
        now = time.time()
        window_start = now - window_seconds

        client = await self.get_redis_client()
        if client:
            try:
                key = f"ai_ratelimit:{client_id}"
                pipeline = client.pipeline()
                pipeline.zremrangebyscore(key, 0, window_start)
                pipeline.zcard(key)
                pipeline.zadd(key, {str(now): now})
                pipeline.expire(key, window_seconds + 5)
                results = await pipeline.execute()

                current_count = results[1]
                if current_count >= max_reqs:
                    raise RateLimitExceededException(
                        message=f"Rate limit of {max_reqs} requests per {window_seconds}s exceeded.",
                        retry_after=window_seconds
                    )
                return
            except RateLimitExceededException:
                raise
            except Exception as e:
                if self.settings.ENVIRONMENT in {"staging", "production"} and self.settings.REQUIRE_REDIS:
                    logger.error("Redis rate limiter is required but unavailable")
                    raise RuntimeError("Redis rate limiter unavailable") from e
                logger.warning(f"Redis rate limiter failed: {e}. Falling back to in-memory rate limiter.")

        if self.settings.ENVIRONMENT in {"staging", "production"} and self.settings.REQUIRE_REDIS:
            raise RuntimeError("Redis rate limiter unavailable")

        # In-memory sliding window fallback (development/test only when Redis is optional)
        timestamps = self._in_memory_windows[client_id]
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= max_reqs:
            raise RateLimitExceededException(
                message=f"Rate limit of {max_reqs} requests per {window_seconds}s exceeded.",
                retry_after=window_seconds
            )

        timestamps.append(now)


rate_limiter = SlidingWindowRateLimiter()
