from __future__ import annotations
import os
import time
import uuid

import docker
import redis
import requests
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

BASE = os.getenv("LIVE_API_BASE", "https://proxy/api/v1").rstrip("/")


class LiveSession(requests.Session):
    def close(self):
        # Closing the TCP session is NOT logging out. Clean up through the
        # actual API so repeated drills do not consume video-device slots.
        if self.cookies.get('matgar_session'):
            try:
                self.headers['X-CSRF-Token'] = self.cookies.get('matgar_csrf', '')
                self.post(f"{BASE}/auth/logout", timeout=10)
            except requests.RequestException:
                pass
            self.headers.pop("Authorization", None)
            self.cookies.clear()
        super().close()


def isolated():
    if os.getenv("QA_ISOLATED") != "true" or os.getenv("QA_PROJECT") not in {"chemistryprodlocal", "chemistryaudit2", "chemistryrelease1010"}:
        raise RuntimeError("Live integration requires an explicitly allowlisted isolated QA project")


def session(email="teacher@demo.com", password="qa-teacher-pass"):
    isolated()
    result = LiveSession()
    result.verify = os.environ["QA_CA_FILE"]
    response = result.post(f"{BASE}/auth/login", json={"email": email, "password": password,
                                                    "institution_slug": "demo"}, timeout=15)
    assert response.status_code == 200, response.text
    assert 'token' not in response.json()
    result.headers["X-CSRF-Token"] = result.cookies.get("matgar_csrf", "")
    return result


def clear_auth():
    isolated()
    store = redis.Redis.from_url(os.environ["REDIS_URL"])
    # Shared demo users keep their real rolling limits. Wait between cases;
    # never clear user keys to compensate for the harness reusing identities.
    script = """local ms=0;
      for _,p in ipairs({'rate-limit:auth:*','rate-limit:auth_refresh:*','rate-limit:login_ip:*','rate-limit:login_account:*','rate-limit:login_retry:*'}) do
        for _,k in ipairs(redis.call('KEYS',p)) do
          local cap=string.find(p,'login_retry',1,true) and 4 or (string.find(p,'login_account',1,true) and 15 or 8);
          if redis.call('ZCARD',k)>=cap then ms=math.max(ms,redis.call('PTTL',k)) end
        end
      end; return ms"""
    delay_ms = int(store.eval(script, 0))
    if delay_ms > 305000:
        raise RuntimeError("Unexpected live QA auth window; do not bypass it")
    if delay_ms > 0:
        time.sleep((delay_ms + 100) / 1000)


def container(service):
    isolated()
    found = docker.from_env().containers.list(all=True, filters={"label": [
        f"com.docker.compose.project={os.environ['QA_PROJECT']}", f"com.docker.compose.service={service}",
        "com.docker.compose.oneoff=False"]})
    # One-off compose diagnostic/test processes share the service label, but
    # must never be selected for fault injection against the runtime service.
    assert len(found) == 1, f"Expected one isolated {service} container, got {len(found)}"
    return found[0]


def operational_logs(service, predicate, *, since=None, timeout=10):
    """Wait for Docker's asynchronously collected logs, not just HTTP success.

    Positive evidence is still required. Keep the original since boundary and
    never print raw logs (which a broken app could populate with credentials).
    """
    target = container(service)
    deadline = time.monotonic() + timeout
    logs = b""
    while True:
        options = {"stdout": True, "stderr": True}
        if since is not None:
            options["since"] = since
        else:
            options["tail"] = 5000
        # Drain the finite response; follow=False is essential. This does NOT
        # repair a corrupt daemon JSON log file: missing evidence must fail.
        logs = b''.join(target.logs(stream=True, follow=False, **options))
        if predicate(logs):
            return logs
        if time.monotonic() >= deadline:
            raise AssertionError(f"Missing {service} operational log evidence after {timeout}s; bytes={len(logs)}")
        time.sleep(0.2)


def pg_engine():
    from pathlib import Path
    password = Path(os.environ["DB_PASSWORD_FILE"]).read_text().strip()
    return create_engine(URL.create("postgresql+psycopg", username=os.environ["POSTGRES_USER"],
                                   password=password, host="postgres", database=os.environ["POSTGRES_DB"]),
                         connect_args={"connect_timeout": 3})


def lesson(teacher, kind="article", price=0):
    stamp = uuid.uuid4().hex[:12]
    response = teacher.post(f"{BASE}/courses", json={"code": f"QA{stamp}", "title": f"QA Integration {stamp}"}, timeout=15)
    assert response.status_code == 201, response.text
    course = response.json()
    response = teacher.post(f"{BASE}/courses/{course['id']}/modules", json={"title": "QA Unit", "position": 1}, timeout=15)
    assert response.status_code == 201, response.text
    module = response.json()
    response = teacher.post(f"{BASE}/modules/{module['id']}/lessons", json={"title": "QA Lesson", "kind": kind,
                                                                 "position": 1, "price_egp": price}, timeout=15)
    assert response.status_code == 201, response.text
    result = response.json()
    # LessonResponse deliberately does not expose module_id. Retain the
    # module we created for the actual manager delete route in test cleanup.
    result["module_id"] = module["id"]
    assert teacher.post(f"{BASE}/courses/{course['id']}/publish", timeout=15).status_code == 200
    return course, result


def wait_until(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(1)
    raise AssertionError("Timed out waiting for recovery")
