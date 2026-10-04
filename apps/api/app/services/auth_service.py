from __future__ import annotations

from datetime import datetime, timezone, timedelta
UTC = timezone.utc

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_password_reset_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.institution import Institution
from app.models.user import PasswordResetToken, User, UserRole
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    RegisterRequest,
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_registration_institution(db: Session, slug: str) -> Institution:
    normalized_slug = slug.strip().lower()
    institution = db.scalar(select(Institution).where(Institution.slug == normalized_slug))
    if institution is None:
        # Public registration must never turn arbitrary client input into a
        # tenant. Institutions are provisioned by the platform separately.
        raise ValueError("Registration is not available for this institution")
    return institution


def register_student(db: Session, payload: RegisterRequest) -> User:
    institution = get_registration_institution(db, payload.institution_slug)
    email = normalize_email(str(payload.email))
    username = (payload.username or email.split("@", 1)[0]).strip().lower()

    if db.scalar(select(User.id).where(User.institution_id == institution.id, User.email == email)):
        raise ValueError("Email address is already registered")
    if db.scalar(select(User.id).where(User.institution_id == institution.id, User.username == username)):
        raise ValueError("Username is already registered")
    if payload.national_id and db.scalar(
        select(User.id).where(
            User.institution_id == institution.id,
            User.national_id == payload.national_id,
        )
    ):
        raise ValueError("National ID is already registered")

    user = User(
        institution_id=institution.id,
        username=username,
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=UserRole.STUDENT,
        grade_level=payload.grade_level.value,
        student_phone=payload.student_phone,
        guardian_phone=payload.guardian_phone,
        national_id=payload.national_id,
        governorate=payload.governorate,
        school_name=payload.school_name,
        gender=payload.gender,
        religion=payload.religion,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Registration data conflicts with an existing account") from exc
    return user


def authenticate(db: Session, payload: LoginRequest) -> User | None:
    institution = db.scalar(
        select(Institution).where(Institution.slug == payload.institution_slug.strip().lower())
    )
    if institution is None:
        return None

    raw_ident = normalize_email(str(payload.email))
    user = db.scalar(
        select(User).where(
            User.institution_id == institution.id,
            (User.email == raw_ident) | (User.username == raw_ident),
            User.deleted_at.is_(None),
        ).with_for_update()
    )

    if user is None or not user.is_active:
        return None

    pwd_valid = verify_password(payload.password, user.password_hash)
    if not pwd_valid:
        return None

    user.last_login_at = datetime.now(UTC)
    db.flush()
    return user


def change_password(db: Session, user: User, payload: ChangePasswordRequest) -> None:
    user = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if not verify_password(payload.current_password, user.password_hash):
        raise ValueError("Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.flush()


def request_password_reset(db: Session, email: str, institution_slug: str) -> str | None:
    institution = db.scalar(
        select(Institution).where(Institution.slug == institution_slug.strip().lower())
    )
    if institution is None:
        return None
    user = db.scalar(
        select(User).where(
            User.institution_id == institution.id,
            User.email == normalize_email(email),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    if user is None:
        return None

    raw_token, token_hash = create_password_reset_token()
    now = datetime.now(UTC)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=get_settings().password_reset_ttl_minutes),
        )
    )
    db.commit()
    return raw_token


def reset_password(db: Session, payload: PasswordResetConfirm) -> None:
    owner_id = db.scalar(select(PasswordResetToken.user_id).where(PasswordResetToken.token_hash == hash_token(payload.token)))
    user = db.scalar(select(User).where(User.id == owner_id).with_for_update().execution_options(populate_existing=True))
    token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(payload.token),
            PasswordResetToken.used_at.is_(None),
        ).with_for_update().execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    # SQLite drops timezone metadata for DateTime columns; PostgreSQL keeps it.
    expires_at = token.expires_at if token is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if token is None or expires_at is None or expires_at <= now:
        raise ValueError("Reset token is invalid or expired")
    if user is None or not user.is_active or user.deleted_at is not None:
        raise ValueError("Reset token is invalid or expired")

    user.password_hash = hash_password(payload.new_password)
    token.used_at = now
    # A recovered account must not retain sessions created with the old secret.
    from app.models.platform import RefreshSession

    db.query(RefreshSession).filter(
        RefreshSession.user_id == token.user_id,
        RefreshSession.revoked_at.is_(None),
    ).update({RefreshSession.revoked_at: now}, synchronize_session=False)
    db.commit()
    from app.api.routes.platform import clear_revoked_account_video_slots
    clear_revoked_account_video_slots(token.user_id)
