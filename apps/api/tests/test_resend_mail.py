"""Offline provider/feature tests: never send real mail or use provider credentials."""
import json
import ssl
import re
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.main import app
from app.models.mail_outbox import ResetMailOutbox, ResetRequestOutbox
from app.models.user import PasswordResetToken, UserRole
from app.services import mail_service, session_maintenance
from tests.test_security_and_tenancy import make_institution, make_user


def resend_settings(**overrides):
    return Settings(_env_file=None, **{
        'app_env': 'test', 'email_enabled': True, 'email_provider': 'resend',
        'email_from_email': 'reset@example.test', 'resend_api_key': 'synthetic-private-key',
        'frontend_origins': 'https://frontend.example.test',
        **overrides,
    })


def fake_transport(monkeypatch, *, status=200, data=b'{"id":"synthetic-delivery-id"}', error=None):
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, limit):
            assert limit == 65537
            return data

    Response.status = status

    class Opener:
        def open(self, request, timeout):
            assert timeout == 10
            requests.append(request)
            if error:
                raise error
            return Response()

    def build(https, redirects):
        assert https._context.verify_mode == ssl.CERT_REQUIRED
        assert redirects.redirect_request(None, None, 302, None, {}, 'https://other.example.test') is None
        return Opener()

    monkeypatch.setattr(mail_service, 'build_opener', build)
    monkeypatch.setattr(mail_service.smtplib, 'SMTP_SSL', lambda *_args, **_kw: pytest.fail('HTTPS must not use SMTP'))
    return requests


def test_resend_uses_https_fragment_link_and_stable_retry_identity(monkeypatch):
    requests = fake_transport(monkeypatch)
    for _ in range(2):
        mail_service.send_password_reset_email('student@example.test', 'synthetic-reset-token',
            resend_settings(), message_id='synthetic-outbox-id')
    assert len(requests) == 2
    assert requests[0].full_url == 'https://api.resend.com/emails'
    headers = {key.lower(): value for key, value in requests[0].header_items()}
    assert headers['authorization'] == 'Bearer synthetic-private-key'
    assert headers['idempotency-key'] == dict((k.lower(), v) for k, v in requests[1].header_items())['idempotency-key']
    payload = json.loads(requests[0].data)
    assert payload['from'] == 'reset@example.test' and payload['to'] == ['student@example.test']
    assert 'https://frontend.example.test/#auth?reset_token=synthetic-reset-token' in payload['text']


@pytest.mark.parametrize('status,data,error', [
    (503, b'private-provider-response', None),
    (200, b'not-json-private-response', None),
    (200, b'{}', None),
    (200, b'x' * 65537, None),
    (200, b'{}', TimeoutError('private request detail')),
    (200, b'{}', HTTPError('https://api.resend.com/emails', 429, 'private response', {}, None)),
], ids=['http-failure', 'invalid-json', 'missing-id', 'oversized-body', 'timeout', 'rate-limit'])
def test_provider_failure_is_retryable_without_secret_details(monkeypatch, status, data, error):
    fake_transport(monkeypatch, status=status, data=data, error=error)
    with pytest.raises(RuntimeError) as failure:
        mail_service.send_password_reset_email('student@example.test', 'private-token', resend_settings())
    assert str(failure.value) == 'Password reset email provider request failed'


def test_disabled_mail_does_not_queue_process_or_send_even_with_credentials(monkeypatch, db):
    settings = get_settings()
    monkeypatch.setattr(settings, 'email_enabled', False)
    monkeypatch.setattr(mail_service, 'build_opener', lambda *_args: pytest.fail('Disabled email must not connect'))
    client = TestClient(app)
    assert client.get('/api/v1/auth/features').json() == {'password_reset_enabled': False}
    response = client.post('/api/v1/auth/password-reset/request',
        json={'email': 'student@example.com', 'institution_slug': 'demo'})
    assert response.status_code == 503 and 'not enabled' in response.json()['detail']
    assert db.query(ResetRequestOutbox).count() == db.query(ResetMailOutbox).count() == db.query(PasswordResetToken).count() == 0
    assert session_maintenance.process_reset_requests() == session_maintenance.deliver_reset_mail() == 0
    with pytest.raises(RuntimeError, match='not configured'):
        mail_service.send_password_reset_email('student@example.test', 'private-token', resend_settings(email_enabled=False))


def test_features_expose_availability_without_credentials(monkeypatch):
    monkeypatch.setattr('app.api.routes.auth.password_reset_mail_configured', lambda: True)
    assert TestClient(app).get('/api/v1/auth/features').json() == {'password_reset_enabled': True}


def test_resend_reset_flow_retries_then_consumes_token_once(monkeypatch, db):
    institution = make_institution(db, 'resend-recovery')
    user = make_user(db, institution.id, UserRole.STUDENT, 'resend-student')
    db.commit()
    settings = get_settings()
    for name, value in dict(email_enabled=True, email_provider='resend',
        resend_api_key=SecretStr('synthetic-private-key'), email_from_email='reset@example.test',
        frontend_origins='https://frontend.example.test').items():
        monkeypatch.setattr(settings, name, value)
    client = TestClient(app)
    assert client.get('/api/v1/auth/features').json() == {'password_reset_enabled': True}
    responses = [client.post('/api/v1/auth/password-reset/request',
        json={'email': email, 'institution_slug': institution.slug})
        for email in (user.email, 'missing@example.com')]
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json() == responses[1].json()
    assert session_maintenance.process_reset_requests() == 2
    fake_transport(monkeypatch, status=503)
    assert session_maintenance.deliver_reset_mail() == 0
    db.expire_all()
    job = db.query(ResetMailOutbox).one()
    assert job.attempts == 1 and job.completed_at is None
    job.retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    sent = fake_transport(monkeypatch)
    assert session_maintenance.deliver_reset_mail() == 1
    assert session_maintenance.deliver_reset_mail() == 0
    db.expire_all()
    assert db.query(ResetMailOutbox).one().encrypted_token is None
    text = json.loads(sent[0].data)['text']
    token = re.search(r'reset_token=([A-Za-z0-9_-]+)', text).group(1)
    payload = {'token': token, 'new_password': 'Replacement-resend-password-2026'}
    assert client.post('/api/v1/auth/password-reset/confirm', json=payload).status_code == 204
    assert client.post('/api/v1/auth/password-reset/confirm', json=payload).status_code == 400
    assert client.post('/api/v1/auth/login', json={'email': user.email,
        'password': payload['new_password'], 'institution_slug': institution.slug}).status_code == 200
