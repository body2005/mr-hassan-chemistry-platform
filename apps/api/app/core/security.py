from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
UTC = timezone.utc
from typing import Any

import os
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.models.user import User

if os.getenv("APP_ENV") == "test":
    password_hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
else:
    password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def create_session_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "institution_id": str(user.institution_id),
        "role": user.role.value,
        "type": "session",
        "aud": "session",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(seconds=settings.session_ttl_seconds),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_session_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError:
        return None

    # CRITICAL: Reject preview tokens immediately so they cannot be used as generic session credentials
    if payload.get("type") == "preview" or payload.get("aud") == "preview":
        return None

    if not payload.get("sub") or not payload.get("institution_id"):
        return None
    return payload


def create_preview_token(user: User, source_id: uuid.UUID, expires_in_seconds: int = 300) -> str:
    """
    Creates a tightly scoped, short-lived preview token (default 5 minutes).
    Scoped strictly to source_id with aud='preview' and type='preview'.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "user_id": str(user.id),
        "institution_id": str(user.institution_id),
        "role": user.role.value,
        "source_id": str(source_id),
        "type": "preview",
        "aud": "preview",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(seconds=expires_in_seconds),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_preview_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            audience="preview",
        )
    except jwt.PyJWTError:
        return None

    if payload.get("type") != "preview" or not payload.get("sub") or not payload.get("source_id"):
        return None
    return payload


def create_video_token(
    user: User,
    lesson_id: uuid.UUID,
    expires_in_seconds: int = 300,
    nonce: str | None = None,
) -> str:
    """
    Creates a tightly scoped, short-lived video streaming token (default 5 minutes).
    Scoped strictly to lesson_id with aud='video_stream', purpose='video_stream'.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "user_id": str(user.id),
        "institution_id": str(user.institution_id) if user.institution_id else None,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "lesson_id": str(lesson_id),
        "purpose": "video_stream",
        "aud": "video_stream",
        "nonce": nonce or uuid.uuid4().hex[:12],
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(seconds=expires_in_seconds),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_video_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            audience="video_stream",
        )
    except jwt.PyJWTError:
        return None

    if payload.get("purpose") != "video_stream" or not payload.get("sub") or not payload.get("lesson_id"):
        return None
    return payload


def create_password_reset_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_token(raw_token)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
