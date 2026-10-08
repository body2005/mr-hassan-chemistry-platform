"""Real PostgreSQL row locks/rollback for background delivery and retention.

Every row belongs to a private schema, not to runtime students. SMTP is a
deterministic sink here; real TLS SMTP outage/retry is covered separately.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker
from app.models.base import Base
from app.models.institution import Institution
from app.models.platform import AuditLog, RefreshSession, RevokedSession
from app.models.user import PasswordResetToken, User, UserRole
from app.models.mail_outbox import ResetMailOutbox, ResetRequestOutbox
from app.services.auth_service import request_password_reset
from app.services import session_maintenance as maintenance
from .live_helpers import isolated, pg_engine


@pytest.fixture
def maintenance_db(monkeypatch):
    isolated()
    engine = pg_engine()
    schema = 'qa_maintenance_' + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(scoped)
        factory = sessionmaker(bind=scoped)
        monkeypatch.setattr(maintenance, 'SessionLocal', factory)
        with factory() as db:
            institution = Institution(slug='qa-maintenance', name='Private synthetic schema')
            db.add(institution); db.flush()
            user = User(institution_id=institution.id, username='qa', email='maintenance@qa.example.com',
                display_name='Synthetic', role=UserRole.STUDENT, password_hash='unused-no-login')
            db.add(user); db.commit()
            user_id = user.id
        yield factory, user_id
    finally:
        # The exact UUID schema is the only destructive target, never public.
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_multiple_postgresql_consumers_claim_each_reset_request_once(maintenance_db):
    factory, user_id = maintenance_db
    with factory() as db:
        for _ in range(20):
            maintenance.enqueue_reset_request(db, 'maintenance@qa.example.com', 'qa-maintenance')
    gate = threading.Barrier(4)
    def consume():
        gate.wait(timeout=10)
        return maintenance.process_reset_requests(25)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _index: consume(), range(4)))
    assert sum(results) == 20
    with factory() as db:
        requests = db.scalars(select(ResetRequestOutbox)).all()
        tokens = db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)).all()
        mails = db.scalars(select(ResetMailOutbox)).all()
        assert len(requests) == len(tokens) == len(mails) == 20
        assert all(job.completed_at and job.encrypted_identity is None for job in requests)
        assert len({job.token_id for job in mails}) == 20


def test_postgresql_reset_request_commit_loss_cannot_leave_a_token_or_duplicate_mail(maintenance_db, monkeypatch):
    factory, user_id = maintenance_db
    with factory() as db:
        maintenance.enqueue_reset_request(db, 'maintenance@qa.example.com', 'qa-maintenance')
    with monkeypatch.context() as patch:
        def lost_commit(_session):
            raise RuntimeError('Synthetic request consumer commit loss')
        patch.setattr(Session, 'commit', lost_commit)
        with pytest.raises(RuntimeError, match='commit loss'):
            maintenance.process_reset_requests()
    with factory() as db:
        assert not list(db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)))
        assert not list(db.scalars(select(ResetMailOutbox)))
        pending = db.scalar(select(ResetRequestOutbox))
        assert pending.encrypted_identity and pending.completed_at is None
    assert maintenance.process_reset_requests() == 1
    assert maintenance.process_reset_requests() == 0
    with factory() as db:
        assert len(list(db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)))) == 1
        assert len(list(db.scalars(select(ResetMailOutbox)))) == 1


def test_multiple_postgresql_consumers_claim_each_mail_once(maintenance_db, monkeypatch):
    factory, _user_id = maintenance_db
    with factory() as db:
        for _ in range(12):
            request_password_reset(db, 'maintenance@qa.example.com', 'qa-maintenance', enqueue_mail=True)
    sent, lock = [], threading.Lock()
    def sink(_recipient, _token, *, message_id):
        with lock:
            sent.append(message_id)
    monkeypatch.setattr(maintenance, 'send_password_reset_email', sink)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(lambda _: maintenance.deliver_reset_mail(5), range(4))) == 12
    assert len(sent) == len(set(sent)) == 12
    assert maintenance.deliver_reset_mail() == 0
    with factory() as db:
        jobs = db.scalars(select(ResetMailOutbox)).all()
        assert len(jobs) == 12
        assert all(job.completed_at and job.encrypted_token is None for job in jobs)


def test_worker_crash_before_commit_keeps_mail_retryable_with_stable_identity(maintenance_db, monkeypatch):
    factory, _user_id = maintenance_db
    with factory() as db:
        request_password_reset(db, 'maintenance@qa.example.com', 'qa-maintenance', enqueue_mail=True)
    identities = []
    def crash(_recipient, _token, *, message_id):
        identities.append(message_id)
        # SMTP accepted, but the process died before committing completion.
        raise SystemExit('synthetic worker crash')
    monkeypatch.setattr(maintenance, 'send_password_reset_email', crash)
    with pytest.raises(SystemExit):
        maintenance.deliver_reset_mail()
    with factory() as db:
        job = db.scalar(select(ResetMailOutbox))
        assert job.completed_at is None and job.encrypted_token
    monkeypatch.setattr(maintenance, 'send_password_reset_email',
        lambda _recipient, _token, *, message_id: identities.append(message_id))
    assert maintenance.deliver_reset_mail() == 1
    assert len(identities) == 2 and identities[0] == identities[1]
    # Explicitly at-least-once, NOT an exactly-once SMTP delivery claim.


def test_concurrent_cleanup_preserves_live_tokens_replay_retention_and_audit(maintenance_db):
    factory, user_id = maintenance_db
    now = datetime.now(timezone.utc)
    with factory() as db:
        for expires in (now - timedelta(days=30), now - timedelta(days=2), now + timedelta(days=2)):
            for _ in range(12):
                key = uuid.uuid4().hex
                db.add(RefreshSession(user_id=user_id, token_hash=key, family_id=uuid.uuid4(), jti=key, expires_at=expires))
                db.add(RevokedSession(user_id=user_id, jti=key, expires_at=expires))
                db.add(PasswordResetToken(user_id=user_id, token_hash=key, expires_at=expires))
        db.add(AuditLog(action='synthetic_retention', resource_type='qa', occurred_at=now-timedelta(days=60)))
        db.commit()
    def clean(_):
        removed = 0
        while True:
            batch = maintenance.cleanup_expired_sessions(3)
            removed += batch
            if batch == 0:
                return removed
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(clean, range(4))) == 36
    assert maintenance.cleanup_expired_sessions() == 0
    with factory() as db:
        for model in (RefreshSession, RevokedSession, PasswordResetToken):
            rows = db.scalars(select(model)).all()
            assert len(rows) == 24
            assert all(row.expires_at >= now - timedelta(days=2, seconds=1) for row in rows)
        assert len(db.scalars(select(AuditLog)).all()) == 1
