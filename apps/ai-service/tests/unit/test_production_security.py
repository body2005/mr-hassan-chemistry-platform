from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_missing_api_key():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", DEBUG=False, API_KEY=None, CORS_ORIGINS="https://lms.example")


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", DEBUG=False, API_KEY="secret", CORS_ORIGINS="*")


def test_production_accepts_explicit_origin_and_auth():
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        API_KEY="secret",
        CORS_ORIGINS="https://lms.example,https://admin.example",
    )
    assert settings.cors_origins == ["https://lms.example", "https://admin.example"]
