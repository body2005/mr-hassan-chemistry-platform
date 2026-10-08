"""Uniform public admission, atomic consumers and credential-epoch safety."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.main import app
from app.models.mail_outbox import ResetMailOutbox, ResetRequestOutbox
from app.models.user import PasswordResetToken, UserRole
from app.schemas import ChangePasswordRequest, PasswordResetConfirm
from app.services import auth_service, session_maintenance as maintenance
from tests.test_security_and_tenancy import make_institution, make_user


def owner(db):
    inst = make_institution(db, 'uniform-reset')
    user = make_user(db, inst.id, UserRole.STUDENT, 'uniform')
    db.commit()
    return inst, user


def test_http_queues_identical_envelopes_without_account_lookup(db, monkeypatch):
    inst, user = owner(db)
    monkeypatch.setattr('app.api.routes.auth.password_reset_mail_configured', lambda: True)
    monkeypatch.setattr(auth_service, 'request_password_reset',
        lambda *_args, **_kw: pytest.fail('Account lookup must not run in HTTP'))
    client = TestClient(app)
    bodies = []
    inputs = [(user.email, inst.slug), ('absent@example.com', inst.slug),
              ('absent@example.com', 'absent-tenant')]
    statements = []
    def observe(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lower())
    event.listen(db.get_bind(), 'before_cursor_execute', observe)
    try:
        for email, slug in inputs:
            result = client.post('/api/v1/auth/password-reset/request',
                                 json={'email': email, 'institution_slug': slug})
            assert result.status_code == 200
            bodies.append(result.json())
    finally:
        event.remove(db.get_bind(), 'before_cursor_execute', observe)
    assert all('from users' not in sql and 'from institutions' not in sql for sql in statements)
    assert bodies[0] == bodies[1] == bodies[2]
    jobs = db.query(ResetRequestOutbox).all()
    assert len(jobs) == 3 and len({len(job.encrypted_identity) for job in jobs}) == 1
    assert all(user.email not in job.encrypted_identity for job in jobs)
    assert db.query(PasswordResetToken).count() == db.query(ResetMailOutbox).count() == 0


@pytest.mark.parametrize('kind', ['existing', 'missing-user', 'missing-tenant', 'inactive', 'deleted', 'expired', 'corrupt', 'pre-registration'])
def test_consumer_completes_and_erases_every_identity_but_only_mails_live_accounts(db, kind):
    inst, user = owner(db)
    if kind == 'inactive':
        user.is_active = False
    if kind == 'deleted':
        user.deleted_at = datetime.now(timezone.utc)
    db.commit()
    maintenance.enqueue_reset_request(db, user.email if kind != 'missing-user' else 'missing@example.com',
                                      inst.slug if kind != 'missing-tenant' else 'missing-tenant')
    job = db.query(ResetRequestOutbox).one()
    if kind == 'expired':
        job.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    if kind == 'corrupt':
        job.encrypted_identity = 'not-a-fernet-envelope'
    if kind == 'pre-registration':
        job.requested_at = user.password_changed_at - timedelta(seconds=1)
    db.commit()
    assert maintenance.process_reset_requests() == 1
    assert maintenance.process_reset_requests() == 0
    db.expire_all()
    job = db.query(ResetRequestOutbox).one()
    assert job.completed_at and job.encrypted_identity is None
    expected = int(kind == 'existing')
    assert db.query(PasswordResetToken).count() == db.query(ResetMailOutbox).count() == expected


def test_uniform_admission_database_outage_is_retryable_without_identity_detail(db, monkeypatch):
    monkeypatch.setattr('app.api.routes.auth.password_reset_mail_configured', lambda: True)
    def fail(*_args):
        raise SQLAlchemyError('Synthetic private identity must not be reflected')
    monkeypatch.setattr(maintenance, 'enqueue_reset_request', fail)
    result = TestClient(app).post('/api/v1/auth/password-reset/request',
        json={'email': 'private@example.com', 'institution_slug': 'unknown'})
    assert result.status_code == 503 and result.headers['Retry-After'] == '1'
    assert 'private' not in result.text and 'identity' not in result.text


@pytest.mark.parametrize('change', ['password-change', 'reset-confirm'])
def test_queued_old_request_cannot_survive_a_password_epoch_change(db, change):
    inst, user = owner(db)
    raw = auth_service.request_password_reset(db, user.email, inst.slug)
    maintenance.enqueue_reset_request(db, user.email, inst.slug)
    if change == 'password-change':
        auth_service.change_password(db, user,
            ChangePasswordRequest(current_password='password-123456', new_password='New-Uniform-2026!'))
        db.commit()
    else:
        auth_service.reset_password(db, PasswordResetConfirm(token=raw, new_password='New-Uniform-2026!'))
    assert maintenance.process_reset_requests() == 1
    db.expire_all()
    assert db.query(PasswordResetToken).count() == 1
    assert db.query(PasswordResetToken).one().used_at is not None
    assert db.query(ResetMailOutbox).count() == 0
    # A new request after the change is still usable.
    maintenance.enqueue_reset_request(db, user.email, inst.slug)
    assert maintenance.process_reset_requests() == 1
    assert db.query(PasswordResetToken).count() == 2
    assert db.query(ResetMailOutbox).count() == 1


def test_consumer_crash_rolls_back_token_mail_and_request_completion_together(db, monkeypatch):
    inst, user = owner(db)
    maintenance.enqueue_reset_request(db, user.email, inst.slug)
    with monkeypatch.context() as patch:
        def fail(_session):
            raise RuntimeError('Synthetic lost consumer commit')
        patch.setattr(Session, 'commit', fail)
        with pytest.raises(RuntimeError, match='lost consumer commit'):
            maintenance.process_reset_requests()
    db.expire_all()
    assert db.query(PasswordResetToken).count() == db.query(ResetMailOutbox).count() == 0
    assert db.query(ResetRequestOutbox).one().completed_at is None
    assert db.query(ResetRequestOutbox).one().encrypted_identity
    assert maintenance.process_reset_requests() == 1
    assert db.query(PasswordResetToken).count() == db.query(ResetMailOutbox).count() == 1
