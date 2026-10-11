"""Pure, bounded safety checks for QA load; never modifies runtime limits."""
from collections import deque
import math
import threading


def percentile(values, q):
    return round(sorted(values)[max(0, math.ceil(len(values) * q) - 1)], 2) if values else None


class LoadSafety:
    """Stop new work on sustained overload; finish already in-flight requests.

    Interactive latency excludes whole large-file uploads. The latter have a
    separate 15s budget. A rolling 100-request window avoids a one-sample p95
    claim; all errors still fail the final gate even below the stop threshold.
    Resource limits are the ACTUAL cgroup and PostgreSQL limits, not inferred
    from host RAM or a supposed application-pool utilization percentage.
    """
    def __init__(self):
        self.stopped = threading.Event()
        self.reason = None
        self.lock = threading.Lock()
        self.records = deque(maxlen=100)
        self.sustained = {}

    def stop(self, reason):
        with self.lock:
            if self.reason is None:
                self.reason = reason
                self.stopped.set()

    def request(self, record):
        with self.lock:
            self.records.append(record)
            if self.reason is None and record['kind'] == 'upload' and record['ms'] > 15000:
                self.reason = 'whole_upload_above_15000ms'
                self.stopped.set()
            if len(self.records) < 100 or self.reason is not None:
                return
            errors = sum(not isinstance(r['status'], int) or r['status'] >= 400 for r in self.records)
            interactive = [r['ms'] for r in self.records if r['kind'] in ('browse', 'video')]
            reason = None
            if errors / len(self.records) > .01:
                reason = 'rolling_error_rate_above_1_percent'
            elif len(interactive) >= 50 and percentile(interactive, .95) > 2000:
                reason = 'interactive_p95_above_2000ms'
            if reason:
                self.reason = reason
                self.stopped.set()

    def resources(self, sample, limits):
        breaches = set()
        for service, limit in limits.items():
            memory = limit.get('memory_bytes', 0)
            cpu = limit.get('cpu_percent', 0)
            if memory and sample['memory_bytes'].get(service, 0) >= .9 * memory:
                breaches.add('memory_above_90_percent:' + service)
            value = sample['cpu_percent'].get(service)
            if cpu and value is not None and value >= .9 * cpu:
                breaches.add('cpu_above_90_percent:' + service)
        maximum = sample.get('postgres_max_connections', 0)
        if maximum and sample.get('postgres_connections', 0) >= .8 * maximum:
            breaches.add('postgres_connections_above_80_percent')
        if sample.get('video_queue_depth', 0) >= 50:
            breaches.add('video_queue_depth_at_least_50')
        with self.lock:
            for name in set(self.sustained) | breaches:
                self.sustained[name] = self.sustained.get(name, 0) + 1 if name in breaches else 0
            if self.reason is None:
                for name, count in sorted(self.sustained.items()):
                    if count >= 3:
                        self.reason = 'three_consecutive_samples:' + name
                        self.stopped.set()
                        break
