"""Run production_like lifespan against a fresh schema, not the unit DB."""
import os
import subprocess
import sys
import uuid
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.storage import S3StorageProvider
from app.models.storage_cleanup import StorageCleanup
from .live_helpers import isolated, pg_engine


def test_production_like_periodic_consumer_deletes_only_synthetic_object():
    isolated()
    root = pg_engine()
    schema = 'qa_cleanup_' + uuid.uuid4().hex
    key = 'qa-cleanup-probe/' + uuid.uuid4().hex
    provider = S3StorageProvider(region_name='us-east-1')
    probe = None
    try:
        with root.begin() as db:
            db.execute(text(f'CREATE SCHEMA {schema}'))
        url = root.url.update_query_dict({'options': f'-csearch_path={schema}'})
        probe = create_engine(url)
        StorageCleanup.__table__.create(probe)
        provider.save_bytes(b'synthetic periodic cleanup probe', key)
        with Session(probe) as db:
            db.add(StorageCleanup(object_key=key)); db.commit()
        result = subprocess.run([sys.executable, '-m', 'scripts.qa_cleanup_runtime'], env={**os.environ,
            'APP_ENV': 'production_like', 'STORAGE_BACKEND': 's3', 'DATABASE_URL': url.render_as_string(hide_password=False),
            'QA_CLEANUP_KEY': key, 'SECRET_KEY': Path(os.environ['SECRET_KEY_FILE']).read_text().strip(),
            'COOKIE_SECURE': 'true', 'FRONTEND_ORIGINS': 'https://proxy',
            'SMTP_HOST': 'mailpit', 'SMTP_USER': 'qa', 'SMTP_PASSWORD': 'synthetic-not-used',
            'SMTP_FROM_EMAIL': 'qa@example.test', 'SMTP_TLS_VERIFY': 'true',
            'PAYMENT_INSTAPAY_ACCOUNT': 'qa-synthetic-merchant'}, capture_output=True, text=True, timeout=45)
        # Never print environment or stderr: a configuration failure could
        # include a connection string. Assertions expose status only.
        assert result.returncode == 0, f'Periodic consumer probe failed, exit={result.returncode}'
        assert 'production_like lifespan consumed' in result.stdout
        assert not provider.exists(key)
    finally:
        provider.delete(key)
        if probe is not None: probe.dispose()
        with root.begin() as db:
            db.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        root.dispose()
