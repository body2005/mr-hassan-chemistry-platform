"""Isolated live consumer probe invoked by the integration harness only."""
import asyncio
import os
import time
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.storage import S3StorageProvider, get_storage_provider
from app.main import app, lifespan, settings
from app.models.storage_cleanup import StorageCleanup


async def main():
    if (os.getenv('QA_ISOLATED') != 'true' or os.getenv('QA_PROJECT') not in {'chemistryaudit2', 'chemistryrelease1010'}
            or settings.app_env != 'production_like' or 'qa_cleanup_' not in settings.database_url):
        raise RuntimeError('Cleanup probe requires a dedicated QA schema and production_like runtime')
    key = os.environ['QA_CLEANUP_KEY']
    if not key.startswith('qa-cleanup-probe/'):
        raise RuntimeError('Only synthetic probe objects may be used')
    if not isinstance(get_storage_provider(), S3StorageProvider) or not get_storage_provider().exists(key):
        raise RuntimeError('The consumer must see the actual synthetic S3 object before deletion')
    async with lifespan(app):
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            with SessionLocal() as db:
                pending = db.scalar(select(StorageCleanup.id).where(StorageCleanup.object_key == key))
            if pending is None and not get_storage_provider().exists(key):
                print('production_like lifespan consumed PostgreSQL intent and deleted QA S3 object')
                return
            await asyncio.sleep(0.5)
        raise AssertionError('No periodic cleanup acknowledgement')


if __name__ == '__main__':
    asyncio.run(main())
