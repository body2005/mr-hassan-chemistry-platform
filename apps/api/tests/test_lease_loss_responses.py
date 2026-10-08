"""A failed distributed reservation closes work, never becomes a fake500.

Exercise both actual ASGI admission wrappers, including nested reservations.
Unrelated client cancellations and already-started streams are not rewritten.
"""
import asyncio
import json

import pytest

from app.core import leases
from app.core.concurrency import AdmissionMiddleware
from app.core.upload_limits import UploadBudgetMiddleware


def scenario(monkeypatch, kind, *, started=False, unrelated=False):
    held, sent, finished = [], [], []

    async def acquire(lease):
        lease.owner = asyncio.current_task()
        held.append(lease)
        return True

    monkeypatch.setattr(leases.ResourceLease, 'acquire', acquire)
    monkeypatch.setattr('app.core.upload_limits.ensure_staging_capacity', lambda *_args: None)

    async def endpoint(scope, receive, send):
        if started:
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'first', 'more_body': True})
        for lease in held:
            if not unrelated:
                lease.lost = True
            lease.owner.cancel()
        await asyncio.sleep(0)
        finished.append('must not continue after loss')

    app = endpoint
    if kind in {'admission', 'nested'}:
        app = AdmissionMiddleware(app, classify=lambda *_args: 'upload')
    if kind in {'upload', 'nested'}:
        app = UploadBudgetMiddleware(app)

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message):
        sent.append(message)

    scope = {'type': 'http', 'method': 'POST', 'path': '/api/v1/lessons/example/materials',
             'headers': [], 'query_string': b'', 'client': ('127.0.0.1', 12345)}
    return app, scope, receive, send, sent, finished


@pytest.mark.parametrize('kind', ['admission', 'upload', 'nested'])
def test_loss_before_headers_returns_one503_and_no_further_work(monkeypatch, kind):
    app, scope, receive, send, sent, finished = scenario(monkeypatch, kind)
    asyncio.run(app(scope, receive, send))
    assert not finished
    headers = [message for message in sent if message['type'] == 'http.response.start']
    assert len(headers) == 1 and headers[0]['status'] == 503
    assert dict(headers[0]['headers'])[b'retry-after'] == b'2'
    body = b''.join(message.get('body', b'') for message in sent)
    assert json.loads(body) == {'detail': 'Admission service temporarily unavailable'}


@pytest.mark.parametrize('backend_error', [False, True])
def test_real_renewal_marks_loss_and_logs_no_backend_secret(monkeypatch, caplog, backend_error):
    monkeypatch.setattr(leases, 'RENEW_INTERVAL_SECONDS', 0)

    class Backend:
        def eval(self, *_args):
            if backend_error:
                raise RuntimeError('private-backend-value-must-not-appear')
            return 0

    async def exercise():
        lease = leases.ResourceLease([('qa-reservation', 1)])
        lease.client = Backend()
        lease.owner = asyncio.current_task()
        lease.renew_task = asyncio.create_task(lease._renew())
        with pytest.raises(asyncio.CancelledError):
            await asyncio.sleep(30)
        assert lease.lost
        await lease.release()

    asyncio.run(exercise())
    assert 'Resource lease lost' in caplog.text
    assert ('RuntimeError' if backend_error else 'reservation_missing_or_expired') in caplog.text
    assert 'private-backend-value-must-not-appear' not in caplog.text


def test_client_cancellation_is_not_swallowed_or_mislabeled(monkeypatch):
    app, scope, receive, send, sent, finished = scenario(monkeypatch, 'nested', unrelated=True)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(app(scope, receive, send))
    assert not sent and not finished


def test_lost_stream_is_closed_without_a_second_status_or_success_tail(monkeypatch):
    app, scope, receive, send, sent, finished = scenario(monkeypatch, 'nested', started=True)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(app(scope, receive, send))
    assert [message['status'] for message in sent if message['type'] == 'http.response.start'] == [200]
    assert sent[-1]['more_body'] is True
    assert not finished
