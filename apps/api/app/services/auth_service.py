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
        )
    )

    if user is None or not user.is_active:
        return None

    pwd_valid = verify_password(payload.password, user.password_hash)
    if not pwd_valid:
        return None

    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, payload: ChangePasswordRequest) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise ValueError("Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()


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
    token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(payload.token),
            PasswordResetToken.used_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    if token is None or token.expires_at <= now:
        raise ValueError("Reset token is invalid or expired")

    token.user.password_hash = hash_password(payload.new_password)
    token.used_at = now
    db.commit()
