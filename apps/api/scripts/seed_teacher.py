"""Seed deployment accounts only when their Render secrets are supplied."""
import os
import sys

# Ensure the api package root is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine
from app.core.security import hash_password, verify_password
from app.models import Base
from app.models.institution import Institution
from app.models.user import User, UserRole


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _get_or_create_institution(db, slug: str, name: str | None = None) -> Institution:
    institution = db.query(Institution).filter(Institution.slug == slug).first()
    if institution:
        return institution
    institution = Institution(name=name or slug.replace("-", " ").title(), slug=slug)
    db.add(institution)
    db.flush()
    return institution


def _seed_account(
    db,
    *,
    institution: Institution,
    email: str,
    username: str,
    display_name: str,
    password: str,
    role: UserRole,
    reset_password: bool,
    ensure_password_matches: bool = False,
    label: str,
) -> None:
    existing = db.query(User).filter(
        User.institution_id == institution.id,
        User.email == email,
    ).first()

    if existing:
        changed = False
        if existing.role != role:
            existing.role = role
            changed = True
        if not existing.is_active or existing.deleted_at is not None:
            existing.is_active = True
            existing.deleted_at = None
            changed = True
        if existing.username != username:
            existing.username = username
            changed = True
        if existing.display_name != display_name:
            existing.display_name = display_name
            changed = True
        if reset_password or (ensure_password_matches and not verify_password(password, existing.password_hash)):
            existing.password_hash = hash_password(password)
            changed = True
        if changed:
            db.commit()
            print(f"{label} updated from deployment configuration: {email}")
        else:
            print(f"{label} already exists: {email}")
        return

    account = User(
        institution_id=institution.id,
        username=username,
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(account)
    db.commit()
    print(f"{label} created: {email}")


def seed() -> None:
    teacher_email = os.getenv("INITIAL_TEACHER_EMAIL", "").strip().lower()
    teacher_password = os.getenv("INITIAL_TEACHER_PASSWORD", "")
    demo_enabled = _env_flag("ENABLE_DEMO_ACCOUNTS")

    with SessionLocal() as db:
        if teacher_email and teacher_password:
            institution_slug = os.getenv("INITIAL_INSTITUTION_SLUG", "demo").strip().lower()
            institution = _get_or_create_institution(db, institution_slug)
            _seed_account(
                db,
                institution=institution,
                email=teacher_email,
                username=os.getenv(
                    "INITIAL_TEACHER_USERNAME", teacher_email.split("@", 1)[0]
                ).strip().lower(),
                display_name=os.getenv("INITIAL_TEACHER_NAME", "مستر حسن شعبان").strip(),
                password=teacher_password,
                role=UserRole.TEACHER,
                reset_password=_env_flag("RESET_INITIAL_TEACHER_PASSWORD"),
                label="Initial teacher",
            )
        else:
            print(
                "Initial teacher seed skipped: set INITIAL_TEACHER_EMAIL "
                "and INITIAL_TEACHER_PASSWORD."
            )

        if not demo_enabled:
            print("Demo account seed disabled.")
            return

        demo_teacher_password = os.getenv("DEMO_TEACHER_PASSWORD", "")
        demo_student_password = os.getenv("DEMO_STUDENT_PASSWORD", "")
        if not demo_teacher_password or not demo_student_password:
            print(
                "Demo account seed skipped: set DEMO_TEACHER_PASSWORD "
                "and DEMO_STUDENT_PASSWORD."
            )
            return

        demo_slug = os.getenv("DEMO_INSTITUTION_SLUG", "demo").strip().lower()
        demo_institution = _get_or_create_institution(
            db,
            demo_slug,
            os.getenv("DEMO_INSTITUTION_NAME", "Demo Chemistry Academy").strip(),
        )
        reset_demo_passwords = _env_flag("RESET_DEMO_PASSWORDS")

        _seed_account(
            db,
            institution=demo_institution,
            email=os.getenv("DEMO_TEACHER_EMAIL", "teacher@demo.com").strip().lower(),
            username=os.getenv("DEMO_TEACHER_USERNAME", "teacher").strip().lower(),
            display_name=os.getenv("DEMO_TEACHER_NAME", "Demo Teacher").strip(),
            password=demo_teacher_password,
            role=UserRole.TEACHER,
            reset_password=reset_demo_passwords,
            ensure_password_matches=False,
            label="Demo teacher",
        )
        _seed_account(
            db,
            institution=demo_institution,
            email=os.getenv("DEMO_STUDENT_EMAIL", "student@demo.com").strip().lower(),
            username=os.getenv("DEMO_STUDENT_USERNAME", "student").strip().lower(),
            display_name=os.getenv("DEMO_STUDENT_NAME", "Demo Student").strip(),
            password=demo_student_password,
            role=UserRole.STUDENT,
            reset_password=reset_demo_passwords,
            ensure_password_matches=False,
            label="Demo student",
        )

        if reset_demo_passwords:
            for email, password in (
                (os.getenv("DEMO_TEACHER_EMAIL", "teacher@demo.com").strip().lower(), demo_teacher_password),
                (os.getenv("DEMO_STUDENT_EMAIL", "student@demo.com").strip().lower(), demo_student_password),
            ):
                seeded = db.query(User).filter(
                    User.institution_id == demo_institution.id,
                    User.email == email,
                ).first()
                if not seeded or not verify_password(password, seeded.password_hash):
                    raise RuntimeError(f"Demo credential reconciliation failed for {email}")


if __name__ == "__main__":
    seed()
