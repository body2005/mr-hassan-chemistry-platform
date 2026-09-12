"""Controlled virtual-user load test for the deployed API.

Uploads are disabled by default.  See README.md in this directory before
running against production.
"""
from __future__ import annotations

import io
import os
import threading
import uuid

from locust import HttpUser, between, task


_TOKEN_LOCK = threading.Lock()
_SHARED_TOKEN = os.getenv("LOAD_TEST_TOKEN", "").strip()


def _token_for(client) -> str:
    global _SHARED_TOKEN
    if _SHARED_TOKEN:
        return _SHARED_TOKEN

    with _TOKEN_LOCK:
        if _SHARED_TOKEN:
            return _SHARED_TOKEN
        email = os.getenv("LOAD_TEST_EMAIL", "").strip()
        password = os.getenv("LOAD_TEST_PASSWORD", "")
        institution = os.getenv("LOAD_TEST_INSTITUTION", "demo").strip()
        if not email or not password:
            raise RuntimeError(
                "Set LOAD_TEST_TOKEN, or set LOAD_TEST_EMAIL and LOAD_TEST_PASSWORD."
            )
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password,
                "institution_slug": institution,
            },
            name="POST /auth/login [setup]",
        )
        if response.status_code != 200:
            raise RuntimeError(f"Load-test login failed: HTTP {response.status_code}")
        _SHARED_TOKEN = response.json()["token"]
        return _SHARED_TOKEN


class ChemistryPlatformUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        token = _token_for(self.client)
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(8)
    def current_user(self) -> None:
        self.client.get("/api/v1/auth/me", name="GET /auth/me")

    @task(6)
    def courses(self) -> None:
        self.client.get("/api/v1/courses?page=1&page_size=20", name="GET /courses")

    @task(4)
    def notifications(self) -> None:
        self.client.get("/api/v1/notifications", name="GET /notifications")

    @task(3)
    def knowledge_sources(self) -> None:
        self.client.get(
            "/api/v1/knowledge-center/sources?page=1&page_size=20",
            name="GET /knowledge-center/sources",
        )

    @task(2)
    def submissions(self) -> None:
        self.client.get("/api/v1/submissions", name="GET /submissions")

    @task(1)
    def optional_small_upload(self) -> None:
        if os.getenv("LOAD_TEST_ENABLE_UPLOADS", "0").lower() not in {"1", "true", "yes"}:
            return
        course_id = os.getenv("LOAD_TEST_COURSE_ID", "").strip()
        if not course_id:
            return
        payload = ("virtual load test\n" * 1024).encode("utf-8")
        filename = f"load_test_{uuid.uuid4().hex}.txt"
        self.client.post(
            "/api/v1/knowledge-center/sources/upload",
            data={"course_id": course_id, "source_role": "KNOWLEDGE"},
            files={"file": (filename, io.BytesIO(payload), "text/plain")},
            name="POST /knowledge-center/sources/upload [small]",
        )
