import os

import pytest
import requests


API_BASE = "http://127.0.0.1:8000/api/v1"


def test_live_login_rate_limit_returns_retry_after():
    """Opt-in live-service abuse check; never performs requests at collection."""
    api_base = os.getenv("LIVE_API_BASE", API_BASE).rstrip("/")
    try:
        requests.get(f"{api_base.removesuffix('/api/v1')}/health", timeout=2).raise_for_status()
    except requests.RequestException as exc:
        pytest.skip(f"Live API is unavailable: {exc}")

    got_429 = False
    retry_after_val = None
    for i in range(1, 25):
        response = requests.post(
            f"{api_base}/auth/login",
            json={"email": f"fake_{i}@chemistry.invalid", "password": "wrong"},
            timeout=5,
        )
        if response.status_code == 429:
            got_429 = True
            retry_after_val = response.headers.get("Retry-After")
            break

    assert got_429, "Rate limiter did not return HTTP 429 after 24 invalid logins"
    assert retry_after_val and int(retry_after_val) > 0
