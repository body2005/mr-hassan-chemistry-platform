"""Real large playback and upstream failure must not leak the signed query.

Assert on all three HTTP hops, including gateway error diagnostics; disabling
access logs alone previously missed Nginx temporary-buffer warning messages.
"""
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

from .live_helpers import BASE, container, operational_logs, session, wait_until


def test_playback_credentials_are_private_during_stream_and_upstream_failure():
    started = int(time.time())
    checkpoint = json.loads(Path('/qa/storage-checkpoint.json').read_text())
    api = container('api')
    with session() as teacher:
        response = teacher.post(f"{BASE}/lessons/{checkpoint['video_lesson']}/video-token", timeout=15)
        assert response.status_code == 200
        path = response.json()['stream_url']
        secret = parse_qs(urlsplit(path).query)['token'][0]
        url = urljoin(BASE.removesuffix('/api/v1') + '/', path)
        response = teacher.get(url, timeout=45)
        assert response.status_code == 200
        assert hashlib.sha256(response.content).hexdigest() == checkpoint['video_sha256']
        try:
            api.stop(timeout=2)
            response = teacher.get(url, headers={'Range': 'bytes=0-1023'}, timeout=15)
            assert response.status_code in (502, 504)
        finally:
            api.start()
            def recovered():
                try:
                    return teacher.get(f'{BASE}/ready', timeout=6).status_code == 200
                except requests.RequestException:
                    return False
            wait_until(recovered, timeout=75)
        response = teacher.get(url, headers={'Range': 'bytes=0-1023'}, timeout=15)
        assert response.status_code == 206
    for name in ('api', 'web', 'proxy'):
        evidence = b'token=[REDACTED]' if name == 'api' else b'/stream HTTP/'
        logs = operational_logs(name, lambda value: evidence in value, since=started).decode(errors='replace')
        assert secret not in logs, f'{name} leaked the playback credential'
        if name == 'api':
            assert 'token=[REDACTED]' in logs
        else:
            assert '/stream HTTP/' in logs
            assert 'upstream=' in logs
