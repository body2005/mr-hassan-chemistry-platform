"""Real paused TLS SMTP and stopped shared broker; synthetic recipients only.

Run sequentially with other fault/browser/load suites in the allowlisted QA
project. No rate-limit counters, credentials or production rows are erased.
"""
import json
import os
import statistics
import time
import uuid

import redis
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mail_outbox import ResetMailOutbox
from app.models.user import PasswordResetToken
from .live_helpers import BASE, container, wait_until
from .test_remaining_security_live import synthetic_account


def test_slow_smtp_does_not_block_reset_http_and_mail_recovers_without_celery_broker():
    engine, user_id, email, _password = synthetic_account()
    smtp, worker, broker = (container(name) for name in ('mailpit', 'worker', 'redis'))
    paused = worker_stopped = broker_stopped = False
    samples = {'existing': [], 'missing': []}
    job_ids = []
    try:
        store = redis.Redis.from_url(os.environ['REDIS_URL'])
        # Honor the real five-per-300s reset budget, including previous cases.
        delay = max([store.pttl(key) for key in store.scan_iter('rate-limit:password_reset_request:*')] + [0])
        if delay > 0:
            time.sleep((delay + 100) / 1000)
        store.close()
        with Session(engine) as db:
            previous = set(db.scalars(select(ResetMailOutbox.id).join(PasswordResetToken,
                PasswordResetToken.id == ResetMailOutbox.token_id).where(PasswordResetToken.user_id == user_id)))
        worker.stop(timeout=2)
        worker_stopped = True
        smtp.pause()  # TCP accepts but TLS/SMTP cannot progress until unpause.
        paused = True
        message = None
        for kind in ('existing', 'missing', 'missing', 'existing'):
            started = time.perf_counter()
            response = requests.post(BASE + '/auth/password-reset/request',
                json={'email': email if kind == 'existing' else uuid.uuid4().hex + '@qa.example.com',
                      'institution_slug': 'demo'}, verify=os.environ['QA_CA_FILE'], timeout=4)
            samples[kind].append(round((time.perf_counter() - started) * 1000, 3))
            assert response.status_code == 200, response.text
            assert 'token' not in response.json()
            if message is None:
                message = response.json()
            assert response.json() == message
        def enqueued():
            with Session(engine) as db:
                jobs = db.scalars(select(ResetMailOutbox).join(PasswordResetToken,
                    PasswordResetToken.id == ResetMailOutbox.token_id).where(
                    PasswordResetToken.user_id == user_id, ResetMailOutbox.id.not_in(previous))).all()
                return len(jobs) == 2
        # Public HTTP now acknowledges durable identity requests before lookup.
        # Require both real mail jobs to be produced by the background consumer.
        wait_until(enqueued, 60)
        with Session(engine) as db:
            jobs = db.scalars(select(ResetMailOutbox).join(PasswordResetToken,
                PasswordResetToken.id == ResetMailOutbox.token_id).where(
                PasswordResetToken.user_id == user_id, ResetMailOutbox.id.not_in(previous))).all()
            assert len(jobs) == 2
            assert all(job.completed_at is None and job.encrypted_token for job in jobs)
            job_ids = [job.id for job in jobs]

        def deferred():
            with Session(engine) as db:
                return any(db.get(ResetMailOutbox, key).attempts > 0 for key in job_ids)
        wait_until(deferred, 60)  # Actual ten-second SMTP timeout plus maintenance tick.
        # Redis is also the Celery broker, but reset delivery is DB-backed.
        # Public admission deliberately remains fail-closed while Redis is down.
        broker.stop(timeout=2)
        broker_stopped = True
        smtp.unpause()
        paused = False

        def delivered():
            with Session(engine) as db:
                return all(db.get(ResetMailOutbox, key).completed_at is not None
                           and db.get(ResetMailOutbox, key).encrypted_token is None for key in job_ids)
        wait_until(delivered, 90)
        print(json.dumps({'paused_tls_smtp_reset_http_ms': samples,
            'median_ms': {key: statistics.median(values) for key, values in samples.items()},
            'durable_jobs': 2, 'completed_without_celery_worker_or_broker': True,
            'boundary': 'two samples per identity class: not statistical timing-equivalence proof'}))
    finally:
        if paused:
            smtp.unpause()
        if broker_stopped:
            broker.start()
        if worker_stopped:
            worker.start()
        try:
            def recovered():
                try:
                    return requests.get(BASE + '/ready', verify=os.environ['QA_CA_FILE'], timeout=6).status_code == 200
                except requests.RequestException:
                    return False
            wait_until(recovered, 75)
        finally:
            engine.dispose()
