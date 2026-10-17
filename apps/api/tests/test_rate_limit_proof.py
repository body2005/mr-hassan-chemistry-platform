import base64
import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.config import get_settings
from app.main import app


def signature(*, expiry=None):
    audit = uuid.uuid4().hex
    expires = str(int(time.time()) + 60 if expiry is None else expiry)
    mac = hmac.new(get_settings().secret_key.encode(),
                   f'rate-limit-proof-v1:{audit}.{expires}'.encode(), hashlib.sha256).hexdigest()
    return f'{audit}.{expires}.{mac}'


@pytest.fixture
def local_limiter(monkeypatch):
    monkeypatch.setattr(get_settings(), 'redis_required', False)
    monkeypatch.setattr(get_settings(), 'trusted_proxies', '127.0.0.1,::1')
    monkeypatch.setattr(rate_limit, '_get_redis_client', lambda: None)


@pytest.mark.parametrize('kind', ['missing', 'invalid', 'expired', 'too_far_ahead'])
def test_no_proof_for_unsigned_tampered_or_expired_requests(local_limiter, kind):
    value = {'missing': None, 'invalid': signature()[:-1] + 'Z',
             'expired': signature(expiry=int(time.time()) - 1),
             'too_far_ahead': signature(expiry=int(time.time()) + 1805)}[kind]
    headers = {'X-RateLimit-Proof': value} if value else {}
    response = TestClient(app).get('/api/v1/auth/me', headers=headers)
    assert response.status_code == 401
    assert 'X-RateLimit-Proof' not in response.headers


def test_signed_observation_never_authenticates_or_uses_claimed_ip(local_limiter):
    client = TestClient(app, client=('198.51.100.8', 12345))
    response = client.get('/api/v1/auth/me', headers={
        'X-RateLimit-Proof': signature(), 'X-Proof-Expected-IP': '203.0.113.99',
        'X-Forwarded-For': '203.0.113.99', 'Cookie': 'private-test-cookie=value'})
    assert response.status_code == 401
    proof = json.loads(base64.urlsafe_b64decode(response.headers['X-RateLimit-Proof']))
    assert proof['expected_match'] is False
    assert proof['client'] == proof['peer']
    assert proof['policies'][0]['backend'] == 'memory'
    assert proof['policies'][0]['allowed'] is True
    assert response.headers['Cache-Control'] == 'private, no-store'
    payload = json.dumps(proof)
    for private in [get_settings().secret_key, '198.51.100.8', '203.0.113.99', 'private-test-cookie']:
        assert private not in payload


def test_valid_proof_preserves_429_and_retry_after(local_limiter, monkeypatch):
    monkeypatch.setattr(get_settings(), 'rate_limit_read', 1)
    client = TestClient(app, client=('192.0.2.47', 12345))
    headers = {'X-RateLimit-Proof': signature()}
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 401
    denied = client.get('/api/v1/auth/me', headers=headers)
    assert denied.status_code == 429
    assert int(denied.headers['Retry-After']) > 0
    proof = json.loads(base64.urlsafe_b64decode(denied.headers['X-RateLimit-Proof']))
    assert proof['status'] == 429 and proof['policies'][0]['allowed'] is False
    assert proof['policies'][0]['limit'] == 1
