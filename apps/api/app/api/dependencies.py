from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataclasses import dataclass
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_preview_token, decode_session_token
from app.models.platform import RevokedSession
from app.models.user import User, UserRole

DbSession = Annotated[Session, Depends(get_db)]


def _extract_token(request: Request, session_cookie: str | None = None) -> str | None:
    # An explicit Authorization header must win over a stale browser cookie.
    # The SPA keeps the freshly issued token in localStorage, while browsers
    # can retain or reject cross-site cookie deletion independently.
    # CRITICAL: General session authentication must NEVER extract ambient ?token=
    # query parameters, which are strictly reserved for scoped preview tokens.
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    if session_cookie:
        return session_cookie
    return None


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


@dataclass
class PreviewAuthContext:
    user_id: uuid.UUID
    institution_id: uuid.UUID
    source_id: uuid.UUID
    user: User
    is_preview_token: bool = False


def get_preview_auth_context(
    request: Request,
    db: DbSession,
    session_cookie: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> PreviewAuthContext:
    """
    Dedicated dependency for preview-file, preview-page, and media streaming endpoints.
    Allows authentication via:
    1) A scoped preview token (in query param ?token= or Authorization header) with aud='preview'
       matching the path parameter {source_id}.
    2) A valid session credential (Bearer header or session cookie) for authorized users.
    Rejects any preview token being used against a different source_id.
    """
    path_source_id_str = request.path_params.get("source_id")
    expected_source_id: uuid.UUID | None = None
    if path_source_id_str:
        try:
            expected_source_id = uuid.UUID(str(path_source_id_str))
        except (ValueError, TypeError):
            pass

    # 1. Check for dedicated preview token in query parameter
    query_token = request.query_params.get("token")
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    bearer_token = auth_header[7:].strip() if (auth_header and auth_header.lower().startswith("bearer ")) else None

    # Check candidates for preview token
    for cand in [query_token, bearer_token]:
        if not cand:
            continue
        payload = decode_preview_token(cand)
        if payload:
            token_source_str = payload.get("source_id")
            token_sub_str = payload.get("sub") or payload.get("user_id")
            token_inst_str = payload.get("institution_id")
            if not token_source_str or not token_sub_str or not token_inst_str:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed preview token")

            token_source_id = uuid.UUID(str(token_source_str))
            token_user_id = uuid.UUID(str(token_sub_str))
            token_institution_id = uuid.UUID(str(token_inst_str))

            if expected_source_id and token_source_id != expected_source_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Preview token is not valid for this source",
                )

            user = db.scalar(
                select(User).where(
                    User.id == token_user_id,
                    User.institution_id == token_institution_id,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                )
            )
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session user no longer exists",
                )

            return PreviewAuthContext(
                user_id=user.id,
                institution_id=user.institution_id,
                source_id=token_source_id,
                user=user,
                is_preview_token=True,
            )

    # 2. Check for standard session token via Bearer header or session cookie
    session_token = _extract_token(request, session_cookie)
    if session_token:
        payload = decode_session_token(session_token)
        if payload and payload.get("sub") and payload.get("institution_id"):
            u_id = uuid.UUID(str(payload["sub"]))
            inst_id = uuid.UUID(str(payload["institution_id"]))
            user = db.scalar(
                select(User).where(
                    User.id == u_id,
                    User.institution_id == inst_id,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                )
            )
            if user:
                jti = str(payload.get("jti", ""))
                if jti and not db.scalar(select(RevokedSession.id).where(RevokedSession.jti == jti)):
                    return PreviewAuthContext(
                        user_id=user.id,
                        institution_id=user.institution_id,
                        source_id=expected_source_id or uuid.uuid4(),
                        user=user,
                        is_preview_token=False,
                    )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required for preview access",
    )


PreviewAuth = Annotated[PreviewAuthContext, Depends(get_preview_auth_context)]
