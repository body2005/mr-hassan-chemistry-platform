"""Server-only Axinom entitlement adapter; no raw keys leave the worker.

Disabled by default. This is preparation for a licensed deployment, not an
assertion that provider credentials or real-device playback have been verified.
"""
import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from cryptography import x509
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.models.video_upload import VideoUpload

LICENSE_ENDPOINTS = {
    'widevine': 'https://drm-widevine-licensing.axprod.net/AcquireLicense',
    'fairplay': 'https://drm-fairplay-licensing.axprod.net/AcquireLicense',
}


def communication_key(identity: str | None = None) -> tuple[str, bytes]:
    settings = get_settings()
    try:
        if settings.video_drm_provider != 'axinom':
            raise ValueError()
        active = str(uuid.UUID(settings.video_drm_communication_key_id or ''))
        identity = str(uuid.UUID(identity)) if identity else active
        ring = json.loads(settings.video_drm_keyring.get_secret_value()) if settings.video_drm_keyring else {}
        encoded = settings.video_drm_communication_key.get_secret_value() if identity == active and settings.video_drm_communication_key else ring[identity]
        key = base64.b64decode(encoded, validate=True)
        if len(key) != 32:
            raise ValueError()
        return identity, key
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, 'DRM provider credentials are not configured') from None


def fairplay_certificate() -> bytes:
    settings = get_settings()
    try:
        cert = (base64.b64decode(settings.video_drm_fairplay_certificate_base64, validate=True)
            if settings.video_drm_fairplay_certificate_base64 else Path(settings.video_drm_fairplay_certificate_path or '').read_bytes())
        if not 64 <= len(cert) <= 65536:
            raise ValueError()
        x509.load_der_x509_certificate(cert)
        return cert
    except (OSError, ValueError):
        raise HTTPException(503, 'FairPlay certificate is not configured') from None


def new_content_key() -> tuple[bytes, dict]:
    identity, wrapping_key = communication_key()
    # Require both systems before packaging the shared CBCS asset.
    fairplay_certificate()
    kid, key, iv = uuid.uuid4(), os.urandom(16), os.urandom(16)
    encryptor = Cipher(algorithms.AES(wrapping_key), modes.CBC(kid.bytes)).encryptor()
    wrapped = encryptor.update(key) + encryptor.finalize()
    return key, {'provider': 'axinom', 'scheme': 'cbcs', 'key_id': str(kid),
        'communication_key_id': identity, 'encrypted_key': base64.b64encode(wrapped).decode('ascii'),
        'iv': base64.b64encode(iv).decode('ascii')}


def current_asset(db, lesson) -> VideoUpload | None:
    from app.services.video_playback import current_hls_generation
    asset = current_hls_generation(db, lesson)
    # current_hls_generation already compares the exact canonical manifest.
    # A second suffix check incorrectly rejected unqualified local keys.
    if not asset:
        if lesson.video_drm_protected:
            raise HTTPException(503, 'Protected video generation is not available')
        return None
    if lesson.video_drm_protected and (not asset.drm or asset.drm.get('scheme') != 'cbcs'):
        raise HTTPException(503, 'Protected video generation is not available')
    return asset


def license_message(asset: VideoUpload, lesson, user_id: str, *, is_student: bool = True) -> str:
    metadata = asset.drm or {}
    if metadata.get('provider') != 'axinom' or metadata.get('scheme') != 'cbcs':
        raise HTTPException(403, 'Encrypted video required')
    identity, key = communication_key(metadata.get('communication_key_id'))
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(seconds=300)
    if is_student and lesson.available_until:
        end = lesson.available_until
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        expiry = min(expiry, end)
    if expiry <= now:
        raise HTTPException(403, 'Lesson is no longer available')
    # Absolute expiration and duration are mutually exclusive in Axinom.
    message = {'version': 1, 'com_key_id': identity, 'expiration_date': expiry.isoformat(),
        'message': {'type': 'entitlement_message', 'version': 2,
            'license': {'start_datetime': now.isoformat(), 'expiration_datetime': expiry.isoformat(), 'allow_persistence': False},
            'content_keys_source': {'inline': [{'id': metadata['key_id'],
                'encrypted_key': metadata['encrypted_key'], 'iv': metadata['iv']}]},
            'session': {'user_id': user_id}}}
    return jwt.encode(message, key, algorithm='HS256')


def playback_descriptor(lesson, asset: VideoUpload, token: str) -> dict | None:
    if not lesson.video_drm_protected:
        return None
    communication_key((asset.drm or {}).get('communication_key_id'))
    fairplay_certificate()
    base = f'/api/v1/lessons/{lesson.id}/hls/{asset.id}/drm'
    return {'scheme': 'cbcs', 'widevine_license_url': f'{base}/license/widevine?token={token}',
        'fairplay_license_url': f'{base}/license/fairplay?token={token}',
        'fairplay_certificate_url': f'{base}/certificate?token={token}'}
