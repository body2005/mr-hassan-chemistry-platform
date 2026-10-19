"""Authenticated upstream assertions; arbitrary forwarding headers confer no trust."""
import hashlib
import hmac
import ipaddress
import os
import re
import time


def address(value):
    try:
        return str(ipaddress.ip_address(value)) if value and len(value) <= 45 else None
    except ValueError:
        return None


def asserted_client_ip(request, settings):
    secret = getattr(settings, 'proxy_assertion_secret', None)
    secret = secret.get_secret_value() if secret else None
    if not secret:
        return None
    headers = request.headers
    raw = headers.get('X-Chemistry-Client-IP', '')
    stamp = headers.get('X-Chemistry-Client-Time', '')
    signature = headers.get('X-Chemistry-Client-Signature', '')
    normalized = address(raw)
    if not normalized or not re.fullmatch(r'\d{10}', stamp) or not re.fullmatch(r'[0-9a-f]{64}', signature):
        return None
    age = time.time() - int(stamp)
    if not -5 <= age <= 60:
        return None
    path = request.scope.get('raw_path', request.url.path.encode()).decode('ascii', errors='replace')
    query = request.scope.get('query_string', b'').decode('ascii', errors='replace')
    target = path + ('?' + query if query else '')
    payload = f'client-ip-v1\n{stamp}\n{request.method.upper()}\n{target}\n{raw}'
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return normalized if hmac.compare_digest(signature, expected) else None


def render_client_ip(request, settings):
    # Opt-in contract: Render's Cloudflare edge overwrites this header, and
    # the native service's immediate socket is its loopback proxy. No generic
    # private CIDRs, XFF-leftmost, Vercel header or claimed Host are trusted.
    if getattr(settings, 'client_ip_mode', 'proxy_chain') != 'render' or os.getenv('RENDER') != 'true':
        return None
    peer = address(request.client.host) if request.client else None
    if not peer or not ipaddress.ip_address(peer).is_loopback:
        return None
    return address(request.headers.get('CF-Connecting-IP'))
