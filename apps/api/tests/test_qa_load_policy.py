import pytest
from scripts.qa_load_policy import LoadSafety, percentile


def record(status=200, ms=20, kind='browse'):
    return {'status': status, 'ms': ms, 'kind': kind}


def test_percentiles_use_actual_samples_and_preserve_empty():
    assert percentile([], .95) is None
    assert percentile(list(range(1, 101)), .95) == 95
    assert percentile(list(range(1, 101)), .99) == 99


def test_error_threshold_does_not_hide_429_or_retry_it():
    guard = LoadSafety()
    for _ in range(98):
        guard.request(record())
    guard.request(record(429))
    assert not guard.stopped.is_set()
    guard.request(record('network'))
    assert guard.reason == 'rolling_error_rate_above_1_percent'
    guard.stop('another')
    assert guard.reason == 'rolling_error_rate_above_1_percent'


def test_single_error_at_exact_one_percent_does_not_stop_escalation():
    guard = LoadSafety()
    for _ in range(99):
        guard.request(record())
    guard.request(record(429))
    assert not guard.stopped.is_set()


def test_slow_interactive_window_stops_but_not_large_upload_p95():
    guard = LoadSafety()
    for _ in range(99):
        guard.request(record(ms=2001))
    assert not guard.stopped.is_set()
    guard.request(record())
    assert guard.reason == 'interactive_p95_above_2000ms'
    guard = LoadSafety()
    for _ in range(99):
        guard.request(record())
    guard.request(record(ms=14000, kind='upload'))
    assert not guard.stopped.is_set()
    guard.request(record(ms=15001, kind='upload'))
    assert guard.reason == 'whole_upload_above_15000ms'


@pytest.mark.parametrize('field,value,reason', [
    ('memory_bytes', {'api': 90}, 'memory_above_90_percent:api'),
    ('cpu_percent', {'api': 68}, 'cpu_above_90_percent:api'),
    ('postgres_connections', 80, 'postgres_connections_above_80_percent'),
    ('video_queue_depth', 50, 'video_queue_depth_at_least_50'),
])
def test_actual_resource_limits_require_three_consecutive_samples(field, value, reason):
    guard = LoadSafety()
    limits = {'api': {'memory_bytes': 100, 'cpu_percent': 75}}
    normal = {'memory_bytes': {'api': 10}, 'cpu_percent': {'api': 1},
              'postgres_connections': 10, 'postgres_max_connections': 100, 'video_queue_depth': 0}
    overloaded = {**normal, field: value}
    for _ in range(2):
        guard.resources(overloaded, limits)
    guard.resources(normal, limits)
    assert not guard.stopped.is_set()
    for _ in range(3):
        guard.resources(overloaded, limits)
    assert guard.reason == 'three_consecutive_samples:' + reason


def test_unlimited_cgroup_is_not_mislabeled_as_zero_capacity():
    guard = LoadSafety()
    sample = {'memory_bytes': {'api': 10**12}, 'cpu_percent': {'api': 200},
              'postgres_connections': 5, 'video_queue_depth': 0}
    for _ in range(4):
        guard.resources(sample, {'api': {'memory_bytes': 0, 'cpu_percent': 0}})
    assert not guard.stopped.is_set()


def test_slow_whole_upload_stops_even_before_rolling_window_fills():
    guard = LoadSafety()
    guard.request(record(ms=15001, kind='upload'))
    assert guard.reason == 'whole_upload_above_15000ms'
