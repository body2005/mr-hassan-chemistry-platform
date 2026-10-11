"""Real Uvicorn startup, sanitized subprocess env, synthetic values only."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest
from sqlalchemy import create_engine
from app.models import Base

KNOWN_REPOSITORY_DEFAULT = "local-docker-production-secret-key-at-least-32-chars-long"


def runtime_env(tmp_path, app_env, secret):
    # Do not inherit secret-file paths, tokens or application credentials from
    # the QA runner. This process uses its own disposable SQLite database.
    values = {key: os.environ[key] for key in ("PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
              if key in os.environ}
    values.update(PYTHONPATH=str(Path(__file__).resolve().parents[1]), APP_ENV=app_env,
        SECRET_KEY=secret, COOKIE_SECURE="true", DATABASE_URL=f"sqlite:///{tmp_path / 'startup.sqlite'}",
        STORAGE_BACKEND="local", STORAGE_DIR=str(tmp_path / "objects"),
        FRONTEND_ORIGINS="https://qa.example.test", REDIS_URL="redis://127.0.0.1:9/0",
        REDIS_REQUIRED="false", SMTP_HOST="smtp.example.test", SMTP_USER="qa@example.test",
        SMTP_PASSWORD="synthetic-startup-test-only", SMTP_FROM_EMAIL="qa@example.test",
        SMTP_TLS_VERIFY="true", PAYMENT_INSTAPAY_ACCOUNT="synthetic-merchant")
    return values


def command(port=0):
    return [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)]


@pytest.mark.parametrize("app_env", ["production", "production_like", "staging"])
def test_actual_startup_rejects_known_repository_secret(tmp_path, app_env):
    result = subprocess.run(command(), cwd=tmp_path,
        env=runtime_env(tmp_path, app_env, KNOWN_REPOSITORY_DEFAULT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
    assert result.returncode != 0
    assert b"SECRET_KEY must be replaced before production startup" in result.stdout
    assert b"Application startup complete" not in result.stdout


def test_actual_startup_rejects_insecure_cookie_setting(tmp_path):
    env = runtime_env(tmp_path, "production_like", "synthetic-control-secret-not-for-deployment-2026")
    env["COOKIE_SECURE"] = "false"
    result = subprocess.run(command(), cwd=tmp_path, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
    assert result.returncode != 0
    assert b"Secure cookies must remain enabled" in result.stdout


def test_actual_startup_control_serves_health_with_external_test_secret(tmp_path):
    env = runtime_env(tmp_path, "production_like", "synthetic-control-secret-not-for-deployment-2026")
    engine = create_engine(env["DATABASE_URL"])
    Base.metadata.create_all(engine); engine.dispose()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    # This is the internal upstream HTTP socket, not a replacement for the
    # externally required HTTPS reverse proxy or a browser certificate test.
    with (tmp_path / "startup-control.log").open("wb") as log:
        process = subprocess.Popen(command(port), cwd=tmp_path, env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                assert process.poll() is None, "Synthetic control API exited before health"
                try:
                    with urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=0.5) as response:
                        assert response.status == 200
                        return
                except OSError:
                    time.sleep(0.1)
            pytest.fail("Synthetic control API did not start")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
