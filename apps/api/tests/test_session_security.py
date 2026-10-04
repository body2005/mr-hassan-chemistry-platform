from datetime import datetime, timedelta, timezone
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc
from fastapi.testclient import TestClient

from app.core.security import create_session_token, hash_token
from app.main import app
from app.models.institution import Institution
from app.models.platform import RefreshSession
from app.models.user import User
from app.services import auth_service
from app.services import mail_service
from app.core.config import get_settings
import re


def _register(client: TestClient, db, email: str = "session.student@example.com") -> None:
    db.add(Institution(name="Session Security", slug="session-security"))
    db.commit()
    response = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Session Student",
            "email": email,
            "password": "a-strong-password",
            "institution_slug": "session-security",
            "grade_level": "SECONDARY_2",
            "student_phone": "01012345678",
            "guardian_phone": "01112345678",
            "national_id": "30201010101010" if email == "session.student@example.com" else None,
            "governorate": "CAIRO",
            "school_name": "Session Secondary School",
            "gender": "MALE",
            "religion": "MUSLIM",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["token"]
    assert response.json()["expires_at"]


def _csrf_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": "http://localhost:5173",
        "X-CSRF-Token": client.cookies.get("matgar_csrf") or "",
    }


def test_auth_supports_cookie_and_bearer_and_refresh_tokens_are_hashed(db) -> None:
    client = TestClient(app)
    _register(client, db)

    assert client.get("/api/v1/auth/me").status_code == 200
    refresh_session = db.query(RefreshSession).one()
    user = db.get(User, refresh_session.user_id)
    assert user is not None
    assert refresh_session.token_hash
    # A Bearer token is supported for cross-origin SPAs (401 session fix v3)
    header_only_client = TestClient(app)
    assert header_only_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {create_session_token(user)}"},
    ).status_code == 200
    # Unauthenticated request fails
    assert TestClient(app).get("/api/v1/auth/me").status_code == 401
    assert db.query(RefreshSession).count() == 1
    assert client.cookies.get("matgar_refresh") not in {None, refresh_session.token_hash}


def test_refresh_rotates_and_replay_revokes_its_family(db) -> None:
    client = TestClient(app)
    _register(client, db, "rotation.student@example.com")
    original_refresh = client.cookies.get("matgar_refresh")
    assert original_refresh

    refreshed = client.post("/api/v1/auth/refresh", headers=_csrf_headers(client))
    assert refreshed.status_code == 200, refreshed.text
    replacement_refresh = client.cookies.get("matgar_refresh")
    assert replacement_refresh and replacement_refresh != original_refresh

    # Multi-tab race replay inside grace window receives valid session
    race_client = TestClient(app)
    race_client.cookies.set("matgar_refresh", original_refresh)
    race_client.cookies.set("matgar_csrf", "race-csrf")
    race_res = race_client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": "race-csrf"},
    )
    assert race_res.status_code == 200

    # The grace clock is anchored to consumption of the ORIGINAL credential,
    # not the newest descendant (otherwise later rotations extend replay).
    db.query(RefreshSession).filter(RefreshSession.token_hash == hash_token(original_refresh)).update(
        {RefreshSession.revoked_at: datetime.now(UTC) - timedelta(seconds=60)}
    )
    # Outside the grace window, replaying old token revokes family (theft detection)
    db.query(RefreshSession).filter(RefreshSession.token_hash == hash_token(replacement_refresh)).update(
        {RefreshSession.created_at: datetime.now(UTC) - timedelta(seconds=60)}
    )
    db.commit()

    replay_client = TestClient(app)
    replay_client.cookies.set("matgar_refresh", original_refresh)
    replay_client.cookies.set("matgar_csrf", "replay-csrf")
    replay = replay_client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": "replay-csrf"},
    )
    assert replay.status_code == 401
    # Reuse invalidates the active descendant, not merely the leaked token.
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cookie_mutation_requires_csrf_and_password_change_revokes_family(db) -> None:
    client = TestClient(app)
    _register(client, db, "csrf.student@example.com")

    missing_csrf = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "a-strong-password", "new_password": "another-strong-password"},
    )
    assert missing_csrf.status_code == 403

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=_csrf_headers(client),
        json={"current_password": "a-strong-password", "new_password": "another-strong-password"},
    )
    assert changed.status_code == 204, changed.text
    assert client.get("/api/v1/auth/me").status_code == 401


def test_password_reset_is_one_use_and_revokes_existing_sessions(db) -> None:
    client = TestClient(app)
    email = "reset.student@example.com"
    _register(client, db, email)
    assert client.get("/api/v1/auth/me").status_code == 200

    # The reset service currently returns the raw token; delivery is tested
    # separately because the public endpoint must never expose this secret.
    token = auth_service.request_password_reset(db, email, "session-security")
    assert token
    anonymous = TestClient(app)
    response = anonymous.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "replacement-strong-password"},
    )
    assert response.status_code == 204, response.text
    assert client.get("/api/v1/auth/me").status_code == 401
    assert anonymous.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "another-strong-password"},
    ).status_code == 400
    assert anonymous.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "a-strong-password", "institution_slug": "session-security"},
    ).status_code == 401
    assert anonymous.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "replacement-strong-password", "institution_slug": "session-security"},
    ).status_code == 200


def test_reset_request_sends_fragment_link_without_exposing_account(monkeypatch, db) -> None:
    client = TestClient(app)
    email = "email-reset.student@example.com"
    _register(client, db, email)
    request = {"email": email, "institution_slug": "session-security"}
    # Test the unconfigured branch explicitly; the Docker QA environment has
    # a real local SMTP sink and should not change this unit test's premise.
    for name in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    assert client.post("/api/v1/auth/password-reset/request", json=request).status_code == 503

    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "qa@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "synthetic-test-only")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "qa@example.test")
    monkeypatch.setenv("SMTP_TLS_VERIFY", "true")
    get_settings.cache_clear()
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout, context):
            assert (host, port, timeout) == ("smtp.example.test", 465, 10)
            assert context.verify_mode == mail_service.ssl.CERT_REQUIRED

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def login(self, user, password):
            assert (user, password) == ("qa@example.test", "synthetic-test-only")

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(mail_service.smtplib, "SMTP_SSL", FakeSMTP)
    try:
        known = client.post("/api/v1/auth/password-reset/request", json=request)
        missing = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "nobody@example.com", "institution_slug": "session-security"},
        )
        assert known.status_code == missing.status_code == 200
        assert known.json() == missing.json()
        assert len(sent) == 1
        body = sent[0].get_content()
        assert "/#auth?reset_token=" in body
        assert "/?reset_token=" not in body
        token = re.search(r"reset_token=([A-Za-z0-9_-]+)", body)
        assert token
        assert client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token.group(1), "new_password": "email-reset-new-password"},
        ).status_code == 204
    finally:
        get_settings.cache_clear()
