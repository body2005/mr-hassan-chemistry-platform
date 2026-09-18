from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
UTC = timezone.utc
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_session_token, decode_session_token, hash_token
from app.models.platform import RefreshSession, RevokedSession
from app.models.user import User
from app.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PrivateUserResponse,
    RegisterRequest,
    UserResponse,
)
from app.services import auth_service
from app.services.audit_service import record_audit

router = APIRouter(prefix="/auth")
Db = Annotated[Session, Depends(get_db)]


def _cookie_options(request: Request | None = None) -> tuple[str, bool]:
    settings = get_settings()
    is_https = False
    if request:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        is_https = proto.lower() == "https"
    # Browser sessions are same-origin via the frontend /api proxy.  Lax
    # prevents third-party cookie sends while preserving ordinary navigation.
    # Cross-site cookies would require SameSite=None and materially weaken the
    # CSRF boundary, so they are intentionally not enabled by configuration.
    return "lax", settings.secure_cookies or is_https


def _issue_refresh_session(db: Session, user: User, family_id: uuid.UUID | None = None) -> tuple[str, RefreshSession]:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    refresh_session = RefreshSession(
        token_hash=hash_token(raw_token),
        family_id=family_id or uuid.uuid4(),
        jti=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.refresh_ttl_seconds),
    )
    db.add(refresh_session)
    return raw_token, refresh_session


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive timestamps even for timezone-aware columns."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    request: Request | None = None,
) -> None:
    settings = get_settings()
    samesite_val, secure_val = _cookie_options(request)
    now = datetime.now(timezone.utc)
    access_expires_at = now + timedelta(seconds=settings.session_ttl_seconds)
    refresh_expires_at = now + timedelta(seconds=settings.refresh_ttl_seconds)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=access_token,
        max_age=settings.session_ttl_seconds,
        expires=access_expires_at,
        httponly=True,
        secure=secure_val,
        samesite=samesite_val,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_ttl_seconds,
        expires=refresh_expires_at,
        httponly=True,
        secure=secure_val,
        samesite=samesite_val,
        path="/api/v1/auth",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=secrets.token_urlsafe(32),
        max_age=settings.refresh_ttl_seconds,
        expires=refresh_expires_at,
        httponly=False,
        secure=secure_val,
        samesite=samesite_val,
        path="/",
    )


def _clear_auth_cookies(response: Response, request: Request | None = None) -> None:
    settings = get_settings()
    samesite_val, secure_val = _cookie_options(request)
    response.delete_cookie(settings.session_cookie_name, path="/", samesite=samesite_val, secure=secure_val)
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth", samesite=samesite_val, secure=secure_val)
    response.delete_cookie(settings.csrf_cookie_name, path="/", samesite=samesite_val, secure=secure_val)


def _auth_response(user: User, family_id: uuid.UUID, db: Session, response: Response, request: Request) -> AuthResponse:
    refresh_token, refresh_session = _issue_refresh_session(db, user, family_id)
    db.flush()
    access_token = create_session_token(user, family_id=refresh_session.family_id)
    _set_auth_cookies(response, access_token, refresh_token, request)
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)
    return AuthResponse(
        user=PrivateUserResponse.model_validate(user),
        expires_in=settings.session_ttl_seconds,
        expires_at=expires_at,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest, response: Response, db: Db, request: Request
) -> AuthResponse:
    enforce_rate_limit(request, bucket="auth", limit=10, window_seconds=60)
    try:
        user = auth_service.register_student(db, payload)
        record_audit(
            db,
            request,
            action="register",
            resource_type="user",
            actor=user,
            resource_id=str(user.id),
        )
        result = _auth_response(user, uuid.uuid4(), db, response, request)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to complete registration") from exc
    return result


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Db, request: Request) -> AuthResponse:
    enforce_rate_limit(request, bucket="auth", limit=12, window_seconds=60)
    user = auth_service.authenticate(db, payload)
    if user is None:
        record_audit(db, request, action="login_failed", resource_type="session")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    record_audit(db, request, action="login", resource_type="session", actor=user)
    db.commit()
    result = _auth_response(user, uuid.uuid4(), db, response, request)
    db.commit()
    return result


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    response: Response,
    db: Db,
    request: Request,
    refresh_cookie: Annotated[str | None, Cookie(alias=get_settings().refresh_cookie_name)] = None,
) -> AuthResponse:
    """Rotate exactly one refresh credential and detect replay of an older one."""
    enforce_rate_limit(request, bucket="auth", limit=60, window_seconds=60)
    if not refresh_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session is missing")

    now = datetime.now(UTC)
    # Lock the consumed row.  On PostgreSQL this makes two simultaneous
    # refreshes deterministic: one rotates it and the other observes replay.
    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_hash == hash_token(refresh_cookie))
        .with_for_update()
        .one_or_none()
    )
    if session is None:
        _clear_auth_cookies(response, request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session is invalid")
    if session.revoked_at is not None:
        if session.replaced_by:
            db.query(RefreshSession).filter(
                RefreshSession.family_id == session.family_id,
                RefreshSession.revoked_at.is_(None),
            ).update({RefreshSession.revoked_at: now}, synchronize_session=False)
            db.commit()
        _clear_auth_cookies(response, request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session is invalid")
    if _as_utc(session.expires_at) <= now:
        session.revoked_at = now
        db.commit()
        _clear_auth_cookies(response, request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session has expired")

    user = db.get(User, session.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        session.revoked_at = now
        db.commit()
        _clear_auth_cookies(response, request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session is invalid")

    result = _auth_response(user, session.family_id, db, response, request)
    replacement = db.query(RefreshSession).filter(
        RefreshSession.family_id == session.family_id,
        RefreshSession.token_hash != session.token_hash,
        RefreshSession.revoked_at.is_(None),
    ).order_by(RefreshSession.created_at.desc()).first()
    session.revoked_at = now
    session.replaced_by = replacement.jti if replacement else None
    record_audit(db, request, action="session_refreshed", resource_type="session", actor=user)
    db.commit()
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Db,
    request: Request,
    session_cookie: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> None:
    settings = get_settings()
    payload = decode_session_token(session_cookie) if session_cookie else None
    if payload:
        try:
            user_id = uuid.UUID(str(payload["sub"]))
            user = db.get(User, user_id)
            if user:
                db.add(
                    RevokedSession(
                        jti=str(payload["jti"]),
                        user_id=user.id,
                        expires_at=datetime.fromtimestamp(float(payload["exp"]), UTC),
                    )
                )
                family_id = payload.get("family_id")
                if family_id:
                    db.query(RefreshSession).filter(
                        RefreshSession.family_id == uuid.UUID(str(family_id)),
                        RefreshSession.revoked_at.is_(None),
                    ).update({RefreshSession.revoked_at: datetime.now(UTC)}, synchronize_session=False)
                record_audit(db, request, action="logout", resource_type="session", actor=user)
                db.commit()
        except (KeyError, TypeError, ValueError):
            db.rollback()
    _clear_auth_cookies(response, request)


@router.get("/me", response_model=PrivateUserResponse)
def current_user(user: CurrentUser) -> PrivateUserResponse:
    return PrivateUserResponse.model_validate(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, db: Db, request: Request
) -> None:
    try:
        auth_service.change_password(db, user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_audit(db, request, action="password_changed", resource_type="user", actor=user)
    db.query(RefreshSession).filter(
        RefreshSession.user_id == user.id,
        RefreshSession.revoked_at.is_(None),
    ).update({RefreshSession.revoked_at: datetime.now(UTC)}, synchronize_session=False)
    db.commit()


@router.post("/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
def revoke_all_sessions(user: CurrentUser, db: Db, request: Request) -> None:
    now = datetime.now(UTC)
    db.query(RefreshSession).filter(
        RefreshSession.user_id == user.id,
        RefreshSession.revoked_at.is_(None),
    ).update({RefreshSession.revoked_at: now}, synchronize_session=False)
    record_audit(db, request, action="sessions_revoked", resource_type="session", actor=user)
    db.commit()


@router.post("/password-reset/request")
def request_password_reset(
    payload: PasswordResetRequest, db: Db, request: Request
) -> dict[str, str]:
    enforce_rate_limit(request, bucket="auth", limit=5, window_seconds=300)
    # Deliberately generic: account existence must not be exposed to callers.
    auth_service.request_password_reset(db, str(payload.email), payload.institution_slug)
    return {"message": "If the account exists, reset instructions will be sent securely."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm, db: Db, request: Request) -> None:
    enforce_rate_limit(request, bucket="auth", limit=5, window_seconds=300)
    try:
        auth_service.reset_password(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
