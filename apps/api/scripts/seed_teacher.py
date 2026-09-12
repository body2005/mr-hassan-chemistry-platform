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


def seed():
    # Create all tables
    Base.metadata.create_all(bind=engine)

    teacher_email = os.getenv("INITIAL_TEACHER_EMAIL", "teacher@hassanshaban.com").strip().lower() or "teacher@hassanshaban.com"
    teacher_username = os.getenv("INITIAL_TEACHER_USERNAME", "mr.hassan").strip().lower() or "mr.hassan"
    teacher_password = os.getenv("INITIAL_TEACHER_PASSWORD", "").strip() or "Hassan@2025"
    teacher_name = os.getenv("INITIAL_TEACHER_NAME", "مستر حسن شعبان").strip() or "مستر حسن شعبان"
    institution_slug = os.getenv("INITIAL_INSTITUTION_SLUG", "demo").strip().lower() or "demo"

    with SessionLocal() as db:
        # Create institution if missing
        institution = db.query(Institution).filter(Institution.slug == institution_slug).first()
        if not institution:
            institution = Institution(name=institution_slug.replace("-", " ").title(), slug=institution_slug)
            db.add(institution)
            db.flush()

        # Check if primary teacher already exists by email or username
        existing = db.query(User).filter(
            User.institution_id == institution.id,
            (User.email == teacher_email) | (User.username == teacher_username)
        ).first()

        if existing:
            existing.email = teacher_email
            existing.username = teacher_username
            existing.display_name = teacher_name
            existing.password_hash = hash_password(teacher_password)
            existing.is_active = True
            existing.role = UserRole.TEACHER
            db.commit()
            print(f"[seed] Teacher account verified: {existing.username} ({existing.email})")
            teacher = existing
        else:
            # Create teacher
            teacher = User(
                institution_id=institution.id,
                username=teacher_username,
                email=teacher_email,
                display_name=teacher_name,
                password_hash=hash_password(teacher_password),
                role=UserRole.TEACHER,
                is_active=True,
            )
            db.add(teacher)
            db.commit()
            print(f"[seed] Teacher created: {teacher.username} ({teacher.email})")

        # Ensure demo teacher has valid password if present
        demo_t = db.query(User).filter(User.institution_id == institution.id, User.email == "teacher@demo.com").first()
        if demo_t and demo_t.id != teacher.id:
            demo_t.password_hash = hash_password(teacher_password)
            demo_t.is_active = True
            db.commit()

        # Ensure official chemistry course exists
        from app.models.course import Course, CourseStatus
        course = db.query(Course).filter(Course.institution_id == institution.id).first()
        if not course:
            course = Course(
                institution_id=institution.id,
                teacher_id=teacher.id,
                code="CHEM-3SEC",
                title="الكيمياء - الصف الثالث الثانوي",
                description="منهج الكيمياء للثانوية العامة — مستر حسن شعبان",
                status=CourseStatus.PUBLISHED,
            )
            db.add(course)
            db.commit()
            print(f"[seed] Default course created: {course.code}")


if __name__ == "__main__":
    seed()

