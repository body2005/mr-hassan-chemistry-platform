"""Isolated regressions for ECC-01, ECC-02 and ECC-07; no live services."""

import importlib.util
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from app.core.config import Settings
from app.models.course import Course, Enrollment, EnrollmentStatus
from app.models.institution import Institution
from app.models.platform import Notification
from app.models.user import User, UserRole
from app.schemas import NotificationBroadcastRequest, NotificationCreateRequest
from app.services import platform_service


def seed_module():
    path = Path(__file__).parents[1] / "scripts" / "seed_teacher.py"
    spec = importlib.util.spec_from_file_location("ecc_seed", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_user(db, institution, name, role=UserRole.STUDENT, **fields):
    user = User(
        institution_id=institution.id,
        username=name,
        email=f"{name}@example.test",
        display_name=name,
        password_hash="synthetic-existing-hash",
        role=role,
        **fields,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def institution(db):
    item = Institution(name="Isolated ECC", slug="ecc-isolated")
    db.add(item)
    db.flush()
    return item


def run_seed(db, institution, **overrides):
    arguments = dict(
        institution=institution,
        email="bootstrap@example.test",
        username="bootstrap",
        display_name="Bootstrap",
        password="synthetic-private-passphrase",
        role=UserRole.TEACHER,
        reset_password=False,
        label="Initial teacher",
    )
    arguments.update(overrides)
    seed_module()._seed_account(db, **arguments)


@pytest.mark.parametrize("collision", ["email", "username", "both"])
def test_seed_cannot_promote_student_collision(db, institution, collision):
    student = make_user(db, institution, "bootstrap" if collision != "email" else "other")
    if collision != "username":
        student.email = "bootstrap@example.test"
    db.commit()
    before = (student.email, student.username, student.role, student.password_hash)
    with pytest.raises(RuntimeError, match="conflict"):
        run_seed(db, institution)
    db.refresh(student)
    assert (student.email, student.username, student.role, student.password_hash) == before


@pytest.mark.parametrize("deleted", [False, True])
def test_seed_preserves_administrative_disable_and_deletion(db, institution, deleted):
    teacher = make_user(
        db,
        institution,
        "bootstrap",
        UserRole.TEACHER,
        is_active=False,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.commit()
    db.refresh(teacher)
    previous = (teacher.is_active, teacher.deleted_at, teacher.password_hash)
    run_seed(db, institution, reset_password=True)
    db.refresh(teacher)
    assert (teacher.is_active, teacher.deleted_at, teacher.password_hash) == previous


def test_seed_repeated_run_does_not_rewrite_profile_or_password(db, institution):
    run_seed(db, institution)
    teacher = db.scalar(select(User))
    teacher.display_name = "Administrator-chosen profile"
    db.commit()
    previous = (teacher.id, teacher.password_hash, teacher.display_name)
    run_seed(db, institution)
    db.refresh(teacher)
    assert (teacher.id, teacher.password_hash, teacher.display_name) == previous


def test_seed_does_not_revive_soft_deleted_active_identity(db, institution):
    teacher = make_user(
        db, institution, "bootstrap", UserRole.TEACHER, is_active=True, deleted_at=datetime.now(UTC)
    )
    db.commit()
    db.refresh(teacher)
    previous = (teacher.deleted_at, teacher.password_hash)
    run_seed(db, institution, reset_password=True)
    db.refresh(teacher)
    assert (teacher.deleted_at, teacher.password_hash) == previous


def test_seed_refuses_ambiguous_two_account_identity(db, institution):
    by_email = make_user(db, institution, "bootstrap", UserRole.TEACHER)
    by_email.username = "different"
    by_username = make_user(db, institution, "other", UserRole.TEACHER)
    by_username.username = "bootstrap"
    db.commit()
    with pytest.raises(RuntimeError, match="ambiguous"):
        run_seed(db, institution)
    assert db.scalar(select(User).where(User.username == "bootstrap")).id == by_username.id


@pytest.fixture
def audience(db, institution, monkeypatch):
    monkeypatch.setattr(platform_service.event_broker, "publish_event", lambda **kwargs: None)
    teacher = make_user(db, institution, "teacher", UserRole.TEACHER)
    linked = make_user(db, institution, "linked")
    unrelated = make_user(db, institution, "unrelated")
    colleague = make_user(db, institution, "colleague", UserRole.TEACHER)
    admin = make_user(db, institution, "admin", UserRole.INSTITUTION_ADMIN)
    platform = make_user(db, institution, "platform", UserRole.PLATFORM_ADMIN)
    deleted = make_user(db, institution, "deleted", deleted_at=datetime.now(UTC))
    inactive = make_user(db, institution, "inactive", is_active=False)
    withdrawn = make_user(db, institution, "withdrawn")
    other = Institution(name="Other tenant", slug="ecc-other")
    db.add(other)
    db.flush()
    foreign = make_user(db, other, "foreign")
    course = Course(
        institution_id=institution.id, teacher_id=teacher.id, code="ECC", title="Isolated course"
    )
    db.add(course)
    db.flush()
    for student in (linked, deleted, inactive, withdrawn):
        db.add(
            Enrollment(
                course_id=course.id,
                student_id=student.id,
                status=EnrollmentStatus.WITHDRAWN
                if student == withdrawn
                else EnrollmentStatus.ACTIVE,
            )
        )
    db.commit()
    return locals()


def payload(recipient):
    return NotificationCreateRequest(
        recipient_id=recipient.id, kind="system", title="Synthetic notice", message="Isolated test"
    )


@pytest.mark.parametrize(
    "recipient", ["unrelated", "colleague", "admin", "foreign", "deleted", "inactive", "withdrawn"]
)
def test_individual_notice_rejects_out_of_teacher_audience(db, audience, recipient):
    with pytest.raises((LookupError, PermissionError)):
        platform_service.create_notification(db, audience["teacher"], payload(audience[recipient]))
    assert db.scalar(select(Notification.id)) is None


@pytest.mark.parametrize("recipient", ["teacher", "linked"])
def test_individual_and_broadcast_have_identical_teacher_audience(db, audience, recipient):
    sender = audience["teacher"]
    individual = platform_service.create_notification(db, sender, payload(audience[recipient]))
    broadcast = platform_service.broadcast_notification(
        db,
        sender,
        NotificationBroadcastRequest(
            kind="system", title="Synthetic notice", message="Isolated test"
        ),
    )
    assert individual.recipient_id in {notice.recipient_id for notice in broadcast}
    assert {notice.recipient_id for notice in broadcast} == {sender.id, audience["linked"].id}


@pytest.mark.parametrize("role", ["admin", "platform"])
def test_admin_notices_remain_tenant_scoped(db, audience, role):
    notification = platform_service.create_notification(
        db, audience[role], payload(audience["colleague"])
    )
    assert notification.recipient_id == audience["colleague"].id
    with pytest.raises((LookupError, PermissionError)):
        platform_service.create_notification(db, audience[role], payload(audience["foreign"]))


def test_student_cannot_invoke_notification_service(db, audience):
    with pytest.raises(PermissionError):
        platform_service.create_notification(db, audience["linked"], payload(audience["linked"]))


def test_notifications_preserve_scheduling_deduplication_and_course_filter(
    db, audience, monkeypatch
):
    from datetime import timedelta

    calls = []
    monkeypatch.setattr(
        platform_service.event_broker, "publish_event", lambda **kwargs: calls.append(kwargs)
    )
    request = payload(audience["linked"])
    request.scheduled_for = datetime.now(UTC) + timedelta(days=1)
    request.dedup_key = "isolated-direct-retry"
    first = platform_service.create_notification(db, audience["teacher"], request)
    retry = platform_service.create_notification(db, audience["teacher"], request)
    assert first.id == retry.id
    assert calls == []
    broadcast_request = NotificationBroadcastRequest(
        kind="system",
        title="Scheduled course notice",
        message="Isolated test",
        course_id=audience["course"].id,
        scheduled_for=request.scheduled_for,
        dedup_key="isolated-broadcast-retry",
    )
    first_batch = platform_service.broadcast_notification(
        db, audience["teacher"], broadcast_request
    )
    second_batch = platform_service.broadcast_notification(
        db, audience["teacher"], broadcast_request
    )
    assert {item.recipient_id for item in first_batch} == {
        audience["teacher"].id,
        audience["linked"].id,
    }
    assert [item.id for item in first_batch] == [item.id for item in second_batch]
    assert calls == []


def test_notification_route_denies_teacher_target_outside_scope(db, audience):
    from fastapi.testclient import TestClient

    # Reuse the established HTTP test login helper with a synthetic private password.
    from app.core.security import hash_password
    from app.main import app
    from tests.test_security_and_tenancy import csrf_headers, login

    audience["teacher"].password_hash = hash_password("password-123456")
    audience["teacher"].email = "isolated-teacher@example.com"
    db.commit()
    with TestClient(app) as client:
        login(client, audience["teacher"], audience["institution"].slug)
        response = client.post(
            "/api/v1/notifications",
            headers=csrf_headers(client),
            json=payload(audience["unrelated"]).model_dump(mode="json"),
        )
        assert response.status_code == 404
    assert db.scalar(select(Notification.id)) is None


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://user:synthetic-secret@host/db",
        "postgresql+psycopg2://user:synthetic-secret@host/db",
        "sqlite+aiosqlite:///:memory:",
    ],
)
def test_unsupported_database_driver_fails_without_credentials(url):
    settings = Settings(_env_file=None, database_url=url)
    with pytest.raises(ValueError) as error:
        _ = settings.sqlalchemy_database_url
    assert "synthetic-secret" not in str(error.value)
    assert "host" not in str(error.value)


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_supported_provider_urls_create_sync_engine_without_connecting(scheme):
    settings = Settings(_env_file=None, database_url=f"{scheme}://user:synthetic@invalid.test/db")
    normalized = settings.sqlalchemy_database_url
    assert normalized.startswith("postgresql+psycopg://")
    engine = create_engine(normalized)
    assert engine.dialect.driver == "psycopg"
    engine.dispose()


def test_environment_template_uses_installed_sync_driver():
    repo_root = Path(os.environ["QA_REPO_ROOT"]) if "QA_REPO_ROOT" in os.environ else next(
        (
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / ".env.example").is_file()
        ),
        Path("/repo"),
    )
    template = (repo_root / ".env.example").read_text(encoding="utf-8")
    assert "DATABASE_URL=postgresql+psycopg://" in template
