import requests
import os
from .live_helpers import BASE, clear_auth


def test_live_login_rate_limit_returns_retry_after():
    clear_auth()
    try:
        with requests.Session() as client:
            client.verify = os.environ["QA_CA_FILE"]
            assert client.get(f"{BASE}/health", timeout=5).status_code == 200
            statuses = []
            for number in range(24):
                response = client.post(f"{BASE}/auth/login", json={"email": f"fake_{number}@chemistry.invalid",
                                       "password": "wrong", "institution_slug": "demo"}, timeout=10)
                statuses.append(response.status_code)
                if response.status_code == 429:
                    assert int(response.headers["Retry-After"]) > 0
                    break
            assert 429 in statuses, statuses
            assert set(statuses).issubset({401, 429}), statuses
    finally:
        clear_auth()
