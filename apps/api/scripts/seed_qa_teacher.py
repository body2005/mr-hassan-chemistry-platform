"""Create ONE unique synthetic teacher for a serial local browser QA case.

Never enabled on external production. Avoids sharing the demo user's auth
budget or revoking a human's session; real rate limits stay enabled unchanged.
"""
import json
import os
import uuid
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.institution import Institution
from app.models.user import User, UserRole


def main():
    if os.getenv("QA_ISOLATED") != "true" or os.getenv("QA_PROJECT") not in {"chemistryaudit2", "chemistryprodlocal"}:
        raise RuntimeError("Synthetic QA user creation is restricted to the allowlisted local test project")
    stamp = uuid.uuid4().hex
    # The API validates public-domain EmailStr values (reserved .test is not
    # accepted). This synthetic namespace is never used to send external mail.
    email = f"qa-publication-{stamp}@demo.com"
    password = "qa-publication-only-pass"
    with SessionLocal() as db:
        inst = db.scalar(select(Institution).where(Institution.slug == "demo"))
        assert inst is not None, "Seed the isolated demo institution first"
        for previous in db.scalars(select(User).where(User.institution_id == inst.id,
                User.email.like('qa-publication-%@example.test'), User.username.like('qa-pub-%'), User.role == UserRole.TEACHER)):
            previous.email = previous.email.removesuffix('@example.test') + '@demo.com'
        db.add(User(institution_id=inst.id, username=f"qa-pub-{stamp}", email=email,
                    display_name="Synthetic publication QA", role=UserRole.TEACHER,
                    password_hash=hash_password(password), is_active=True))
        db.commit()
    print(json.dumps({"email": email, "password": password}))


if __name__ == "__main__":
    main()
