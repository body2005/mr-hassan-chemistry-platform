"""Private synthetic objects, in-memory identities, and mocked DRM upstream only."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from test_video_drm_hardening import ready_generation
from test_video_protection import _csrf, _login, _setup_world

from app.core.security import create_video_token, decode_session_token
from app.core.storage import LocalStorageProvider
from app.main import app
from app.models.payment import EntitlementType, StudentEntitlement
from app.services import video_drm


@pytest.fixture
def media_world(db, tmp_path, monkeypatch):
    inst, teacher, student, other, lesson = _setup_world(db, tmp_path, monkeypatch)
    lesson.price_egp = 50
    asset = ready_generation(db, lesson, teacher)
    provider = LocalStorageProvider(str(tmp_path / "private-objects"))
    prefix = asset.manifest_key.rsplit("/", 1)[0]
    master = ["#EXTM3U"]
    objects = {asset.object_key: b"private-original-must-not-reach-student"}
    for height in (360, 480, 720, 1080):
        master += [
            f"#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=1920x{height}",
            f"{height}p/index.m3u8",
        ]
        objects[f"{prefix}/{height}p/index.m3u8"] = (
            b"#EXTM3U\n#EXTINF:6,\nsegment_000000.ts\n#EXT-X-ENDLIST\n"
        )
        objects[f"{prefix}/{height}p/segment_000000.ts"] = (
            b"synthetic-clear-hls-bytes-for-authorized-viewer"
        )
    objects[asset.manifest_key] = ("\n".join(master) + "\n").encode()
    for key, content in objects.items():
        provider.save_bytes(content, key)
    asset.outputs = [key for key in objects if key != asset.object_key]
    db.commit()
    monkeypatch.setattr("app.core.storage.get_storage_provider", lambda: provider)
    monkeypatch.setattr("app.api.routes.platform.get_storage_provider", lambda: provider)
    return inst, teacher, student, other, lesson, asset, provider


def grant(db, inst, student, lesson):
    entitlement = StudentEntitlement(
        institution_id=inst.id,
        student_id=student.id,
        entitlement_type=EntitlementType.LESSON,
        resource_id=lesson.id,
        starts_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db.add(entitlement)
    db.commit()
    return entitlement


def test_paid_hls_rechecks_purchase_session_resource_schedule_and_range(db, media_world):
    inst, _, student, other, lesson, asset, _ = media_world
    browser, visitor, outsider = TestClient(app), TestClient(app), TestClient(app)
    _login(browser, student, inst.slug)
    assert visitor.post(f"/api/v1/lessons/{lesson.id}/video-token").status_code in (401, 403)
    assert (
        browser.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=_csrf(browser)).status_code
        == 403
    )
    entitlement = grant(db, inst, student, lesson)
    issued = browser.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=_csrf(browser))
    assert issued.status_code == 200, issued.text
    admission = issued.json()
    assert admission["format"] == "hls"
    assert asset.object_key not in issued.text and "s3://" not in issued.text
    url, token = admission["stream_url"], admission["video_token"]
    master = browser.get(url)
    assert master.status_code == 200 and "no-store" in master.headers["cache-control"]
    variants = [line for line in master.text.splitlines() if line and not line.startswith("#")]
    assert len(variants) == 4
    for variant in variants:
        playlist = browser.get(variant)
        segment = next(
            line for line in playlist.text.splitlines() if line and not line.startswith("#")
        )
        response = browser.get(segment, headers={"Range": "bytes=0-8"})
        assert response.status_code == 206 and response.content == b"synthetic"
        assert "no-store" in response.headers["cache-control"]
        assert "Cookie" in response.headers["vary"]
        assert browser.get(segment, headers={"Range": "bytes=99999-"}).status_code == 416
    # This is evidence of copyable clear bytes in the issuing session, not an
    # assertion of IDM execution or a native-media playback exercise.
    assert browser.get(f"/api/v1/lessons/{lesson.id}/stream?token={token}").status_code == 409
    assert browser.get(f"/api/v1/lessons/{lesson.id}/video").status_code == 403
    assert (
        browser.get(
            f"/api/v1/lessons/{lesson.id}/hls/{asset.id}/original.mp4?token={token}"
        ).status_code
        == 404
    )
    assert visitor.get(url).status_code == 403
    _login(outsider, other, inst.slug)
    assert outsider.get(url).status_code == 403
    assert browser.get(url.replace(str(lesson.id), str(uuid.uuid4()))).status_code == 403
    assert browser.get(url.replace(str(asset.id), str(uuid.uuid4()))).status_code == 404
    assert browser.get(f"/static/{asset.object_key}").status_code == 404
    listing = browser.get(f"/api/v1/courses/{lesson.course_id}")
    assert asset.object_key not in listing.text and "video_asset_key" not in listing.text
    claims = decode_session_token(browser.cookies.get("matgar_session"))
    expired = create_video_token(
        user=student,
        lesson_id=lesson.id,
        expires_in_seconds=-1,
        nonce=claims["jti"],
        family_id=uuid.UUID(claims["family_id"]),
    )
    assert browser.get(url.replace(token, expired)).status_code == 403
    lesson.publish_at = datetime.now(UTC) + timedelta(hours=1)
    db.commit()
    assert browser.get(url).status_code == 403
    lesson.publish_at = None
    db.commit()
    entitlement.revoked_at = datetime.now(UTC)
    db.commit()
    assert browser.get(url).status_code == 403
    entitlement.revoked_at = None
    db.commit()
    assert browser.post("/api/v1/auth/logout", headers=_csrf(browser)).status_code == 204
    assert browser.get(url).status_code == 403


def test_drm_license_proxy_rechecks_access_and_never_delivers_keys_or_clear_fallback(
    db, media_world, monkeypatch
):
    import httpx

    inst, _, student, _, lesson, asset, _ = media_world
    grant(db, inst, student, lesson)
    asset.drm = {
        "provider": "axinom",
        "scheme": "cbcs",
        "key_id": str(uuid.uuid4()),
        "communication_key_id": str(uuid.uuid4()),
        "encrypted_key": "synthetic-wrapped-key",
        "iv": "synthetic-iv",
    }
    lesson.video_drm_protected = True
    db.commit()
    monkeypatch.setattr(
        video_drm, "communication_key", lambda identity=None: (str(uuid.uuid4()), b"x" * 32)
    )
    monkeypatch.setattr(
        video_drm, "fairplay_certificate", lambda: b"synthetic-certificate-not-real-DRM"
    )
    calls, during_request = [], []

    class Upstream:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_bytes(self):
            for callback in during_request:
                callback()
            yield b"opaque-synthetic-license-not-real-DRM"

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url, **kwargs):
            assert url in video_drm.LICENSE_ENDPOINTS.values()
            assert "Cookie" not in kwargs["headers"]
            assert "X-AxDRM-Message" in kwargs["headers"]
            calls.append(url)
            return Upstream()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    browser = TestClient(app)
    _login(browser, student, inst.slug)
    admission = browser.post(f"/api/v1/lessons/{lesson.id}/video-token", headers=_csrf(browser))
    assert admission.status_code == 200, admission.text
    assert asset.drm["encrypted_key"] not in admission.text
    token = admission.json()["video_token"]
    for system in ("widevine", "fairplay"):
        endpoint = admission.json()["drm"][f"{system}_license_url"]
        response = browser.post(
            endpoint, content=b"synthetic-CDM-challenge", headers=_csrf(browser)
        )
        assert response.status_code == 200, response.text
        assert response.content == b"opaque-synthetic-license-not-real-DRM"
        assert "no-store" in response.headers["cache-control"]
        assert asset.drm["encrypted_key"] not in response.text
    endpoint = admission.json()["drm"]["widevine_license_url"]
    assert browser.post(endpoint, content=b"challenge").status_code == 403  # CSRF
    assert browser.get(f"/api/v1/lessons/{lesson.id}/stream?token={token}").status_code == 403
    assert (
        browser.get(
            f"/api/v1/lessons/{lesson.id}/hls/{asset.id}/360p/segment_000000.ts?token={token}"
        ).status_code
        == 403
    )
    assert browser.post(endpoint, content=b"", headers=_csrf(browser)).status_code == 422
    assert (
        browser.post(endpoint, content=b"x" * (256 * 1024 + 1), headers=_csrf(browser)).status_code
        == 413
    )
    assert TestClient(app).post(endpoint, content=b"challenge").status_code in (401, 403)
    assert len(calls) == 2

    # A revoke while awaiting a provider must prevent the license response.
    def revoke():
        student.is_active = False
        db.commit()

    during_request.append(revoke)
    response = browser.post(endpoint, content=b"challenge", headers=_csrf(browser))
    assert response.status_code == 403
