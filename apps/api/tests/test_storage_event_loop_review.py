"""Regression: the synchronous S3 SDK must not suspend lease heartbeats."""
import asyncio
import io
import threading
import time
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from starlette.datastructures import UploadFile, Headers
from app.core import storage
from app.services import lesson_materials


def setup_upload(monkeypatch, tmp_path):
    user, db = Mock(), Mock()
    lesson = SimpleNamespace(id=uuid.uuid4())
    course = SimpleNamespace(institution_id=uuid.uuid4())
    monkeypatch.setattr(lesson_materials, '_lesson_course', lambda *_: (lesson, course))
    monkeypatch.setattr(lesson_materials, 'ensure_course_manager', lambda *_: None)
    monkeypatch.setattr(lesson_materials, 'ensure_staging_capacity', lambda *_: None)
    monkeypatch.setenv('STORAGE_DIR', str(tmp_path))
    upload = UploadFile(io.BytesIO(b'%PDF-1.7\nQA'), filename='qa.pdf', size=12, headers=Headers({'content-type': 'application/pdf'}))
    return db, user, lesson, upload


def test_storage_transfer_leaves_the_event_loop_responsive(monkeypatch, tmp_path):
    db, user, lesson, upload = setup_upload(monkeypatch, tmp_path)
    interval, heartbeats = [], []
    def save_file(*_):
        interval.append(time.monotonic())
        time.sleep(.15)  # Deterministic stand-in for the synchronous SDK call.
        interval.append(time.monotonic())
        return 's3://qa/synthetic.pdf'
    monkeypatch.setattr(storage, 'get_storage_provider', lambda: SimpleNamespace(save_file=save_file))
    async def scenario():
        async def heartbeat():
            while True:
                heartbeats.append(time.monotonic())
                await asyncio.sleep(.005)
        clock = asyncio.create_task(heartbeat())
        try:
            await lesson_materials.upload_material(db, user, lesson.id, upload)
        finally:
            clock.cancel()
            try: await clock
            except asyncio.CancelledError: pass
            await upload.close()
    asyncio.run(scenario())
    assert len(interval) == 2
    assert any(interval[0] < tick < interval[1] for tick in heartbeats), 'S3 transfer blocked the lease/HTTP event loop'


def test_cancelled_upload_waits_for_sdk_before_compensation_and_staging_cleanup(monkeypatch, tmp_path):
    db, user, lesson, upload = setup_upload(monkeypatch, tmp_path)
    started, finished = threading.Event(), threading.Event()
    staged_paths, compensated = [], []
    def save_file(staged, *_):
        from pathlib import Path
        staged_paths.append(Path(staged)); started.set()
        time.sleep(.15)
        assert Path(staged).exists(), 'Staging was removed while the SDK still read it'
        finished.set()
        return 's3://qa/synthetic.pdf'
    def compensate(*_):
        assert finished.is_set(), 'Compensation raced an unfinished S3 transfer'
        compensated.append(True)
    monkeypatch.setattr(storage, 'get_storage_provider', lambda: SimpleNamespace(save_file=save_file))
    monkeypatch.setattr(lesson_materials, 'compensate_upload', compensate)
    async def scenario():
        work = asyncio.create_task(lesson_materials.upload_material(db, user, lesson.id, upload))
        while not started.is_set(): await asyncio.sleep(.001)
        work.cancel()
        await asyncio.sleep(.01)
        work.cancel()  # Repeated disconnect/lease cancellation also waits.
        try:
            await work
            raise AssertionError('Upload committed despite cancellation during storage transfer')
        except asyncio.CancelledError:
            pass
        finally:
            await upload.close()
    asyncio.run(scenario())
    assert finished.is_set() and compensated == [True]
    assert staged_paths and not staged_paths[0].exists()
    db.add.assert_not_called(); db.commit.assert_not_called(); db.rollback.assert_called_once()


def test_failed_sdk_transfer_is_compensated_and_never_committed(monkeypatch, tmp_path):
    db, user, lesson, upload = setup_upload(monkeypatch, tmp_path)
    paths, compensated = [], []
    def save_file(staged, *_):
        from pathlib import Path
        paths.append(Path(staged))
        raise OSError('synthetic unavailable storage')
    monkeypatch.setattr(storage, 'get_storage_provider', lambda: SimpleNamespace(save_file=save_file))
    monkeypatch.setattr(lesson_materials, 'compensate_upload', lambda *_: compensated.append(True))
    async def scenario():
        import pytest
        try:
            with pytest.raises(OSError, match='synthetic unavailable storage'):
                await lesson_materials.upload_material(db, user, lesson.id, upload)
        finally:
            await upload.close()
    asyncio.run(scenario())
    assert compensated == [True] and paths and not paths[0].exists()
    db.add.assert_not_called(); db.commit.assert_not_called(); db.rollback.assert_called_once()
