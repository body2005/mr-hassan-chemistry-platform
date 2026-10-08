"""One service outage at a time, real authenticated traffic, unconditional recovery."""
import json
import time
import pytest
import requests
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.mail_outbox import ResetMailOutbox
from app.models.user import PasswordResetToken
from .live_helpers import BASE, container, session, wait_until, pg_engine, operational_logs, clear_auth


@pytest.mark.parametrize("service", ["postgres", "redis", "s3", "worker", "mailpit", "web", "proxy"])
def test_service_failure_and_recovery(service):
    clear_auth()
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
                engine = pg_engine()
                user_id = uuid.UUID(teacher.get(f'{BASE}/auth/me', timeout=10).json()['id'])
                with Session(engine) as db:
                    previous_jobs = set(db.scalars(select(ResetMailOutbox.id).join(PasswordResetToken,
                        PasswordResetToken.id == ResetMailOutbox.token_id).where(PasswordResetToken.user_id == user_id)))
                response = teacher.post(f"{BASE}/auth/password-reset/request", json={"email": "teacher@demo.com",
                                                                 "institution_slug": "demo"}, timeout=20)
                status = response.status_code
                # Deliberately generic even when mail fails: 503 only for
                # existing users would disclose which email addresses exist.
                assert status == 200, response.text
                # Delivery is no longer synchronous in HTTP. Require durable
                # PostgreSQL retry evidence instead of an immediate SMTP log.
                def deferred():
                    with Session(engine) as db:
                        job = db.scalar(select(ResetMailOutbox).join(PasswordResetToken,
                            PasswordResetToken.id == ResetMailOutbox.token_id).where(
                            PasswordResetToken.user_id == user_id, ResetMailOutbox.id.not_in(previous_jobs)))
                        if job and job.attempts > 0:
                            assert job.completed_at is None and job.encrypted_token
                            return job.id
                    return None
                wait_until(deferred, 45)
                mail_job_id = deferred()
                operational_logs('api', lambda logs: b'Reset mail delivery deferred' in logs)
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
                if service == 'postgres':
                    startup = teacher.get(f'{BASE}/bootstrap', timeout=15)
                    assert startup.status_code == 503, 'DB outage must not become guest success or auth expiry'
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
        if service == 'postgres':
            startup = teacher.get(f'{BASE}/bootstrap', timeout=15)
            assert startup.status_code == 200 and startup.json()['authenticated'] is True
        if service == 'mailpit':
            try:
                def delivered():
                    with Session(engine) as db:
                        job = db.get(ResetMailOutbox, mail_job_id)
                        return job.completed_at is not None and job.encrypted_token is None
                wait_until(delivered, 75)
            finally:
                engine.dispose()
        print(json.dumps({"service": service, "during_status": status, "seconds": round(elapsed, 3),
                          "recovered": True, "course_ids_unchanged": True}))
