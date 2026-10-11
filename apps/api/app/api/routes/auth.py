from __future__ import annotations

import secrets
import logging
import uuid
from datetime import datetime, timedelta, timezone
UTC = timezone.utc
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit, resolve_client_ip
from app.core.security import create_session_token, decode_session_token, hash_token

# A rotated refresh token replayed within this window is treated as a racing
# tab (normal multi-tab behavior) rather than credential theft: the tab gets a
# fresh session instead of the whole family being revoked.
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
from app.services.mail_service import password_reset_mail_configured
from app.services.audit_service import record_audit

router = APIRouter(prefix="/auth")
Db = Annotated[Session, Depends(get_db)]
logger = logging.getLogger(__name__)


@router.post("/avatar", include_in_schema=False)
def account_photo_upload_removed(request: Request, user: CurrentUser):
    # Explicit product decision: no personal photos for any account role.
    # Keep a closed legacy endpoint so old clients get a clear outcome. Do
    # not parse/process the image or mutate/delete existing private objects.
    enforce_rate_limit(request, bucket="avatar", limit=10, window_seconds=60)
    raise HTTPException(410, "Personal account photos are not supported")


@router.get("/avatar", include_in_schema=False)
def account_photo_read_removed(user: CurrentUser):
    raise HTTPException(410, "Personal account photos are not supported")


@router.get("/profile-summary")
def profile_summary(user: CurrentUser, db: Db):
    from app.models.user import UserRole
    from app.models.course import Course, CourseModule, Lesson, Enrollment, EnrollmentStatus
    from app.models.progress import LessonProgress
    if user.role == UserRole.STUDENT:
        rows = db.execute(select(LessonProgress, Lesson.title).join(Lesson, Lesson.id == LessonProgress.lesson_id)
                          .where(LessonProgress.student_id == user.id, LessonProgress.institution_id == user.institution_id)).all()
        return {"progress": [{"lesson_id": str(p.lesson_id), "title": title, "completion_percent": p.completion_percent} for p, title in rows]}
    managed = select(Course.id).where(Course.institution_id == user.institution_id)
    if user.role == UserRole.TEACHER:
        managed = managed.where(Course.teacher_id == user.id)
    # Unique active/completed students across owned courses, not enrollments.
    students = db.scalar(select(func.count(func.distinct(Enrollment.student_id))).join(User, User.id == Enrollment.student_id)
                         .where(Enrollment.course_id.in_(managed), Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
                                User.is_active.is_(True), User.deleted_at.is_(None))) or 0
    # Count lessons with a stored ready video, not pending upload jobs.
    videos = db.scalar(select(func.count(Lesson.id))
                       .where(Lesson.course_id.in_(managed), Lesson.kind == "video", Lesson.video_asset_key.is_not(None))) or 0
    return {"enrolled_students_count": students, "uploaded_videos_count": videos}


def _cookie_options(request: Request | None = None) -> tuple[str, bool]:
    settings = get_settings()
    is_https = False
    if request:
        # Uvicorn applies forwarded headers only for explicitly trusted peers.
        # Never trust a raw client-supplied X-Forwarded-Proto here.
        is_https = request.url.scheme.lower() == "https"
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
    # Apply before DB/password work. No plaintext account identifiers in keys.
    client_ip = resolve_client_ip(request)
    account_identity = payload.institution_slug.strip().lower() + ":" + auth_service.normalize_email(payload.email)
    # Short, distributed admission backoff, capped at ten seconds. Pairing
    # account+IP prevents a remote attacker imposing this cooldown on every
    # device of a victim. Existing IP/account rolling budgets remain active.
    # Count attempts uniformly (not account existence); no sleeps/DB locks.
    enforce_rate_limit(request, bucket="login_retry", limit=4, window_seconds=10,
                       identity=account_identity + ":" + client_ip)
    # Rejected short retries must not consume/extend the account-wide budget.
    enforce_rate_limit(request, bucket="login_ip", limit=12, window_seconds=60,
                       identity=client_ip)
    enforce_rate_limit(request, bucket="login_account", limit=20, window_seconds=300,
                       identity=account_identity)
    user = auth_service.authenticate(db, payload)
    if user is None:
        record_audit(db, request, action="login_failed", resource_type="session")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    record_audit(db, request, action="login", resource_type="session", actor=user)
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
    token_hash = hash_token(refresh_cookie)
    owner_id = db.query(RefreshSession.user_id).filter(RefreshSession.token_hash == token_hash).scalar()
    # Stable lock order for refresh/password/reset/revoke: user, then token.
    user = db.query(User).filter(User.id == owner_id).with_for_update().populate_existing().one_or_none()
    # Lock the consumed row.  On PostgreSQL this makes two simultaneous
    # refreshes deterministic: one rotates it and the other observes replay.
    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_hash == token_hash)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if session is None:
        _clear_auth_cookies(response, request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session is invalid")
    if user is None or not user.is_active or user.deleted_at is not None or _as_utc(session.expires_at) <= now:
        session.revoked_at = now
        db.commit()
        _clear_auth_cookies(response, request)
        raise HTTPException(status_code=401, detail="Refresh session is invalid or expired")
    if session.revoked_at is not None:
        if session.replaced_by:
            # Grace window: a rotated token replayed seconds later is the
            # normal multi-tab race (two tabs refresh simultaneously, the
            # slower one still carries the just-rotated cookie), not theft.
            # Hand the racing tab the family's current credential instead of
            # killing the whole family and logging the user out.
            grace_cutoff = now - timedelta(seconds=get_settings().refresh_replay_grace_seconds)
            successor = (
                db.query(RefreshSession)
                .filter(
                    RefreshSession.family_id == session.family_id,
                    RefreshSession.revoked_at.is_(None),
                    RefreshSession.expires_at > now,
                    RefreshSession.created_at >= grace_cutoff,
                )
                .order_by(RefreshSession.created_at.desc())
                .first()
            )
            if successor is not None and _as_utc(session.revoked_at) >= grace_cutoff:
                result = _auth_response(user, session.family_id, db, response, request)
                record_audit(db, request, action="session_refreshed", resource_type="session", actor=user)
                db.commit()
                return result
            db.query(RefreshSession).filter(
                RefreshSession.family_id == session.family_id,
                RefreshSession.revoked_at.is_(None),
            ).update({RefreshSession.revoked_at: now}, synchronize_session=False)
            from app.models.platform import Notification, DeliveryStatus
            dedup = "refresh-reuse:" + str(session.family_id)
            if not db.scalar(select(Notification.id).where(
                    Notification.recipient_id == user.id, Notification.dedup_key == dedup)):
                record_audit(db, request, action="refresh_reuse_detected", resource_type="session", actor=user)
                db.add(Notification(institution_id=user.institution_id, recipient_id=user.id,
                    kind="security", title="أُغلقت جلسة تسجيل دخول",
                    message="أُعيد استخدام جلسة قديمة بعد انتهاء مهلة التزامن؛ أُغلق هذا الجهاز احتياطيًا. إذا لم تتوقع ذلك، غيّر كلمة المرور.",
                    action_url="#profile", dedup_key=dedup, delivered_at=now,
                    delivery_status=DeliveryStatus.DELIVERED))
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
    refresh_hash = hash_token(request.cookies.get(settings.refresh_cookie_name, ''))
    refresh_owner = db.scalar(select(RefreshSession.user_id).where(RefreshSession.token_hash == refresh_hash))
    # Use the opaque refresh hash, not unverified JWT claims. Lock order is
    # the same as rotation: user first, refresh row second.
    if not payload and refresh_owner:
        user = db.scalar(select(User).where(User.id == refresh_owner).with_for_update())
        row = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == refresh_hash)
                        .with_for_update().execution_options(populate_existing=True))
        if user and row and _as_utc(row.expires_at) > datetime.now(UTC):
            db.query(RefreshSession).filter(RefreshSession.user_id == user.id,
                RefreshSession.family_id == row.family_id, RefreshSession.revoked_at.is_(None)).update(
                    {RefreshSession.revoked_at: datetime.now(UTC)}, synchronize_session=False)
            from app.api.routes.platform import _revoke_video_sessions
            _revoke_video_sessions(db, user.id, row.family_id, None)
            record_audit(db, request, action="logout", resource_type="session", actor=user)
            db.commit()
    if payload:
        try:
            user_id = uuid.UUID(str(payload["sub"]))
            user = db.query(User).filter(User.id == user_id).with_for_update().populate_existing().one_or_none()
            if user:
                if not db.query(RevokedSession.id).filter(RevokedSession.jti == str(payload["jti"])).first():
                    db.add(RevokedSession(
                        jti=str(payload["jti"]),
                        user_id=user.id,
                        expires_at=datetime.fromtimestamp(float(payload["exp"]), UTC),
                    ))
                family_id = payload.get("family_id")
                if family_id:
                    db.query(RefreshSession).filter(
                        RefreshSession.family_id == uuid.UUID(str(family_id)),
                        RefreshSession.revoked_at.is_(None),
                    ).update({RefreshSession.revoked_at: datetime.now(UTC)}, synchronize_session=False)
                # Kill any short-lived video tokens issued from this session:
                # playback must die with the session, not outlive it.
                from app.api.routes.platform import _revoke_video_sessions

                _revoke_video_sessions(
                    db,
                    user.id,
                    uuid.UUID(str(family_id)) if family_id else None,
                    str(payload["jti"]),
                )
                record_audit(db, request, action="logout", resource_type="session", actor=user)
                db.commit()
        except (KeyError, TypeError, ValueError):
            db.rollback()
    _clear_auth_cookies(response, request)


@router.get("/me", response_model=PrivateUserResponse)
def current_user(user: CurrentUser, db: Db) -> PrivateUserResponse:
    response = PrivateUserResponse.model_validate(user)
    if user.role.value != "student":
        counts = profile_summary(user, db)
        response.uploaded_videos_count = counts["uploaded_videos_count"]
        response.enrolled_students_count = counts["enrolled_students_count"]
    return response


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

    from app.api.routes.platform import clear_revoked_account_video_slots
    clear_revoked_account_video_slots(user.id)


@router.post("/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
def revoke_all_sessions(user: CurrentUser, db: Db, request: Request) -> None:
    db.query(User).filter(User.id == user.id).with_for_update().populate_existing().one()
    now = datetime.now(UTC)
    db.query(RefreshSession).filter(
        RefreshSession.user_id == user.id,
        RefreshSession.revoked_at.is_(None),
    ).update({RefreshSession.revoked_at: now}, synchronize_session=False)
    record_audit(db, request, action="sessions_revoked", resource_type="session", actor=user)
    db.commit()
    from app.api.routes.platform import clear_revoked_account_video_slots
    clear_revoked_account_video_slots(user.id)


@router.get("/features")
def auth_features() -> dict[str, bool]:
    return {"password_reset_enabled": password_reset_mail_configured()}


@router.post("/password-reset/request")
def request_password_reset(
    payload: PasswordResetRequest, db: Db, request: Request
) -> dict[str, str]:
    enforce_rate_limit(request, bucket="password_reset_request", limit=5, window_seconds=300)
    if not password_reset_mail_configured():
        raise HTTPException(status_code=503, detail="Password reset by email is not enabled")
    # Deliberately generic: account existence must not be exposed to callers.
    from app.services.session_maintenance import enqueue_reset_request
    try:
        enqueue_reset_request(db, str(payload.email), payload.institution_slug)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Password reset is temporarily unavailable",
                            headers={"Retry-After": "1"}) from exc
    return {"message": "If the account exists, reset instructions will be sent securely."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm, db: Db, request: Request) -> None:
    enforce_rate_limit(request, bucket="password_reset_confirm", limit=5, window_seconds=300)
    try:
        auth_service.reset_password(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
