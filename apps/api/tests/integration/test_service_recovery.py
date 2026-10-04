"""One service outage at a time, real authenticated traffic, unconditional recovery."""
import json
import time
import pytest
import requests
from .live_helpers import BASE, container, session, wait_until


@pytest.mark.parametrize("service", ["postgres", "redis", "s3", "worker", "mailpit", "web", "proxy"])
def test_service_failure_and_recovery(service):
    target = container(service)
    with session() as teacher:
        before = teacher.get(f"{BASE}/courses", timeout=15)
        assert before.status_code == 200
        course_ids = {item["id"] for item in before.json()["items"]}
        status = None
        elapsed = 0
        try:
            target.stop(timeout=2)
            start = time.monotonic()
            if service == "s3":
                from pathlib import Path
                data = json.loads(Path("/qa/storage-checkpoint.json").read_text())
                path = f"lessons/{data['video_lesson']}/materials/{data['material_id']}/download"
                status = teacher.get(f"{BASE}/{path}", timeout=30).status_code
                assert status == 503, f"Object-store outage misreported as {status}"
            elif service == "mailpit":
                response = teacher.post(f"{BASE}/auth/password-reset/request", json={"email": "teacher@demo.com",
                                                                 "institution_slug": "demo"}, timeout=20)
                status = response.status_code
                # Deliberately generic even when mail fails: 503 only for
                # existing users would disclose which email addresses exist.
                assert status == 200, response.text
                assert b"Password reset email delivery failed" in container("api").logs(tail=40)
            elif service == "proxy":
                with pytest.raises(requests.RequestException):
                    teacher.get(f"{BASE}/courses", timeout=10)
                status = "connection_error"
            else:
                response = teacher.get(f"{BASE}/courses", timeout=30)
                status = response.status_code
                # A missing Docker DNS record returns 502; a cached IP whose
                # connection times out returns 504. Both are bounded gateway
                # failures, never a silent success or an application 500.
                expected = {"postgres": {503}, "redis": {503}, "worker": {200}, "web": {502, 504}}[service]
                assert status in expected, response.text
            elapsed = time.monotonic() - start
        finally:
            target.start()
            recovery_evidence = {}
            def recovered():
                try:
                    probe = teacher.get(f"{BASE}/ready", timeout=6)
                    recovery_evidence.update(status=probe.status_code, body=probe.json())
                    return probe.status_code == 200 and probe.json().get('status') == 'ready'
                except (requests.RequestException, ValueError) as exc:
                    recovery_evidence.update(status=type(exc).__name__)
                    return False
            try:
                wait_until(recovered, 75)
            finally:
                print(json.dumps({'service': service, 'last_readiness': recovery_evidence}))
        response = teacher.get(f"{BASE}/courses", timeout=15)
        assert response.status_code == 200
        assert {item["id"] for item in response.json()["items"]} == course_ids
        print(json.dumps({"service": service, "during_status": status, "seconds": round(elapsed, 3),
                          "recovered": True, "course_ids_unchanged": True}))
