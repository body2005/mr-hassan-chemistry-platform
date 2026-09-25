from __future__ import annotations

import os

os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FRONTEND_ORIGINS"] = "http://localhost:5173"
os.environ["INGESTION_BACKEND"] = "local"
os.environ["ALLOW_LOCAL_INGESTION"] = "false"
os.environ["STORAGE_BACKEND"] = "local"

from app.core.config import get_settings
get_settings.cache_clear()

import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.rate_limit import reset_rate_limits
from app.models import Base


@pytest.fixture(autouse=True)
def clean_database():
    reset_rate_limits()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Session:
    with SessionLocal() as session:
        yield session
