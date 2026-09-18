from __future__ import annotations

from app.core.config import Settings


def test_s3_render_aliases_are_accepted(monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "render-access")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "render-secret")
    monkeypatch.setenv("S3_BUCKET_NAME", "render-bucket")

    settings = Settings(_env_file=None)

    assert settings.s3_access_key == "render-access"
    assert settings.s3_secret_key == "render-secret"
    assert settings.s3_bucket == "render-bucket"
