import itertools
import json
import os
from locust import HttpUser, task, between

# Load 100 unique tokens
TOKENS = []
token_path = os.path.join(os.path.dirname(__file__), "locust_users.json")
if os.path.exists(token_path):
    with open(token_path, "r", encoding="utf-8") as f:
        TOKENS = json.load(f).get("tokens", [])

token_iterator = itertools.cycle(TOKENS) if TOKENS else None

class EnrolledStudentUser(HttpUser):
    wait_time = between(1.0, 2.5)

    def on_start(self):
        if token_iterator:
            self.token = next(token_iterator)
        else:
            self.token = ""
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(3)
    def get_current_user_profile(self):
        with self.client.get("/api/v1/auth/me", headers=self.headers, catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                resp.failure("Unexpected 429 Too Many Requests under capacity load!")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def list_courses(self):
        with self.client.get("/api/v1/courses", headers=self.headers, catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                resp.failure("Unexpected 429 Too Many Requests under capacity load!")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def check_health(self):
        with self.client.get("/api/v1/health", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health failed with {resp.status_code}")
