import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.response_security import ResponseSecurityHeadersMiddleware
from app.main import app


@pytest.mark.parametrize('status', [200, 401, 403, 413, 429, 503])
@pytest.mark.parametrize('secure', [True, False])
def test_early_and_streaming_responses_keep_security_headers_without_body_buffering(status, secure):
    emitted = []

    async def endpoint(scope, receive, send):
        await send({'type': 'http.response.start', 'status': status,
                    'headers': [(b'access-control-allow-origin', b'https://qa.example.com'),
                                (b'retry-after', b'3')]})
        await send({'type': 'http.response.body', 'body': b'first', 'more_body': True})
        assert emitted[-1]['body'] == b'first', 'Must forward a stream chunk immediately'
        await send({'type': 'http.response.body', 'body': b'last'})

    async def receive():
        return {'type': 'http.request', 'body': b''}

    async def send(message):
        emitted.append(message)

    asyncio.run(ResponseSecurityHeadersMiddleware(endpoint, secure=secure)(
        {'type': 'http'}, receive, send))
    headers = dict(emitted[0]['headers'])
    assert headers[b'x-content-type-options'] == b'nosniff'
    assert headers[b'x-frame-options'] == b'SAMEORIGIN'
    assert headers[b'access-control-allow-origin'] == b'https://qa.example.com'
    assert headers[b'retry-after'] == b'3'
    assert (b'strict-transport-security' in headers) == secure
    assert (b'content-security-policy' in headers) == secure
    assert [message.get('body') for message in emitted[1:]] == [b'first', b'last']


def test_actual_early_rate_limit_response_is_not_missing_base_security_headers(monkeypatch):
    from app import main

    def reject(*args, **kwargs):
        raise HTTPException(429, 'Synthetic early admission rejection', headers={'Retry-After': '7'})

    monkeypatch.setattr(main, 'enforce_rate_limit', reject)
    with TestClient(app) as client:
        result = client.get('/api/v1/courses')
    assert result.status_code == 429
    assert result.headers['Retry-After'] == '7'
    assert result.headers['X-Content-Type-Options'] == 'nosniff'
    assert result.headers['X-Frame-Options'] == 'SAMEORIGIN'


def test_successful_cors_preflight_keeps_base_headers_and_origin_policy():
    with TestClient(app) as client:
        result = client.options('/api/v1/courses', headers={
            'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'X-CSRF-Token'})
    assert result.status_code == 200
    assert result.headers['Access-Control-Allow-Origin'] == 'http://localhost:5173'
    assert result.headers['X-Content-Type-Options'] == 'nosniff'
    assert result.headers['X-Frame-Options'] == 'SAMEORIGIN'
