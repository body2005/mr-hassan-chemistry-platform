"""Short-lived, operator-signed observations; never an authentication bypass.

Ordinary requests receive no diagnostic headers. A proof can reveal only policy
decisions and keyed fingerprints, not addresses, cookies, credentials or data.
It never supplies an identity to authentication, admission or the rate limiter.
"""
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request

from app.core.config import get_settings

_worker = uuid.uuid4().hex[:16]


def _fingerprint(value: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), ('rate-proof-fingerprint:' + value).encode(),
                    hashlib.sha256).hexdigest()[:24]


def _address(value: str | None) -> str | None:
    try:
        return str(ipaddress.ip_address(value)) if value and len(value) <= 45 else None
    except ValueError:
        return None


def _authorized(value: str | None) -> bool:
    if not value or len(value) > 128:
        return False
    try:
        audit, expires, signature = value.split('.')
        if uuid.UUID(hex=audit).hex != audit or not expires.isdecimal():
            return False
        remaining = int(expires) - time.time()
        if not 0 < remaining <= 1800:
            return False
        expected = hmac.new(get_settings().secret_key.encode(),
                            f'rate-limit-proof-v1:{audit}.{expires}'.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, OverflowError):
        return False


def observe_policy(request: Request, *, category: str, key: str, limit: int,
                   window: int, backend: str, allowed: bool) -> None:
    proof = getattr(request.state, 'rate_limit_proof', None)
    if isinstance(proof, dict) and len(proof['policies']) < 8:
        proof['policies'].append({'category': category, 'limit': limit, 'window': window,
                                 'backend': backend, 'allowed': allowed, 'key': _fingerprint(key)})


class RateLimitProofMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        if not _authorized(headers.get('X-RateLimit-Proof')):
            return await self.app(scope, receive, send)
        from app.core.rate_limit import resolve_client_ip

        request = Request(scope)
        resolved = resolve_client_ip(request)
        peer = _address(request.client.host) if request.client else None
        claimed = _address(headers.get('X-Proof-Expected-IP'))
        raw_hops = headers.get('X-Forwarded-For', '')
        hops = [_address(value.strip()) for value in raw_hops.split(',')[:16]] if len(raw_hops) <= 2048 else []
        cf = _address(headers.get('CF-Connecting-IP'))
        vercel = _address(headers.get('X-Vercel-Forwarded-For'))
        proof = {'worker': _worker,
                 'instance': _fingerprint(os.getenv('RENDER_INSTANCE_ID', os.getenv('HOSTNAME', 'local'))),
                 'revision': os.getenv('RENDER_GIT_COMMIT', '')[:40],
                 'client': _fingerprint('ip:' + resolved),
                 'peer': _fingerprint('ip:' + peer) if peer else None,
                 'peer_private': ipaddress.ip_address(peer).is_private if peer else None,
                 'expected_match': resolved == claimed if claimed else None,
                 'expected_hops': [i for i, hop in enumerate(hops) if claimed and hop == claimed],
                 'forwarded': [_fingerprint('ip:' + hop) if hop else None for hop in hops],
                 'cf': _fingerprint('ip:' + cf) if cf else None,
                 'vercel': _fingerprint('ip:' + vercel) if vercel else None,
                 'policies': []}
        request.state.rate_limit_proof = proof

        async def observed_send(message):
            if message['type'] == 'http.response.start':
                proof['status'] = message['status']
                timings = getattr(request.state, 'request_timings', None)
                if isinstance(timings, dict):
                    proof['timings'] = {key: round(value, 2) for key, value in timings.items()}
                encoded = base64.urlsafe_b64encode(json.dumps(proof, separators=(',', ':')).encode()).decode()
                outgoing = MutableHeaders(scope=message)
                outgoing['X-RateLimit-Proof'] = encoded
                outgoing['Cache-Control'] = 'private, no-store'
            await send(message)

        await self.app(scope, receive, observed_send)
