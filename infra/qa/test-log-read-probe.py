"""Read-only diagnostic; mount under /srv/tests/integration for pytest context."""
import json
import time
import uuid
from tests.integration.live_helpers import BASE, container
import requests
import os


def test_log_read_probe():
    api = container("api")
    nonce = uuid.uuid4().hex
    r = requests.get(f"{BASE}/ready?qa_log_probe={nonce}", verify=os.environ["QA_CA_FILE"], timeout=15)
    assert r.status_code == 200
    time.sleep(1)
    buffered = api.logs(tail='all', timestamps=True)
    data = b''.join(api.logs(tail='all', timestamps=True, stream=True, follow=False))
    print(json.dumps({"api_id": api.id, "base": BASE,
        "buffered_bytes": len(buffered), "buffered_probe_found": nonce.encode() in buffered,
        "drained_bytes": len(data), "drained_probe_found": nonce.encode() in data,
        "access_count": data.count(b"HTTP/")}))
    assert nonce.encode() in data
