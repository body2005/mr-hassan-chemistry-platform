"""
Seed script: creates a fresh database with just the teacher account.
Run from the apps/api directory:
    python -m scripts.seed_teacher
"""
import sys
import os

# Ensure the api package root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, SessionLocal
from app.models import Base
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.core.security import hash_password


def seed():
    # Create all tables
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Check if teacher already exists
        existing = db.query(User).filter(User.role == UserRole.TEACHER).first()
        if existing:
            print(f"Teacher already exists: {existing.display_name} ({existing.email})")
            return

        # Create institution
        institution = db.query(Institution).filter(Institution.slug == "demo").first()
        if not institution:
            institution = Institution(name="Demo", slug="demo")
            db.add(institution)
            db.flush()

        # Create teacher
        teacher = User(
            institution_id=institution.id,
            username="mr.hassan",
            email="teacher@hassanshaban.com",
            display_name="مستر حسن شعبان",
            password_hash=hash_password("Hassan@2025"),
            role=UserRole.TEACHER,
            is_active=True,
        )
        db.add(teacher)
        db.commit()
        print(f"✅ Teacher created: {teacher.display_name}")
        print(f"   Email: {teacher.email}")
        print(f"   Password: Hassan@2025")


if __name__ == "__main__":
    seed()
