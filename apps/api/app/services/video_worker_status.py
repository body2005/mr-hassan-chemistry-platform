"""Private encoder heartbeat; monitoring only, never a playback admission gate."""
import json
import logging
import os
import shutil
import threading
import time
import uuid
from datetime import timezone
from pathlib import Path
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.video_worker_heartbeat import VideoWorkerHeartbeat

logger = logging.getLogger(__name__)


class WorkerHeartbeat:
    def __init__(self, workspace='/work'):
        self.identity = uuid.uuid4().hex
        self.workspace = Path(workspace)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._state = {'state': 'starting', 'job_id': None, 'stage': None,
                       'progress_percent': None, 'progress_at': time.time(), 'job_started_at': None}
        self.thread = threading.Thread(target=self._run, name='video-heartbeat', daemon=True)

    def start(self):
        self.thread.start()

    def update(self, state, job_id=None, stage=None, percent=None):
        now = time.time()
        with self._lock:
            prior = self._state
            changed_job = prior['job_id'] != (str(job_id) if job_id else None)
            progressed = changed_job or prior['stage'] != stage or (
                percent is not None and (prior['progress_percent'] is None or percent > prior['progress_percent']))
            self._state = {'state': state, 'job_id': str(job_id) if job_id else None, 'stage': stage,
                'progress_percent': percent, 'progress_at': now if progressed else prior['progress_at'],
                'job_started_at': now if changed_job and job_id else prior['job_started_at'] if job_id else None}

    def _run(self):
        while not self._stop.is_set():
            with self._lock:
                payload = dict(self._state, worker_id=self.identity, seen_at=time.time())
            try:
                payload['workspace_free_bytes'] = shutil.disk_usage(self.workspace).free
                # Container-local: a second encoder sharing /work must not
                # keep a stopped encoder's liveness probe green.
                target = Path('/tmp/video-worker-heartbeat.json')
                staged = target.with_suffix('.tmp')
                staged.write_text(json.dumps(payload), encoding='utf-8')
                os.replace(staged, target)
                payload['progress_age_seconds'] = max(0, payload['seen_at'] - payload['progress_at'])
                with SessionLocal() as db:
                    if db.bind.dialect.name == 'postgresql':
                        db.execute(text("SET LOCAL statement_timeout = '1000ms'"))
                    row = db.get(VideoWorkerHeartbeat, self.identity)
                    if row is None:
                        row = VideoWorkerHeartbeat(worker_id=self.identity)
                        db.add(row)
                    row.seen_at = db.scalar(select(func.now()))
                    row.payload = payload
                    db.commit()
            except Exception:
                # No new Redis/cloud credentials: use the worker's existing
                # database connection. Backend messages/paths never in logs.
                logger.warning('Video worker heartbeat publication deferred')
            self._stop.wait(10)

    def stop(self):
        self.update('stopped')
        self._stop.set()
        self.thread.join(timeout=2)


def worker_status():
    settings = get_settings()
    with SessionLocal() as db:
        records = db.scalars(select(VideoWorkerHeartbeat).order_by(VideoWorkerHeartbeat.seen_at.desc()).limit(100)).all()
        current = db.scalar(select(func.now()))
    now = (current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current).timestamp()
    rows = []
    for record in records:
        row = record.payload
        seen = record.seen_at.replace(tzinfo=timezone.utc) if record.seen_at.tzinfo is None else record.seen_at
        age = max(0, now - seen.timestamp())
        progress_age = max(0, float(row['progress_age_seconds']) + age)
        status = 'stopped' if age > settings.video_worker_stale_seconds else row['state']
        if status == 'processing' and progress_age > settings.video_job_stalled_seconds:
            status = 'delayed'
        rows.append({**row, 'state': status, 'heartbeat_age_seconds': round(age),
                     'progress_age_seconds': round(progress_age)})
    return {'status': 'not_seen' if not rows else 'ok' if any(row['state'] in {'idle', 'processing'} for row in rows) else 'degraded',
            'workers': rows}
