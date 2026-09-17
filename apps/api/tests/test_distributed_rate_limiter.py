from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.core.rate_limit import (
    enforce_rate_limit,
    reset_rate_limits,
    resolve_client_ip,
    resolve_rate_limit_key,
)
from app.core.security import create_session_token
from app.models.institution import Institution
from app.models.user import User, UserRole


def test_resolve_client_ip_direct():
    request = MagicMock(spec=Request)
    request.client = MagicMock(host="203.0.113.10")
    request.headers = {}

    ip = resolve_client_ip(request)
    assert ip == "203.0.113.10"


def test_resolve_client_ip_trusted_proxy_forwarded():
    request = MagicMock(spec=Request)
    request.client = MagicMock(host="127.0.0.1")  # default trusted
    request.headers = {"X-Forwarded-For": "198.51.100.5, 127.0.0.1"}

    ip = resolve_client_ip(request)
    assert ip == "198.51.100.5"


def test_resolve_client_ip_untrusted_proxy_spoof_ignored():
    request = MagicMock(spec=Request)
    request.client = MagicMock(host="203.0.113.50")  # untrusted caller
    request.headers = {"X-Forwarded-For": "198.51.100.5"}

    ip = resolve_client_ip(request)
    # Must use untrusted caller IP, ignoring spoofed X-Forwarded-For header
    assert ip == "203.0.113.50"


def test_resolve_client_ip_supports_trusted_proxy_cidr(monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8")
    request = MagicMock(spec=Request)
    request.client = MagicMock(host="10.1.2.3")
    request.headers = {"X-Forwarded-For": "198.51.100.5, 10.2.3.4"}

    assert resolve_client_ip(request) == "198.51.100.5"


def test_resolve_client_ip_uses_explicit_wildcard_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "*")
    request = MagicMock(spec=Request)
    request.client = MagicMock(host="10.1.2.3")
    request.headers = {"X-Forwarded-For": "198.51.100.5, 10.2.3.4"}

    assert resolve_client_ip(request) == "198.51.100.5"


def test_resolve_rate_limit_key_guest():
    request = MagicMock(spec=Request)
    request.cookies = {}
    request.headers = {}
    request.client = MagicMock(host="198.51.100.20")

    key = resolve_rate_limit_key(request, "read")
    assert key == "rate-limit:read:ip:198.51.100.20"


def test_resolve_rate_limit_key_authenticated_user():
    institution_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        institution_id=institution_id,
        role=UserRole.STUDENT,
        username="teststudent",
        email="test@student.com",
        display_name="Student",
        password_hash="hash",
    )
    token = create_session_token(user)

    request = MagicMock(spec=Request)
    request.cookies = {}
    request.headers = {"Authorization": f"Bearer {token}"}
    request.client = MagicMock(host="198.51.100.20")

    key = resolve_rate_limit_key(request, "read")
    assert key == f"rate-limit:read:{institution_id}:{user_id}"


def test_rate_limit_enforce_and_429():
    reset_rate_limits()
    request = MagicMock(spec=Request)
    request.cookies = {}
    request.headers = {}
    request.client = MagicMock(host="198.51.100.99")

    # Limit 3 requests in 60s
    for _ in range(3):
        enforce_rate_limit(request, category="test_cat", limit=3, window_seconds=60)

    # 4th request must raise HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        enforce_rate_limit(request, category="test_cat", limit=3, window_seconds=60)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) > 0


def test_rate_limit_distinct_authenticated_users_do_not_collide():
    reset_rate_limits()
    inst_id = uuid.uuid4()
    u1 = User(id=uuid.uuid4(), institution_id=inst_id, role=UserRole.STUDENT, username="u1", email="u1@s.com", display_name="U1", password_hash="h")
    u2 = User(id=uuid.uuid4(), institution_id=inst_id, role=UserRole.STUDENT, username="u2", email="u2@s.com", display_name="U2", password_hash="h")

    t1 = create_session_token(u1)
    t2 = create_session_token(u2)

    req1 = MagicMock(spec=Request)
    req1.cookies = {}
    req1.headers = {"Authorization": f"Bearer {t1}"}
    req1.client = MagicMock(host="10.0.0.1")

    req2 = MagicMock(spec=Request)
    req2.cookies = {}
    req2.headers = {"Authorization": f"Bearer {t2}"}
    req2.client = MagicMock(host="10.0.0.1")  # same client host!

    # u1 exhausts their limit (limit=2)
    enforce_rate_limit(req1, category="shared", limit=2, window_seconds=60)
    enforce_rate_limit(req1, category="shared", limit=2, window_seconds=60)
    with pytest.raises(HTTPException):
        enforce_rate_limit(req1, category="shared", limit=2, window_seconds=60)

    # u2 has distinct bucket, so u2 is NOT blocked even from same client IP!
    enforce_rate_limit(req2, category="shared", limit=2, window_seconds=60)
    enforce_rate_limit(req2, category="shared", limit=2, window_seconds=60)
