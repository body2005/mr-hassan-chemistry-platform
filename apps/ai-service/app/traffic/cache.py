import hashlib
import json
import time
from typing import Any, Dict, Optional, Union
import redis.asyncio as aioredis
from app.config import get_settings
from app.core.logging import logger


class RequestCache:
    """
    Deterministic Request Caching Layer:
    - Generates deterministic SHA-256 keys from domain, prompt template version, and normalized payload.
    - Applies domain-specific TTLs (e.g. 24h for quizzes/reports, 48h for essay grading).
    - Supports LMS cache-bypass headers.
    - Provides seamless in-memory fallback when Redis is unreachable.
    """

    def __init__(self):
        self.settings = get_settings()
        self._redis: Optional[aioredis.Redis] = None
        self._in_memory_store: Dict[str, Dict[str, Any]] = {}
        self._in_memory_max_items = 1000

    async def get_redis_client(self) -> Optional[aioredis.Redis]:
        if not self.settings.CACHE_ENABLED:
            return None
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    self.settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=1.0,
                    socket_timeout=1.0
                )
            except Exception as e:
                logger.warning(f"Failed to connect to Redis cache at {self.settings.REDIS_URL}: {e}. Using in-memory cache.")
                self._redis = None
        return self._redis

    def generate_key(self, domain: str, payload: Union[Dict[str, Any], str], prompt_version: str = "v1") -> str:
        """
        Creates a deterministic hash of the request payload and domain constraints.
        """
        if isinstance(payload, dict):
            # Sort keys for deterministic JSON serialization
            serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
        else:
            serialized = str(payload)

        payload_hash = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        return f"ai_cache:{domain}:{prompt_version}:{payload_hash}"

    def _get_ttl_for_domain(self, domain: str) -> int:
        if domain == "quiz":
            return self.settings.TTL_QUIZ_CACHE
        elif domain == "grading":
            return self.settings.TTL_GRADING_CACHE
        elif domain == "reports":
            return self.settings.TTL_REPORT_CACHE
        elif domain == "analytics":
            return self.settings.TTL_ANALYTICS_CACHE
        return 3600  # Default 1 hour fallback

    async def get(self, key: str, bypass_cache: bool = False) -> Optional[Dict[str, Any]]:
        if bypass_cache or not self.settings.CACHE_ENABLED:
            return None

        client = await self.get_redis_client()
        if client:
            try:
                val = await client.get(key)
                if val:
                    return json.loads(val)
            except Exception as e:
                if self.settings.ENVIRONMENT in {"staging", "production"} and self.settings.REQUIRE_REDIS:
                    logger.error("Redis cache is required but unavailable")
                    raise RuntimeError("Redis cache unavailable") from e
                logger.warning(f"Redis get error for {key}: {e}. Checking memory fallback.")

        if self.settings.ENVIRONMENT in {"staging", "production"} and self.settings.REQUIRE_REDIS:
            raise RuntimeError("Redis cache unavailable")

        # In-memory fallback check
        entry = self._in_memory_store.get(key)
        if entry:
            if entry["expires_at"] > time.time():
                return entry["data"]
            else:
                del self._in_memory_store[key]

        return None

    async def set(self, key: str, domain: str, data: Dict[str, Any]) -> None:
        if not self.settings.CACHE_ENABLED:
            return

        ttl = self._get_ttl_for_domain(domain)
        serialized = json.dumps(data)

        client = await self.get_redis_client()
        if client:
            try:
                await client.set(key, serialized, ex=ttl)
                return
            except Exception as e:
                if self.settings.ENVIRONMENT in {"staging", "production"} and self.settings.REQUIRE_REDIS:
                    logger.error("Redis cache is required but unavailable")
                    raise RuntimeError("Redis cache unavailable") from e
                logger.warning(f"Redis set error for {key}: {e}. Using memory fallback.")

        if self.settings.ENVIRONMENT in {"staging", "production"} and self.settings.REQUIRE_REDIS:
            raise RuntimeError("Redis cache unavailable")

        # In-memory fallback
        if len(self._in_memory_store) >= self._in_memory_max_items:
            # Purge oldest entries
            oldest_keys = sorted(self._in_memory_store.keys(), key=lambda k: self._in_memory_store[k]["expires_at"])[:100]
            for k in oldest_keys:
                self._in_memory_store.pop(k, None)

        self._in_memory_store[key] = {
            "data": data,
            "expires_at": time.time() + ttl
        }

    async def clear(self) -> None:
        client = await self.get_redis_client()
        if client:
            try:
                keys = await client.keys("ai_cache:*")
                if keys:
                    await client.delete(*keys)
            except Exception:
                pass
        self._in_memory_store.clear()


request_cache = RequestCache()
