import pytest
from app.core.telemetry import TelemetryCollector


def test_telemetry_collector_aggregates_metrics():
    collector = TelemetryCollector()

    # Record normal requests
    collector.record_request("quiz", "POST:/quiz/draft", 200, 150.0, cached=False)
    collector.record_request("quiz", "POST:/quiz/draft", 200, 250.0, cached=True)
    collector.record_request("tutor", "POST:/tutor/chat", 200, 300.0, cached=False)
    collector.record_request("grading", "POST:/grading/essay", 503, 50.0, cached=False)

    # Record token usage
    collector.record_tokens("external_api", prompt_tokens=500, completion_tokens=150)
    collector.record_tokens("ollama", prompt_tokens=200, completion_tokens=50)

    # GPU tracking
    collector.increment_active_gpu()
    assert collector.active_gpu_inferences == 1
    collector.decrement_active_gpu()
    assert collector.active_gpu_inferences == 0

    summary = collector.get_summary()

    assert summary["requests"]["total"] == 4
    assert summary["cache"]["hits"] == 1
    assert summary["cache"]["misses"] == 3
    assert summary["cache"]["hit_rate"] == 0.25
    assert summary["errors"]["503:grading"] == 1
    assert summary["tokens"]["total_tokens"] == 900
    assert summary["latency_ms"]["quiz"]["avg_ms"] == 200.0
    assert summary["latency_ms"]["quiz"]["count"] == 2
