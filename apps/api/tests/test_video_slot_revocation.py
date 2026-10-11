import uuid
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.api.routes import platform
from app.api.routes.platform import _memory_video_sessions, clear_revoked_account_video_slots


def test_revoked_account_slots_clear_without_touching_other_accounts(monkeypatch):
    monkeypatch.setattr("app.core.rate_limit._get_redis_client", lambda: None)
    account, other = uuid.uuid4(), uuid.uuid4()
    key, other_key = f"video-session:{account}:lesson", f"video-session:{other}:lesson"
    _memory_video_sessions[key] = {"old1": 9999999999, "old2": 9999999999, "old3": 9999999999}
    _memory_video_sessions[other_key] = {"active": 9999999999}
    try:
        clear_revoked_account_video_slots(account)
        assert key not in _memory_video_sessions
        assert _memory_video_sessions[other_key] == {"active": 9999999999}
    finally:
        _memory_video_sessions.pop(other_key, None)


@pytest.fixture
def memory_slots(monkeypatch):
    monkeypatch.setattr(platform, 'get_settings', lambda: SimpleNamespace(
        video_max_concurrent_sessions=2, redis_required=False, deployment_environment=False))
    monkeypatch.setattr(platform, '_video_session_redis', lambda: None)
    monkeypatch.setattr('app.core.rate_limit._get_redis_client', lambda: None)
    account, lesson = uuid.uuid4(), uuid.uuid4()
    key = f'video-session:{account}:{lesson}'
    yield account, lesson, key
    _memory_video_sessions.pop(key, None)


def test_refresh_rotations_reuse_family_slot_without_relaxing_device_budget(memory_slots):
    account, lesson, key = memory_slots
    first, second, third = (uuid.uuid4() for _ in range(3))
    platform._register_video_session(None, account, lesson, 'first-jti', 300, family_id=first)
    platform._register_video_session(None, account, lesson, 'second-jti', 300, family_id=second)
    for index in range(8):
        platform._register_video_session(None, account, lesson, f'rotated-{index}', 300, family_id=first)
    assert set(_memory_video_sessions[key]) == {f'family:{first}', f'family:{second}'}
    with pytest.raises(HTTPException) as denied:
        platform._register_video_session(None, account, lesson, 'third-jti', 300, family_id=third)
    assert denied.value.status_code == 429
    assert denied.value.headers['Retry-After'] == '30'


def test_legacy_jti_slot_is_retained_not_reset_on_family_upgrade(memory_slots):
    account, lesson, key = memory_slots
    family = uuid.uuid4()
    platform._register_video_session(None, account, lesson, 'legacy', 300)
    platform._register_video_session(None, account, lesson, 'rotated', 300, family_id=family)
    assert set(_memory_video_sessions[key]) == {'legacy', f'family:{family}'}
    with pytest.raises(HTTPException) as denied:
        platform._register_video_session(None, account, lesson, 'different-device', 300, family_id=uuid.uuid4())
    assert denied.value.status_code == 429


def test_logout_releases_only_its_stable_family_and_legacy_jti(memory_slots):
    account, lesson, key = memory_slots
    family, other = uuid.uuid4(), uuid.uuid4()
    _memory_video_sessions[key] = {f'family:{family}': 9999999999, 'legacy-current': 9999999999,
                                  f'family:{other}': 9999999999}
    try:
        platform._revoke_video_sessions(None, account, family, 'legacy-current')
        assert set(_memory_video_sessions[key]) == {f'family:{other}'}
        assert f'video-deny:family:{family}' in platform._memory_video_deny
        assert 'video-deny:session:legacy-current' in platform._memory_video_deny
    finally:
        platform._memory_video_deny.pop(f'video-deny:family:{family}', None)
        platform._memory_video_deny.pop('video-deny:session:legacy-current', None)


def test_normal_expiry_frees_a_family_slot(memory_slots):
    account, lesson, key = memory_slots
    family, active, new = (uuid.uuid4() for _ in range(3))
    _memory_video_sessions[key] = {f'family:{family}': 0, f'family:{active}': 9999999999}
    platform._register_video_session(None, account, lesson, 'new', 300, family_id=new)
    assert set(_memory_video_sessions[key]) == {f'family:{active}', f'family:{new}'}


def test_redis_receives_stable_slot_and_scoped_logout_members(monkeypatch):
    account, lesson, family = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    key = f'video-session:{account}:{lesson}'
    calls = []
    class RecordingRedis:
        def eval(self, *args):
            calls.append(('admit', args[5], args[6]))
            return 1
        def set(self, *args, **kwargs):
            pass
        def scan_iter(self, *, match):
            assert match == f'video-session:{account}:*'
            return [key]
        def zrem(self, *args):
            calls.append(('revoke', *args))
    client = RecordingRedis()
    monkeypatch.setattr(platform, '_video_session_redis', lambda: client)
    monkeypatch.setattr('app.core.rate_limit._get_redis_client', lambda: client)
    platform._register_video_session(None, account, lesson, 'current-jti', 300, family_id=family)
    platform._revoke_video_sessions(None, account, family, 'current-jti')
    assert calls == [('admit', f'family:{family}', 2),
                     ('revoke', key, f'family:{family}', 'current-jti')]
