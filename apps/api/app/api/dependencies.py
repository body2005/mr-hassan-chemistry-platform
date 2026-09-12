from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_session_token
from app.models.platform import RevokedSession
from app.models.user import User, UserRole

DbSession = Annotated[Session, Depends(get_db)]


def _extract_token(request: Request, session_cookie: str | None = None) -> str | None:
    # An explicit Authorization header must win over a stale browser cookie.
    # The SPA keeps the freshly issued token in localStorage, while browsers
    # can retain or reject cross-site cookie deletion independently.
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return session_cookie or None


def get_current_user(
    request: Request,
    db: DbSession,
    session_cookie: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> User:
    token = _extract_token(request, session_cookie)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    payload = decode_session_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
        )

    user_id = None
    institution_id = None
    try:
        if payload.get("sub"):
            user_id = uuid.UUID(str(payload["sub"]))
        if payload.get("institution_id"):
            institution_id = uuid.UUID(str(payload["institution_id"]))
    except (KeyError, ValueError):
        pass

    user = None
    if user_id and institution_id:
        user = db.scalar(
            select(User).where(
                User.id == user_id,
                User.institution_id == institution_id,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session user no longer exists; please sign in again",
        )
    if payload.get("role") != user.role.value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session role is no longer valid")
    jti = str(payload.get("jti", ""))
    if not jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    if db.scalar(select(RevokedSession.id).where(RevokedSession.jti == jti)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is revoked")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_user(
    request: Request,
    db: DbSession,
    session_cookie: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> User | None:
    token = _extract_token(request, session_cookie)
    if not token:
        return None
    try:
        payload = decode_session_token(token)
        if not payload:
            return None
        user_id = uuid.UUID(str(payload["sub"]))
        institution_id = uuid.UUID(str(payload["institution_id"]))
        user = db.scalar(
            select(User).where(
                User.id == user_id,
                User.institution_id == institution_id,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        if user is None:
            return None
        jti = str(payload.get("jti", ""))
        if not jti or db.scalar(select(RevokedSession.id).where(RevokedSession.jti == jti)):
            return None
        if payload.get("role") != user.role.value:
            return None
        return user
    except Exception:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*allowed_roles: UserRole) -> Callable[..., User]:
    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return user

    return dependency


def is_admin(user: User) -> bool:
    return user.role in {UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN}


def can_manage_courses(user: User) -> bool:
    return user.role in {
        UserRole.TEACHER,
        UserRole.INSTITUTION_ADMIN,
        UserRole.PLATFORM_ADMIN,
    }
