from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import rate_limit
from app.core.config import get_settings
from app.main import classify_rate_limit_category


@pytest.mark.parametrize('path', ['/api/v1/auth/me', '/api/v1/auth/profile-summary', '/api/v1/auth/avatar'])
@pytest.mark.parametrize('method', ['GET', 'HEAD'])
def test_profile_reads_do_not_consume_credential_mutation_budget(method, path):
    assert classify_rate_limit_category(method, path) == 'read'


@pytest.mark.parametrize('path', ['/api/v1/auth/login', '/api/v1/auth/refresh', '/api/v1/auth/logout',
                                  '/api/v1/auth/change-password', '/api/v1/auth/password-reset/request'])
def test_credential_mutations_keep_the_real_auth_budget(path):
    assert classify_rate_limit_category('POST', path) == 'auth'


def test_refresh_has_no_special_relaxed_default(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_login", 15)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
    assert rate_limit._get_category_defaults("auth") == (15, 60)
    assert rate_limit._get_category_defaults("auth_refresh") == (15, 60)


def test_mixed_auth_mutations_share_the_original_budget(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_login", 15)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
    monkeypatch.setattr(settings, "redis_required", False)
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.delenv("DISABLE_RATE_LIMITING", raising=False)
    monkeypatch.setattr(rate_limit, "_get_redis_client", lambda: None)
    # Isolate the unit-test store, not live Redis counters or production limits.
    monkeypatch.setattr(rate_limit, "_windows", rate_limit.defaultdict(rate_limit.deque))
    paths = ["login", "refresh", "logout", "change-password", "password-reset/request"]
    for number in range(15):
        path = paths[number % len(paths)]
        request = _request()
        category = classify_rate_limit_category("POST", f"/api/v1/auth/{path}")
        rate_limit.enforce_rate_limit(request, category=category)
        if path == "refresh":
            # The route's existing 60/min guard must not bypass middleware's 15/min.
            rate_limit.enforce_rate_limit(request, bucket="auth", limit=60, window_seconds=60)
            assert len(request.state.rate_limit_policies) == 2
    with pytest.raises(HTTPException) as exc_info:
        rate_limit.enforce_rate_limit(_request(), category="auth")
    assert exc_info.value.status_code == 429
    assert 1 <= int(exc_info.value.headers["Retry-After"]) <= 60


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/api/v1/lessons/lesson-id/materials", "upload"),
        ("POST", "/api/v1/lessons/lesson-id/video", "upload"),
        ("POST", "/api/v1/orders/order-id/receipt", "upload"),
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
    rate_limit.enforce_rate_limit(request, category="upload", limit=1, window_seconds=60)
    assert len(request.state.rate_limit_policies) == 1


def test_required_redis_fails_closed_without_memory_fallback(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "redis_required", True)
    monkeypatch.setattr(rate_limit, "_get_redis_client", lambda: None)

    with pytest.raises(HTTPException) as exc_info:
        rate_limit.enforce_rate_limit(_request(), category="read", limit=1, window_seconds=60)

    assert exc_info.value.status_code == 503
    assert "Rate limiting" in str(exc_info.value.detail)
    assert exc_info.value.headers["Retry-After"] == "1"
