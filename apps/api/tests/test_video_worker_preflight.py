from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scripts.video_worker_preflight import main


def configure(monkeypatch):
    for key, value in {
        "DATABASE_URL": "postgresql+psycopg://user:private-password@db.example/db?sslmode=require",
        "S3_ENDPOINT_URL": "https://objects.example",
        "S3_BUCKET_NAME": "private",
        "S3_ACCESS_KEY_ID": "private-access",
        "S3_SECRET_ACCESS_KEY": "private-secret",
        "SECRET_KEY": "worker-private-secret-value-at-least-32-characters",
        "PAYMENT_BANK_DETAILS": "existing public destination",
    }.items():
        monkeypatch.setenv(key, value)


def test_missing_configuration_stops_before_any_connection(monkeypatch, capsys):
    configure(monkeypatch)
    monkeypatch.setenv("S3_BUCKET_NAME", "CHANGE_ME")
    assert main() == 1
    output = capsys.readouterr().out
    assert "S3_BUCKET_NAME" in output
    assert "private-password" not in output and "private-secret" not in output


@pytest.mark.parametrize(
    "key,value",
    [
        ("DATABASE_URL", "postgresql://user:private-password@db.example/db"),
        ("S3_ENDPOINT_URL", "http://objects.example"),
    ],
)
def test_remote_worker_requires_tls(monkeypatch, capsys, key, value):
    configure(monkeypatch)
    monkeypatch.setenv(key, value)
    assert main() == 1
    assert "private-password" not in capsys.readouterr().out


def test_success_checks_storage_encoder_and_disk_and_sanitizes_dependency_errors(
    monkeypatch, capsys
):
    configure(monkeypatch)
    from app.core import database, storage

    engine = MagicMock()
    monkeypatch.setattr(database, "engine", engine)
    provider = SimpleNamespace(check_readiness=lambda: {"status": "ok"})
    monkeypatch.setattr(storage, "get_storage_provider", lambda: provider)
    monkeypatch.setattr("scripts.video_worker_preflight.subprocess.run", MagicMock())
    monkeypatch.setattr(
        "scripts.video_worker_preflight.shutil.disk_usage",
        lambda path: SimpleNamespace(free=40 * 1024**3),
    )
    assert main() == 0
    assert "scratch space: OK" in capsys.readouterr().out
    engine.connect.side_effect = RuntimeError("private-password and private-secret")
    assert main() == 1
    output = capsys.readouterr().out
    assert "RuntimeError" in output
    assert "private-password" not in output and "private-secret" not in output
