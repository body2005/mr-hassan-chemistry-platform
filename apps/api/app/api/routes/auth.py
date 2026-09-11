from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
UTC = timezone.utc
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_session_token, decode_session_token
from app.models.platform import RevokedSession
from app.models.user import User
from app.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    UserResponse,
)
from app.services import auth_service
from app.services.audit_service import record_audit

router = APIRouter(prefix="/auth")
Db = Annotated[Session, Depends(get_db)]


def set_session_cookie(response: Response, token: str, request: Request | None = None) -> None:
    settings = get_settings()
    cross_site = settings.cookie_cross_site
    is_https = False
    if request:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        is_https = proto.lower() == "https"
    secure_val = settings.secure_cookies or cross_site or is_https
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.session_ttl_seconds)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        expires=expires_at,
        httponly=True,
        secure=secure_val,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=secrets.token_urlsafe(32),
        max_age=settings.session_ttl_seconds,
        expires=expires_at,
        httponly=False,
        secure=secure_val,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest, response: Response, db: Db, request: Request
) -> AuthResponse:
    enforce_rate_limit(request, bucket="auth-register", limit=10, window_seconds=60)
    try:
        user = auth_service.register_student(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    record_audit(
        db,
        request,
        action="register",
        resource_type="user",
        actor=user,
        resource_id=str(user.id),
    )
    db.commit()
    token = create_session_token(user)
    set_session_cookie(response, token, request=request)
    return AuthResponse(
        user=UserResponse.model_validate(user),
        expires_in=get_settings().session_ttl_seconds,
        token=token,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Db, request: Request) -> AuthResponse:
    enforce_rate_limit(request, bucket="auth-login", limit=12, window_seconds=60)
    user = auth_service.authenticate(db, payload)
    if user is None:
        record_audit(db, request, action="login_failed", resource_type="session")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    record_audit(db, request, action="login", resource_type="session", actor=user)
    db.commit()
    token = create_session_token(user)
    set_session_cookie(response, token, request=request)
    return AuthResponse(
        user=UserResponse.model_validate(user),
        expires_in=get_settings().session_ttl_seconds,
        token=token,
    )


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
                record_audit(db, request, action="logout", resource_type="session", actor=user)
                db.commit()
        except (KeyError, TypeError, ValueError):
            db.rollback()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


@router.get("/me", response_model=UserResponse)
def current_user(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, db: Db, request: Request
) -> None:
    try:
        auth_service.change_password(db, user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_audit(db, request, action="password_changed", resource_type="user", actor=user)
    db.commit()


@router.post("/password-reset/request")
def request_password_reset(
    payload: PasswordResetRequest, db: Db, request: Request
) -> dict[str, str]:
    enforce_rate_limit(request, bucket="auth-password-reset", limit=5, window_seconds=300)
    # Deliberately generic: account existence must not be exposed to callers.
    auth_service.request_password_reset(db, str(payload.email), payload.institution_slug)
    return {"message": "If the account exists, reset instructions will be sent securely."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm, db: Db, request: Request) -> None:
    enforce_rate_limit(request, bucket="auth-password-reset-confirm", limit=5, window_seconds=300)
    try:
        auth_service.reset_password(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
