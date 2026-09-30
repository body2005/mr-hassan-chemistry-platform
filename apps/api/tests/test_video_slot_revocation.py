import uuid
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
