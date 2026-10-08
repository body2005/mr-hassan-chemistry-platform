"""New review gates: actual TCP, PostgreSQL and shared Redis. No real users."""
import concurrent.futures
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import threading
import time
import uuid
import pytest
import requests
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.security import hash_password, hash_token
from app.models.user import User, UserRole
from app.models.platform import RefreshSession, Notification, AuditLog
from app.models.extended import LearningObjective
from app.services.auth_service import request_password_reset
from .live_helpers import BASE, clear_auth, isolated, pg_engine, session, container


def synthetic_account():
    clear_auth()
    engine = pg_engine()
    password = 'Remaining-QA-synthetic-2026!'
    with session() as teacher:
        institution_id = uuid.UUID(teacher.get(BASE + '/auth/me', timeout=10).json()['institution_id'])
    with Session(engine) as db:
        key = uuid.uuid4().hex
        user = User(institution_id=institution_id, role=UserRole.STUDENT, username='remaining-'+key,
                    email=key+'@qa.example.com', display_name='Synthetic remaining QA', password_hash=hash_password(password))
        db.add(user); db.commit()
        return engine, user.id, user.email, password


@pytest.mark.parametrize('access', ['missing', 'expired'])
def test_real_logout_fallback_races_rotation_without_resurrecting_family(access):
    engine, _id, email, password = synthetic_account()
    try:
        with session(email, password) as original:
            jars = []
            for _ in range(3):
                client = requests.Session(); client.verify = original.verify
                client.cookies.update(original.cookies)
                client.headers['X-CSRF-Token'] = original.cookies.get('matgar_csrf')
                jars.append(client)
            # A saved refresh credential remains independent of rotated cookies.
            replay = jars[2]
            for cookie in list(jars[0].cookies):
                if cookie.name == 'matgar_session':
                    jars[0].cookies.clear(cookie.domain, cookie.path, cookie.name)
            if access == 'expired':
                import jwt
                secret = Path(os.environ['SECRET_KEY_FILE']).read_text().strip()
                old = original.cookies.get('matgar_session')
                claims = jwt.decode(old, secret, algorithms=['HS256'], audience='session', options={'verify_exp': False})
                claims['exp'] = int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())
                jars[0].cookies.set('matgar_session', jwt.encode(claims, secret, algorithm='HS256'), path='/')
            barrier = threading.Barrier(2)
            def send(index):
                barrier.wait(timeout=10)
                return jars[index].post(BASE + ('/auth/logout' if index == 0 else '/auth/refresh'), timeout=20)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(send, [0, 1]))
            assert results[0].status_code == 204
            assert results[1].status_code in {200, 401}
            assert replay.post(BASE + '/auth/refresh', timeout=15).status_code == 401
            # A successful concurrent refresh rotated the CSRF cookie as well.
            # Test family rejection, not an unrelated stale-header CSRF 403.
            jars[1].headers['X-CSRF-Token'] = jars[1].cookies.get('matgar_csrf', '')
            assert jars[1].post(BASE + '/auth/refresh', timeout=15).status_code == 401
            for client in jars: client.close()
    finally:
        engine.dispose()


def test_two_reset_tokens_confirmed_concurrently_allow_only_one_password_epoch():
    engine, _id, email, _password = synthetic_account()
    try:
        with Session(engine) as db:
            tokens = [request_password_reset(db, email, 'demo') for _ in range(2)]
        barrier = threading.Barrier(2)
        def send(token):
            barrier.wait(timeout=10)
            return requests.post(BASE + '/auth/password-reset/confirm',
                json={'token': token, 'new_password': 'Replaced-concurrently-2026!'},
                verify=os.environ['QA_CA_FILE'], timeout=20).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(send, tokens)) == [204, 400]
    finally:
        engine.dispose()


def test_live_configured_refresh_grace_expires_and_concurrent_reuse_notices_deduplicate():
    """Actual HTTPS/PG/time, not a mocked clock or aged database timestamps."""
    engine, user_id, email, password = synthetic_account()
    clients = []
    try:
        # Docker exec does not inherit PID1's secret-file exports. Use the
        # same checked-in production entrypoint, never print those secrets.
        probe = container('api').exec_run(['/bin/sh', '/srv/entrypoint-prod.sh', 'python', '-c',
            'from app.core.config import get_settings; print(get_settings().refresh_replay_grace_seconds)'])
        assert probe.exit_code == 0
        grace = int(probe.output.strip())
        assert 1 <= grace <= 30
        with session(email, password) as original:
            saved = original.cookies.copy()
            old_hash = hash_token(saved.get('matgar_refresh'))

            def old_client():
                client = requests.Session()
                client.verify = original.verify
                client.cookies.update(saved)
                client.headers['X-CSRF-Token'] = saved.get('matgar_csrf')
                clients.append(client)
                return client

            assert original.post(BASE + '/auth/refresh', timeout=15).status_code == 200
            original.headers['X-CSRF-Token'] = original.cookies.get('matgar_csrf')
            with Session(engine) as db:
                consumed = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == old_hash))
                family, revoked_at = consumed.family_id, consumed.revoked_at
            # Independent tab is accepted while the actual configured clock runs.
            assert old_client().post(BASE + '/auth/refresh', timeout=15).status_code == 200
            with Session(engine) as db:
                assert db.scalar(select(RefreshSession.revoked_at).where(
                    RefreshSession.token_hash == old_hash)) == revoked_at
                assert not db.scalars(select(Notification).where(
                    Notification.recipient_id == user_id, Notification.dedup_key == 'refresh-reuse:' + str(family))).all()
            # Wait across the real configured boundary. Replays must not extend it.
            remaining = (revoked_at + timedelta(seconds=grace, milliseconds=250)
                         - datetime.now(timezone.utc)).total_seconds()
            if remaining > 0:
                time.sleep(remaining)
            race = [old_client() for _ in range(4)]
            barrier = threading.Barrier(4)
            def replay(client):
                barrier.wait(timeout=10)
                return client.post(BASE + '/auth/refresh', timeout=20).status_code
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                assert list(pool.map(replay, race)) == [401] * 4
            assert old_client().post(BASE + '/auth/refresh', timeout=15).status_code == 401
            assert original.get(BASE + '/auth/me', timeout=15).status_code == 401
            with Session(engine) as db:
                assert not db.scalars(select(RefreshSession).where(
                    RefreshSession.family_id == family, RefreshSession.revoked_at.is_(None))).all()
                notices = db.scalars(select(Notification).where(Notification.recipient_id == user_id,
                    Notification.dedup_key == 'refresh-reuse:' + str(family))).all()
                assert len(notices) == 1 and notices[0].kind == 'security'
                audits = db.scalars(select(AuditLog).where(AuditLog.actor_id == user_id,
                    AuditLog.action == 'refresh_reuse_detected')).all()
                assert len(audits) == 1
            print(f'Actual configured grace={grace}s; inside200, outside4 concurrent401+repeat401; one notice/audit')
    finally:
        for client in clients:
            client.close()
        engine.dispose()


def test_postgresql_partial_indexes_reject_scoped_and_null_duplicates():
    isolated(); engine = pg_engine()
    try:
        with session() as teacher:
            me = teacher.get(BASE + '/auth/me', timeout=15).json()
            course = teacher.post(BASE + '/courses', json={'code':'QA-OBJ-'+uuid.uuid4().hex[:12], 'title':'Objective scope QA'}, timeout=15).json()
        code = 'QA-' + uuid.uuid4().hex[:12]
        with Session(engine) as db:
            for course_id in (None, uuid.UUID(course['id'])):
                db.add(LearningObjective(institution_id=uuid.UUID(me['institution_id']), course_id=course_id, code=code, title='Unique scope'))
                db.commit()
                with pytest.raises(IntegrityError):
                    with db.begin_nested():
                        db.add(LearningObjective(institution_id=uuid.UUID(me['institution_id']), course_id=course_id, code=code, title='Rejected duplicate'))
                        db.flush()
            assert len(db.scalars(select(LearningObjective).where(LearningObjective.code == code)).all()) == 2
    finally:
        engine.dispose()


def test_real_reset_limit_is_five_not_middleware_fifteen():
    isolated()
    import redis
    store = redis.Redis.from_url(os.environ['REDIS_URL'])
    # Wait out existing reset budget instead of erasing/relaxing it.
    keys = list(store.scan_iter('rate-limit:password_reset_request:*'))
    delay = max([store.pttl(key) for key in keys] + [0])
    if delay > 0: time.sleep((delay + 100) / 1000)
    codes = []
    for _ in range(6):
        result = requests.post(BASE + '/auth/password-reset/request',
            json={'email': 'nonexistent-' + uuid.uuid4().hex + '@qa.example.com', 'institution_slug':'demo'},
            verify=os.environ['QA_CA_FILE'], timeout=10)
        codes.append(result.status_code)
    assert codes == [200] * 5 + [429], codes
    assert int(result.headers['Retry-After']) > 0
