from __future__ import annotations

import threading
import time
from collections import Counter

_lock = threading.Lock()
_requests: Counter[tuple[str, str]] = Counter()
_latency_ms: Counter[str] = Counter()
_started_at = time.time()


def record_request(path: str, method: str, status_code: int, latency_ms: int) -> None:
    with _lock:
        _requests[(method, path)] += 1
        _latency_ms[path] += latency_ms


def render_metrics() -> str:
    lines = [
        "# HELP matgar_process_uptime_seconds Process uptime in seconds",
        "# TYPE matgar_process_uptime_seconds gauge",
        f"matgar_process_uptime_seconds {time.time() - _started_at:.3f}",
        "# TYPE matgar_http_requests_total counter",
    ]
    with _lock:
        for (method, path), count in sorted(_requests.items()):
            safe_path = path.replace('"', '\\"')
            lines.append(
                f'matgar_http_requests_total{{method="{method}",path="{safe_path}"}} {count}'
            )
        lines.append("# TYPE matgar_http_request_latency_ms_total counter")
        for path, total in sorted(_latency_ms.items()):
            safe_path = path.replace('"', '\\"')
            lines.append(f'matgar_http_request_latency_ms_total{{path="{safe_path}"}} {total}')
    return "\n".join(lines) + "\n"
