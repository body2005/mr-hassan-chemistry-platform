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
        if self.headers.get("Authorization"):
            try:
                self.post(f"{BASE}/auth/logout", timeout=10)
            except requests.RequestException:
                pass
            self.headers.pop("Authorization", None)
        super().close()


def isolated():
    if os.getenv("QA_ISOLATED") != "true" or os.getenv("QA_PROJECT") != "chemistryprodlocal":
        raise RuntimeError("Live integration requires the isolated chemistryprodlocal project")


def session(email="teacher@demo.com", password="qa-teacher-pass"):
    isolated()
    result = LiveSession()
    result.verify = os.environ["QA_CA_FILE"]
    response = result.post(f"{BASE}/auth/login", json={"email": email, "password": password,
                                                    "institution_slug": "demo"}, timeout=15)
    assert response.status_code == 200, response.text
    result.headers["Authorization"] = f"Bearer {response.json()['token']}"
    result.headers["X-CSRF-Token"] = result.cookies.get("matgar_csrf", "")
    return result


def clear_auth():
    isolated()
    store = redis.Redis.from_url(os.environ["REDIS_URL"])
    keys = list(store.scan_iter("rate-limit:auth:ip:*"))
    if keys:
        store.unlink(*keys)


def container(service):
    isolated()
    found = docker.from_env().containers.list(all=True, filters={"label": [
        "com.docker.compose.project=chemistryprodlocal", f"com.docker.compose.service={service}"]})
    assert len(found) == 1, f"Expected one isolated {service} container, got {len(found)}"
    return found[0]


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
    assert teacher.post(f"{BASE}/courses/{course['id']}/publish", timeout=15).status_code == 200
    return course, result


def wait_until(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(1)
    raise AssertionError("Timed out waiting for recovery")
