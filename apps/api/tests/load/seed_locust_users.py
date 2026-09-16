import json
import uuid
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password, create_session_token
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.models.course import Course, Enrollment

def seed_load_users(count: int = 100) -> list[str]:
    with SessionLocal() as db:
        institution = db.scalar(select(Institution).where(Institution.slug == "demo"))
        if not institution:
            institution = Institution(name="Demo Academy", slug="demo")
            db.add(institution)
            db.flush()

        course = db.scalar(select(Course).limit(1))
        
        # Check existing
        existing_users = {
            u.email: u for u in db.scalars(
                select(User).where(User.email.like("loaduser_%@chemistry.com"))
            ).all()
        }

        default_pwd_hash = hash_password("LoadTestPassword123!")
        users_to_add = []
        tokens = []

        for i in range(1, count + 1):
            email = f"loaduser_{i}@chemistry.com"
            user = existing_users.get(email)
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    institution_id=institution.id,
                    username=f"loaduser_{i}",
                    email=email,
                    display_name=f"Load User {i}",
                    password_hash=default_pwd_hash,
                    role=UserRole.STUDENT,
                    is_active=True,
                )
                users_to_add.append(user)
                if course:
                    enrollment = Enrollment(
                        student_id=user.id,
                        course_id=course.id,
                    )
                    db.add(enrollment)
            token = create_session_token(user)
            tokens.append(token)

        if users_to_add:
            db.add_all(users_to_add)
            db.commit()
            print(f"Seeded {len(users_to_add)} new load test users.")
        else:
            print(f"All {count} load test users already exist.")

        with open("/srv/tests/load/locust_users.json", "w", encoding="utf-8") as f:
            json.dump({"tokens": tokens}, f)
        print(f"Generated {len(tokens)} tokens and saved to /srv/tests/load/locust_users.json")
        return tokens

if __name__ == "__main__":
    seed_load_users(100)
