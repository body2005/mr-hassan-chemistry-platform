"""Create the initial teacher only when deployment credentials are supplied."""
import sys
import os

# Ensure the api package root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, SessionLocal
from app.models import Base
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.core.security import hash_password


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def seed():
    # Create all tables
    Base.metadata.create_all(bind=engine)

    teacher_email = os.getenv("INITIAL_TEACHER_EMAIL", "").strip().lower()
    teacher_password = os.getenv("INITIAL_TEACHER_PASSWORD", "")
    teacher_name = os.getenv("INITIAL_TEACHER_NAME", "مستر حسن شعبان").strip()
    institution_slug = os.getenv("INITIAL_INSTITUTION_SLUG", "demo").strip().lower()
    if not teacher_email or not teacher_password:
        print("Initial teacher seed skipped: set INITIAL_TEACHER_EMAIL and INITIAL_TEACHER_PASSWORD.")
        return

    with SessionLocal() as db:
        # Create institution
        institution = db.query(Institution).filter(Institution.slug == institution_slug).first()
        if not institution:
            institution = Institution(name=institution_slug.replace("-", " ").title(), slug=institution_slug)
            db.add(institution)
            db.flush()

        existing = db.query(User).filter(
            User.institution_id == institution.id,
            User.email == teacher_email,
        ).first()
        if existing:
            if _env_flag("RESET_INITIAL_TEACHER_PASSWORD"):
                existing.password_hash = hash_password(teacher_password)
                existing.is_active = True
                existing.deleted_at = None
                db.commit()
                print(f"Teacher password reset from deployment secret: {existing.email}")
            else:
                print(f"Teacher already exists: {existing.display_name} ({existing.email})")
            return

        # Create teacher
        teacher = User(
            institution_id=institution.id,
            username=os.getenv("INITIAL_TEACHER_USERNAME", teacher_email.split("@", 1)[0]).strip().lower(),
            email=teacher_email,
            display_name=teacher_name,
            password_hash=hash_password(teacher_password),
            role=UserRole.TEACHER,
            is_active=True,
        )
        db.add(teacher)
        db.commit()
        print(f"✅ Teacher created: {teacher.display_name}")
        print(f"   Email: {teacher.email}")


if __name__ == "__main__":
    seed()
