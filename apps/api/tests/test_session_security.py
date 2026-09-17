from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import create_session_token
from app.main import app
from app.models.platform import RefreshSession
from app.models.user import User


def _register(client: TestClient, email: str = "session.student@example.com") -> None:
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
    assert "token" not in response.json()
    assert response.json()["expires_at"]


def _csrf_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": "http://localhost:5173",
        "X-CSRF-Token": client.cookies.get("matgar_csrf") or "",
    }


def test_auth_is_cookie_only_and_refresh_tokens_are_hashed(db) -> None:
    client = TestClient(app)
    _register(client)

    assert client.get("/api/v1/auth/me").status_code == 200
    # A syntactically valid session token in a header is not an API credential.
    refresh_session = db.query(RefreshSession).one()
    user = db.get(User, refresh_session.user_id)
    assert user is not None
    assert refresh_session.token_hash
    header_only_client = TestClient(app)
    assert header_only_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {create_session_token(user)}"},
    ).status_code == 401
    assert db.query(RefreshSession).count() == 1
    assert client.cookies.get("matgar_refresh") not in {None, refresh_session.token_hash}


def test_refresh_rotates_and_replay_revokes_its_family() -> None:
    client = TestClient(app)
    _register(client, "rotation.student@example.com")
    original_refresh = client.cookies.get("matgar_refresh")
    assert original_refresh

    refreshed = client.post("/api/v1/auth/refresh", headers=_csrf_headers(client))
    assert refreshed.status_code == 200, refreshed.text
    replacement_refresh = client.cookies.get("matgar_refresh")
    assert replacement_refresh and replacement_refresh != original_refresh

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


def test_cookie_mutation_requires_csrf_and_password_change_revokes_family() -> None:
    client = TestClient(app)
    _register(client, "csrf.student@example.com")

    missing_csrf = client.post(
        "/api/v1/auth/change-password",
        headers={"Origin": "http://localhost:5173"},
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
