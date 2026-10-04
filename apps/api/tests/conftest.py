from __future__ import annotations

import os
from urllib.parse import urlsplit

os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FRONTEND_ORIGINS"] = "http://localhost:5173"
os.environ["INGESTION_BACKEND"] = "local"
os.environ["ALLOW_LOCAL_INGESTION"] = "false"
os.environ["STORAGE_BACKEND"] = "local"

from app.core.config import get_settings
get_settings.cache_clear()
# The in-process SQLite app must NEVER reset the live app's Redis counters.
# Keep REDIS_URL intact for the HTTPS integration helpers and worker probes;
# only the cached settings used by this unit-test app get a separate DB.
unit_redis_url = os.getenv("QA_UNIT_REDIS_URL", "redis://localhost:6379/15")
if urlsplit(unit_redis_url).path != "/15" or urlsplit(os.getenv("REDIS_URL", "redis://localhost/0")).path == "/15":
    raise RuntimeError("Unit and live API Redis databases must be distinct")
get_settings().redis_url = unit_redis_url

import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.rate_limit import reset_rate_limits
from app.models import Base


@pytest.fixture(autouse=True)
def clean_database():
    get_settings().redis_url = unit_redis_url
    reset_rate_limits()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Session:
    with SessionLocal() as session:
        yield session
