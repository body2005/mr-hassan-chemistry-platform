"""Real PostgreSQL + SeaweedFS; injection is at the DB commit boundary only."""
import asyncio
import io
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from starlette.datastructures import Headers

from app.core import storage as storage_core
from app.core.storage import S3StorageProvider
from app.models.course import Lesson
from app.models.extended import LessonAsset
from app.models.storage_cleanup import StorageCleanup
from app.models.user import User
from app.services import lesson_materials, platform_service, storage_cleanup
from .live_helpers import BASE, clear_auth, container, lesson, pg_engine, session, wait_until


@pytest.fixture
def real_storage(monkeypatch):
    engine = pg_engine()
    provider = S3StorageProvider(region_name='us-east-1')
    monkeypatch.setattr(storage_core, 'get_storage_provider', lambda: provider)
    monkeypatch.setattr(storage_cleanup, 'get_storage_provider', lambda: provider)
    monkeypatch.setattr(storage_cleanup, 'SessionLocal', sessionmaker(engine))
    clear_auth()
    with session() as teacher:
        course, item = lesson(teacher, kind='video')
        teacher_id = teacher.get(BASE + '/auth/me', timeout=15).json()['id']
    yield engine, provider, item, uuid.UUID(teacher_id)
    engine.dispose()


def fail_one_commit(monkeypatch, db):
    original = db.commit
    def injected():
        monkeypatch.setattr(db, 'commit', original)
        raise OperationalError('injected QA commit failure', {}, Exception('synthetic fault'))
    monkeypatch.setattr(db, 'commit', injected)


def attach_real_objects(engine, provider, item):
    video_key = f"audit/video-{uuid.uuid4().hex}.webm"
    material_key = f"audit/material-{uuid.uuid4().hex}.pdf"
    provider.save_bytes(b'\x1aE\xdf\xa3synthetic QA bytes', video_key)
    provider.save_bytes(b'%PDF-1.7\nsynthetic QA bytes', material_key)
    with Session(engine) as db:
        row = db.get(Lesson, uuid.UUID(item['id']))
        row.video_asset_key = video_key
        user = db.scalar(select(User).where(User.email == 'teacher@demo.com'))
        asset = LessonAsset(lesson_id=row.id, institution_id=user.institution_id,
                            asset_kind='pdf', object_key=material_key, filename='qa.pdf')
        db.add(asset); db.commit()
        return video_key, material_key, asset.id


def test_delete_rollback_preserves_database_and_s3_bytes(real_storage, monkeypatch):
    engine, provider, item, teacher_id = real_storage
    keys = attach_real_objects(engine, provider, item)
    with Session(engine) as db:
        user = db.get(User, teacher_id); row = db.get(Lesson, uuid.UUID(item['id']))
        fail_one_commit(monkeypatch, db)
        with pytest.raises(OperationalError):
            platform_service.delete_lesson(db, user, row.module_id, row.id)
        db.rollback()
        assert db.get(Lesson, uuid.UUID(item['id'])) is not None
        assert db.get(LessonAsset, keys[2]) is not None
        assert not db.scalars(select(StorageCleanup).where(StorageCleanup.object_key.in_(keys[:2]))).all()
    assert all(provider.exists(key) for key in keys[:2])


def test_delete_commits_retry_intents_during_real_s3_outage(real_storage):
    engine, provider, item, teacher_id = real_storage
    keys = attach_real_objects(engine, provider, item)
    target = container('s3')
    try:
        target.stop(timeout=2)
        with Session(engine) as db:
            user = db.get(User, teacher_id); row = db.get(Lesson, uuid.UUID(item['id']))
            platform_service.delete_lesson(db, user, row.module_id, row.id)
            assert db.get(Lesson, uuid.UUID(item['id'])) is None
        storage_cleanup.drain_cleanup()
        def retry_recorded_for_every_object():
            with Session(engine) as retry_db:
                jobs = retry_db.scalars(select(StorageCleanup).where(StorageCleanup.object_key.in_(keys[:2]))).all()
                return len(jobs) == 2 and all(job.attempts > 0 for job in jobs)
        # A real API cleanup worker may own one row via SKIP LOCKED. Wait for
        # both transactions to finish; do not treat a reserved row as lost.
        wait_until(retry_recorded_for_every_object, 75)
        with Session(engine) as db:
            jobs = db.scalars(select(StorageCleanup).where(StorageCleanup.object_key.in_(keys[:2]))).all()
            assert len(jobs) == 2 and all(job.attempts > 0 for job in jobs)
    finally:
        target.start()
        wait_until(lambda: provider.exists(keys[0]), 60)
    with Session(engine) as db:
        # The production cleanup loop is still running. Claim rows before
        # changing retry_at; otherwise it can legitimately delete a row
        # between this SELECT and flush (StaleDataError in the harness).
        for job in db.scalars(select(StorageCleanup).where(StorageCleanup.object_key.in_(keys[:2])).with_for_update()):
            job.retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    storage_cleanup.drain_cleanup()
    # Either real worker may own SKIP LOCKED rows; verify the durable outcome.
    wait_until(lambda: not any(provider.exists(key) for key in keys[:2]), 75)
    with Session(engine) as db:
        assert not db.scalars(select(StorageCleanup).where(StorageCleanup.object_key.in_(keys[:2]))).all()


def test_upload_commit_failure_compensates_actual_s3_object(real_storage, monkeypatch):
    engine, provider, item, teacher_id = real_storage
    keys = []
    original = provider.save_file
    def tracked(*args, **kwargs):
        result = original(*args, **kwargs); keys.append(args[1]); return result
    monkeypatch.setattr(provider, 'save_file', tracked)
    upload = UploadFile(io.BytesIO(b'%PDF-1.7\nQA rollback proof'), filename='rollback.pdf', size=27,
                        headers=Headers({'content-type': 'application/pdf'}))
    with Session(engine) as db:
        user = db.get(User, teacher_id)
        fail_one_commit(monkeypatch, db)
        with pytest.raises(OperationalError):
            asyncio.run(lesson_materials.upload_material(db, user, uuid.UUID(item['id']), upload))
        db.rollback()
        assert not db.scalars(select(LessonAsset).where(LessonAsset.lesson_id == uuid.UUID(item['id']))).all()
    assert len(keys) == 1 and not provider.exists(keys[0])


def test_material_delete_cleans_real_s3_after_commit(real_storage):
    engine, provider, item, teacher_id = real_storage
    keys = attach_real_objects(engine, provider, item)
    with Session(engine) as db:
        lesson_materials.delete_material(db, db.get(User, teacher_id), uuid.UUID(item['id']), keys[2])
    storage_cleanup.drain_cleanup()
    assert not provider.exists(keys[1]) and provider.exists(keys[0])
