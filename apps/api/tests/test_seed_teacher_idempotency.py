import importlib.util
from pathlib import Path

from app.core.security import hash_password, verify_password
from app.models.institution import Institution
from app.models.user import User, UserRole


def _seed_module():
    script = Path(__file__).parents[1] / "scripts" / "seed_teacher.py"
    spec = importlib.util.spec_from_file_location("seed_teacher_script", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_reconciles_email_by_username_without_resetting_password(db):
    seed_teacher = _seed_module()
    institution = Institution(name="Seed test", slug="seed-test")
    db.add(institution)
    db.flush()
    original_password = "existing-password"
    account = User(
        institution_id=institution.id,
        username="teacher",
        email="old-email@example.test",
        display_name="Existing Teacher",
        password_hash=hash_password(original_password),
        role=UserRole.TEACHER,
        is_active=True,
    )
    db.add(account)
    db.commit()

    seed_teacher._seed_account(
        db,
        institution=institution,
        username="teacher",
        email="new-email@example.test",
        display_name="Updated Teacher",
        password="deployment-secret-that-must-not-replace-the-login",
        role=UserRole.TEACHER,
        reset_password=False,
        label="Initial teacher",
    )

    accounts = db.query(User).filter(User.institution_id == institution.id).all()
    assert len(accounts) == 1
    assert accounts[0].email == "new-email@example.test"
    assert accounts[0].display_name == "Updated Teacher"
    assert verify_password(original_password, accounts[0].password_hash)
    assert not verify_password(
        "deployment-secret-that-must-not-replace-the-login", accounts[0].password_hash
    )
