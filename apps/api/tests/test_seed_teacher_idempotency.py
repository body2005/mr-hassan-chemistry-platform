import importlib.util
import pytest
from pathlib import Path

from app.core.security import hash_password, verify_password
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.models.user import GradeLevel


def test_preview_students_are_opt_in_private_and_idempotent_in_production(db, monkeypatch):
    seed = _seed_module()
    institution = Institution(name="Preview test", slug="preview-test")
    db.add(institution)
    db.commit()
    monkeypatch.setenv("INITIAL_INSTITUTION_SLUG", institution.slug)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SEED_PREVIEW_STUDENTS", "false")
    seed.seed()
    assert db.query(User).count() == 0
    monkeypatch.setenv("SEED_PREVIEW_STUDENTS", "true")
    monkeypatch.setenv("DEMO_STUDENT_PASSWORD", "short")
    with pytest.raises(RuntimeError, match="private DEMO_STUDENT_PASSWORD"):
        seed.seed()
    assert db.query(User).count() == 0
    monkeypatch.setenv("DEMO_STUDENT_PASSWORD", "Private-test-secret!2026")
    seed.seed()
    students = db.query(User).order_by(User.username).all()
    assert len(students) == 3
    assert [u.email for u in students] == [f"student{n:02d}@demo.com" for n in range(1, 4)]
    assert [u.grade_level for u in students] == [g.value for g in GradeLevel]
    assert all(u.role == UserRole.STUDENT and verify_password("Private-test-secret!2026", u.password_hash) for u in students)
    from fastapi.testclient import TestClient
    from app.main import app
    for student in students:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/login", json={"email": student.email,
                "password": "Private-test-secret!2026", "institution_slug": institution.slug})
            assert response.status_code == 200
            assert response.json()["user"]["grade_level"] == student.grade_level
            assert client.get("/api/v1/auth/me").status_code == 200
    hashes = [u.password_hash for u in students]
    monkeypatch.setenv("DEMO_STUDENT_PASSWORD", "Different-private-test-secret")
    seed.seed()
    assert [u.password_hash for u in db.query(User).order_by(User.username)] == hashes


def test_preview_students_do_not_repurpose_existing_accounts(db, monkeypatch):
    seed = _seed_module()
    inst = Institution(name="Collision test", slug="collision-test")
    db.add(inst)
    db.flush()
    db.add(User(institution_id=inst.id, email="student03@demo.com", username="existing-teacher",
        display_name="Teacher", password_hash=hash_password("Existing-private-secret"), role=UserRole.TEACHER))
    db.commit()
    monkeypatch.setenv("SEED_PREVIEW_STUDENTS", "true")
    monkeypatch.setenv("INITIAL_INSTITUTION_SLUG", inst.slug)
    monkeypatch.setenv("DEMO_STUDENT_PASSWORD", "Private-test-secret!2026")
    with pytest.raises(RuntimeError, match="conflicts"):
        seed.seed()
    assert db.query(User).count() == 1
    assert db.query(User).one().role == UserRole.TEACHER


def _seed_module():
    script = Path(__file__).parents[1] / "scripts" / "seed_teacher.py"
    spec = importlib.util.spec_from_file_location("seed_teacher_script", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("flag", ["ENABLE_DEMO_ACCOUNTS", "RESET_DEMO_PASSWORDS", "RESET_INITIAL_TEACHER_PASSWORD"])
@pytest.mark.parametrize("environment", ["production", "production_like", "staging"])
def test_production_seed_rejects_demo_and_password_reset(db, monkeypatch, flag, environment):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv(flag, "true")
    with pytest.raises(RuntimeError, match="Production seeding"):
        _seed_module().seed()
    assert db.query(User).count() == 0


@pytest.mark.parametrize("environment", ["production", "production_like", "staging"])
def test_production_seed_rejects_published_short_password(db, monkeypatch, environment):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("INITIAL_TEACHER_PASSWORD", "admin")
    with pytest.raises(RuntimeError, match="private password"):
        _seed_module().seed()


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


def test_demo_seed_creates_ten_fixed_student_identities(db, monkeypatch):
    seed_teacher = _seed_module()
    monkeypatch.setenv("ENABLE_DEMO_ACCOUNTS", "true")
    monkeypatch.setenv("DEMO_TEACHER_PASSWORD", "TeacherDemo!2026")
    monkeypatch.setenv("DEMO_STUDENT_PASSWORD", "StudentDemo!2026")
    monkeypatch.setenv("DEMO_INSTITUTION_SLUG", "demo")

    seed_teacher.seed()
    institution = db.query(Institution).filter(Institution.slug == "demo").one()
    students = (
        db.query(User)
        .filter(User.institution_id == institution.id, User.role == UserRole.STUDENT)
        .order_by(User.email)
        .all()
    )
    assert [student.email for student in students] == [
        f"student{number:02d}@demo.com" for number in range(1, 11)
    ]
    assert all(verify_password("StudentDemo!2026", student.password_hash) for student in students)

    # A normal deployment rerun is idempotent and does not rotate credentials.
    seed_teacher.seed()
    assert db.query(User).filter(User.institution_id == institution.id, User.role == UserRole.STUDENT).count() == 10
