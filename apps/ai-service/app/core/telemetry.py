import threading
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional
import numpy as np


class TelemetryCollector:
    """
    Thread-safe collector for real-time service metrics:
    - Request counts by domain, endpoint, and status
    - Latency distribution (p50, p95, p99, avg)
    - Token spend (prompt & completion tokens) for external APIs
    - Active local GPU/VRAM inference load
    - Cache hit & miss rates
    - Queue depths
    """

    def __init__(self, max_history_size: int = 1000):
        self._lock = threading.Lock()
        self._max_history = max_history_size

        self.requests_total: Dict[str, int] = defaultdict(int)
        self.errors_total: Dict[str, int] = defaultdict(int)
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.active_gpu_inferences: int = 0

        # Token accounting
        self.tokens_prompt_total: Dict[str, int] = defaultdict(int)
        self.tokens_completion_total: Dict[str, int] = defaultdict(int)

        # Rolling latencies (in milliseconds) per domain/endpoint
        self._latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self._max_history))

    def record_request(
        self,
        domain: str,
        endpoint: str,
        status_code: int,
        duration_ms: float,
        cached: bool = False,
        provider: Optional[str] = None
    ) -> None:
        with self._lock:
            key = f"{domain}:{endpoint}:{status_code}"
            self.requests_total[key] += 1
            self.requests_total[f"domain:{domain}"] += 1
            self.requests_total["total"] += 1

            if cached:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

            if status_code >= 400:
                self.errors_total[f"{status_code}:{domain}"] += 1

            self._latencies[domain].append(duration_ms)
            self._latencies["all"].append(duration_ms)

    def record_error(self, error_type: str, domain: str) -> None:
        with self._lock:
            self.errors_total[f"{error_type}:{domain}"] += 1

    def record_tokens(self, provider: str, prompt_tokens: int, completion_tokens: int) -> None:
        with self._lock:
            self.tokens_prompt_total[provider] += prompt_tokens
            self.tokens_completion_total[provider] += completion_tokens

    def set_active_gpu_inferences(self, count: int) -> None:
        with self._lock:
            self.active_gpu_inferences = max(0, count)

    def increment_active_gpu(self) -> None:
        with self._lock:
            self.active_gpu_inferences += 1

    def decrement_active_gpu(self) -> None:
        with self._lock:
            self.active_gpu_inferences = max(0, self.active_gpu_inferences - 1)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            latency_stats: Dict[str, Any] = {}
            for key, samples in self._latencies.items():
                if samples:
                    arr = np.array(list(samples))
                    latency_stats[key] = {
                        "count": len(arr),
                        "avg_ms": round(float(np.mean(arr)), 2),
                        "p50_ms": round(float(np.percentile(arr, 50)), 2),
                        "p95_ms": round(float(np.percentile(arr, 95)), 2),
                        "p99_ms": round(float(np.percentile(arr, 99)), 2),
                        "min_ms": round(float(np.min(arr)), 2),
                        "max_ms": round(float(np.max(arr)), 2),
                    }
                else:
                    latency_stats[key] = {"count": 0}

            total_cache_ops = self.cache_hits + self.cache_misses
            cache_hit_rate = round(self.cache_hits / total_cache_ops, 4) if total_cache_ops > 0 else 0.0

            return {
                "requests": {
                    "total": self.requests_total.get("total", 0),
                    "breakdown": dict(self.requests_total),
                },
                "errors": dict(self.errors_total),
                "cache": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_rate": cache_hit_rate,
                },
                "resource_load": {
                    "active_local_gpu_inferences": self.active_gpu_inferences,
                },
                "tokens": {
                    "prompt_tokens_by_provider": dict(self.tokens_prompt_total),
                    "completion_tokens_by_provider": dict(self.tokens_completion_total),
                    "total_tokens": sum(self.tokens_prompt_total.values()) + sum(self.tokens_completion_total.values()),
                },
                "latency_ms": latency_stats,
            }


telemetry = TelemetryCollector()
