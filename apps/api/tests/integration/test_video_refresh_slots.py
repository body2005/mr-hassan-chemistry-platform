"""Real HTTPS/PG/Redis device budget, refresh and nonce binding. No mock clock."""
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid
import requests
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.models.user import User, UserRole
from .live_helpers import BASE, clear_auth, lesson, pg_engine, session


def test_refresh_keeps_one_video_device_slot_and_logout_frees_only_that_family():
    clear_auth()
    engine = pg_engine()
    clients = []
    password = 'QA-video-device-regression-2026!'
    try:
        with session() as teacher:
            institution = uuid.UUID(teacher.get(BASE + '/auth/me', timeout=15).json()['institution_id'])
            course, item = lesson(teacher, kind='video')
        with Session(engine) as db:
            key = uuid.uuid4().hex
            user = User(institution_id=institution, username='qa-device-' + key,
                email=key + '@qa.example.com', display_name='Synthetic video device QA',
                role=UserRole.STUDENT, password_hash=hash_password(password))
            db.add(user); db.commit()
            email = user.email
        clients = [session(email, password) for _ in range(3)]
        assert clients[0].post(f"{BASE}/courses/{course['id']}/enroll", timeout=15).status_code == 200
        endpoint = f"{BASE}/lessons/{item['id']}/video-token"
        first = clients[0].post(endpoint, timeout=15)
        assert first.status_code == 200
        assert clients[1].post(endpoint, timeout=15).status_code == 200
        rejected = clients[2].post(endpoint, timeout=15)
        assert rejected.status_code == 429
        assert rejected.json()['detail'] == 'Too many concurrent video sessions for this account.'
        assert rejected.headers['Retry-After'] == '30'
        for _ in range(2):
            clear_auth()  # WAIT on real windows; never erase admission counters.
            old_jti = clients[0].cookies.get('matgar_session')
            assert clients[0].post(BASE + '/auth/refresh', timeout=15).status_code == 200
            clients[0].headers['X-CSRF-Token'] = clients[0].cookies.get('matgar_csrf', '')
            assert clients[0].cookies.get('matgar_session') != old_jti
            assert clients[0].post(endpoint, timeout=15).status_code == 200
        # The quota fix must NOT make a saved playback URL valid after refresh
        # or from the other device. No actual media is claimed by this test.
        old_url = BASE.removesuffix('/api/v1') + first.json()['stream_url']
        for client in clients[:2]:
            assert client.get(old_url, timeout=15).status_code == 403
        barrier = threading.Barrier(8)
        def issue(_index):
            # Independent TCP sessions share only this family's real cookies.
            with requests.Session() as client:
                client.verify = clients[0].verify
                client.cookies.update(clients[0].cookies)
                client.headers['X-CSRF-Token'] = clients[0].cookies.get('matgar_csrf', '')
                barrier.wait(timeout=10)
                return client.post(endpoint, timeout=20).status_code
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert list(pool.map(issue, range(8))) == [200] * 8
        still_rejected = clients[2].post(endpoint, timeout=15)
        assert still_rejected.status_code == 429
        assert still_rejected.json()['detail'] == rejected.json()['detail']
        assert clients[0].post(BASE + '/auth/logout', timeout=15).status_code == 204
        clients[0].cookies.clear()
        assert clients[2].post(endpoint, timeout=15).status_code == 200
        assert clients[1].post(endpoint, timeout=15).status_code == 200
    finally:
        for client in clients:
            client.close()
        engine.dispose()
