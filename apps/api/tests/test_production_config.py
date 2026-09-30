import pytest
from pydantic import ValidationError

from app.core import config, storage


def production_settings(**overrides: object) -> config.Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "secret_key": "qa-config-test-secret-key-not-for-deployment",
        "frontend_origins": "https://chemistry.example.test",
        "storage_backend": "minio",
        "smtp_host": "smtp.example.test",
        "smtp_user": "qa@example.test",
        "smtp_password": "synthetic-test-only",
        "smtp_from_email": "qa@example.test",
        "smtp_tls_verify": True,
        "payment_instapay_account": "qa-synthetic-merchant",
    }
    values.update(overrides)
    return config.Settings(_env_file=None, **values)


def test_production_cors_only_allows_configured_origin(monkeypatch):
    monkeypatch.delenv("CORS_ORIGIN_REGEX", raising=False)
    settings = production_settings()

    assert settings.cors_origins == ["https://chemistry.example.test"]
    assert settings.cors_origin_regex is None


def test_production_rejects_http_origin_and_default_secret():
    with pytest.raises(ValidationError, match="FRONTEND_ORIGINS must use HTTPS"):
        production_settings(frontend_origins="http://localhost:5173")
    with pytest.raises(ValidationError, match="FRONTEND_ORIGINS must use HTTPS"):
        production_settings(frontend_origins="https://chemistry.example.test,http://localhost:5173")
    with pytest.raises(ValidationError, match="SECRET_KEY must be replaced"):
        production_settings(secret_key="development-only-change-me")
    with pytest.raises(ValidationError, match="SMTP delivery must be configured"):
        production_settings(smtp_host=None)
    with pytest.raises(ValidationError, match="SMTP TLS certificate verification"):
        production_settings(smtp_tls_verify=False)
    with pytest.raises(ValidationError, match="At least one payment destination"):
        production_settings(payment_instapay_account=None)


def test_production_storage_cannot_silently_fall_back_to_local(monkeypatch):
    monkeypatch.setattr(config, "get_settings", production_settings)
    monkeypatch.setattr(storage, "_storage_instance", None)

    def fail_storage(**_kwargs):
        raise ConnectionError("synthetic MinIO failure")

    monkeypatch.setattr(storage, "S3StorageProvider", fail_storage)
    with pytest.raises(RuntimeError, match="Configured object storage is unavailable"):
        storage.get_storage_provider()
