from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import rate_limit
from app.core.config import get_settings
from app.main import classify_rate_limit_category


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/api/v1/lessons/lesson-id/materials", "upload"),
        ("POST", "/api/v1/lessons/lesson-id/video", "upload"),
        ("POST", "/api/v1/orders/order-id/receipt", "upload"),
        ("POST", "/api/v1/ai/chat", "ai"),
        ("POST", "/api/v1/quiz/extract-from-file", "quiz_extraction"),
        ("PATCH", "/api/v1/courses/course-id", "mutation"),
    ],
)
def test_rate_limit_request_classification(method: str, path: str, expected: str) -> None:
    assert classify_rate_limit_category(method, path) == expected


def _request(*, categories: set[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(rate_limit_categories=categories or set()),
        cookies={},
        headers={},
        client=SimpleNamespace(host="198.51.100.20"),
    )


def test_endpoint_does_not_charge_upload_twice_after_middleware() -> None:
    request = _request(categories={"upload"})
    # The middleware has already charged the upload bucket for this request.
    # The route-level guard must not consume it again.
    rate_limit.enforce_rate_limit(request, category="upload", limit=1, window_seconds=60)


def test_required_redis_fails_closed_without_memory_fallback(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "redis_required", True)
    monkeypatch.setattr(rate_limit, "_get_redis_client", lambda: None)

    with pytest.raises(HTTPException) as exc_info:
        rate_limit.enforce_rate_limit(_request(), category="read", limit=1, window_seconds=60)

    assert exc_info.value.status_code == 503
    assert "Rate limiting" in str(exc_info.value.detail)
    assert exc_info.value.headers["Retry-After"] == "1"
