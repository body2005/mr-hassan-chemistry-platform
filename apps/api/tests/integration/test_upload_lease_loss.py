"""Real paused upload + Redis outage; local allowlisted project only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os
from pathlib import Path
import threading
import time
import uuid

import redis
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extended import LessonAsset
from .live_helpers import BASE, clear_auth, container, lesson, operational_logs, pg_engine, session, wait_until


def test_actual_upload_lease_loss_returns503_not500_and_recovers():
    clear_auth()
    broker = container('redis')
    release = threading.Event()
    stopped = False
    engine = pg_engine()

    def recovered():
        try:
            response = requests.get(BASE + '/ready', verify=os.environ['QA_CA_FILE'], timeout=6)
            return response.status_code == 200 and response.json().get('status') == 'ready'
        except requests.RequestException:
            return False

    @contextmanager
    def restored_broker():
        nonlocal stopped
        try:
            yield
        finally:
            release.set()
            if stopped:
                broker.start()
                stopped = False
            # This context closes BEFORE the real identity; logout must revoke
            # its family even when an assertion/controller step has failed.
            wait_until(recovered, 75)

    try:
        with session() as teacher, restored_broker(), ThreadPoolExecutor(max_workers=1) as pool:
            _course, item = lesson(teacher)
            with (Path(os.environ['QA_MEDIA_DIR']) / 'large.pdf').open('rb') as source:
                encoder = MultipartEncoder({'file': ('lease-loss.pdf', source, 'application/pdf')})

                class PausedBody:
                    len = encoder.len
                    transmitted = 0

                    def read(self, size=-1):
                        if self.transmitted >= 64 * 1024:
                            assert release.wait(90), 'Upload controller did not release the body'
                        data = encoder.read(size)
                        self.transmitted += len(data)
                        return data

                body = PausedBody()
                started = int(time.time())
                upload = pool.submit(teacher.post, BASE + f"/lessons/{item['id']}/materials",
                    data=body, headers={'Content-Type': encoder.content_type}, timeout=(10, 60))
                try:
                    # Read ONLY the resource reservation count, not token values
                    # or rate counters. No lease/counter is manually removed.
                    with redis.Redis.from_url(os.environ['REDIS_URL']) as store:
                        wait_until(lambda: store.zcard('upload:global') == 1, 20)
                    broker.stop(timeout=2)
                    stopped = True
                    operational_logs('api', lambda logs: b'Resource lease lost; closing reserved work' in logs,
                                     since=started, timeout=50)
                finally:
                    release.set()
                response = upload.result(timeout=60)
                assert response.status_code == 503, response.text
                assert response.json() == {'detail': 'Admission service temporarily unavailable'}
                assert response.headers['Retry-After'] == '2'
                assert response.headers['X-Content-Type-Options'] == 'nosniff'
                assert 'Strict-Transport-Security' in response.headers
                with Session(engine) as db:
                    assert not db.scalars(select(LessonAsset).where(
                        LessonAsset.lesson_id == uuid.UUID(item['id']))).all()
    finally:
        release.set()
        if stopped:
            broker.start()

        try:
            wait_until(recovered, 75)
        finally:
            engine.dispose()
