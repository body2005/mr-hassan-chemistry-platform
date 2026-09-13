from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Enrollment, Lesson, LessonKind
from app.models.institution import Institution
from app.models.payment import EntitlementType, PaymentOrder, PaymentStatus, StudentEntitlement
from app.models.user import User, UserRole
from app.services.payment_service import can_access_lesson_content, student_can_use_ai_for_lesson


def _seed_catalog(db, slug: str = "payments"):
    institution = Institution(name="Payment Academy", slug=slug)
    db.add(institution)
    db.flush()
    teacher = User(
        institution_id=institution.id,
        username=f"teacher-{uuid.uuid4().hex[:6]}",
        email=f"teacher-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Teacher",
        password_hash=hash_password("teacher-password"),
        role=UserRole.TEACHER,
    )
    student = User(
        institution_id=institution.id,
        username=f"student-{uuid.uuid4().hex[:6]}",
        email=f"student-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Student",
        password_hash=hash_password("student-password"),
        role=UserRole.STUDENT,
    )
    db.add_all([teacher, student])
    db.flush()
    course = Course(
        institution_id=institution.id,
        teacher_id=teacher.id,
        code=f"PAY-{uuid.uuid4().hex[:5]}",
        title="Paid Chemistry",
        status=CourseStatus.PUBLISHED,
        price_egp=250,
    )
    db.add(course)
    db.flush()
    module = CourseModule(course_id=course.id, title="Module", position=1)
    db.add(module)
    db.flush()
    lesson = Lesson(
        module_id=module.id,
        title="Paid Lesson",
        kind=LessonKind.VIDEO,
        position=1,
        price_egp=50,
        content="Private paid lesson content",
        video_asset_key="/api/v1/lessons/private/video",
    )
    db.add(lesson)
    db.commit()
    return institution, teacher, student, course, lesson


def _login(client: TestClient, user: User, slug: str, password: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password, "institution_slug": slug},
    )
    assert response.status_code == 200, response.text


def test_paid_course_requires_approved_order(db, monkeypatch) -> None:
    _, teacher, student, course, lesson = _seed_catalog(db)
    monkeypatch.setattr(get_settings(), "payment_instapay_account", "teacher@instapay")
    student_client = TestClient(app)
    _login(student_client, student, "payments", "student-password")

    public_course = TestClient(app).get(f"/api/v1/courses/{course.id}")
    assert public_course.status_code == 200
    public_lesson = public_course.json()["modules"][0]["lessons"][0]
    assert public_lesson["content"] is None
    assert public_lesson["video_asset_key"] is None

    assert student_client.post(f"/api/v1/courses/{course.id}/enroll").status_code == 402
    # Verify whole-course checkout is rejected with 422 as per business rules
    course_attempt = student_client.post(
        "/api/v1/payments/orders",
        json={
            "product_type": "course",
            "product_id": str(course.id),
            "payment_method": "instapay",
            "payer_reference": "TX-123",
        },
    )
    assert course_attempt.status_code == 422

    created = student_client.post(
        "/api/v1/payments/orders",
        json={
            "product_type": "lesson",
            "product_id": str(lesson.id),
            "payment_method": "instapay",
            "payer_reference": "TX-123",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["amount_egp"] == 50

    receipt = student_client.post(
        f"/api/v1/payments/orders/{created.json()['id']}/receipt",
        files={"receipt": ("receipt.png", b"small-receipt", "image/png")},
    )
    assert receipt.status_code == 200
    assert receipt.json()["status"] == "under_review"

    teacher_client = TestClient(app)
    _login(teacher_client, teacher, "payments", "teacher-password")
    receipt_view = teacher_client.get(f"/api/v1/payments/orders/{created.json()['id']}/receipt")
    assert receipt_view.status_code == 200
    assert receipt_view.content == b"small-receipt"
    approved = teacher_client.post(
        f"/api/v1/payments/orders/{created.json()['id']}/approve",
        json={"note": "Payment verified"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "paid"

    paid_course = student_client.get(f"/api/v1/courses/{course.id}").json()
    paid_lesson = paid_course["modules"][0]["lessons"][0]
    assert paid_lesson["content"] == "Private paid lesson content"
    assert paid_lesson["video_asset_key"] == "/api/v1/lessons/private/video"
    db.expire_all()
    refreshed_student = db.get(User, student.id)
    assert can_access_lesson_content(db, refreshed_student, lesson.id)
    assert student_can_use_ai_for_lesson(db, refreshed_student, lesson.id)


def test_student_cannot_review_payment_order(db, monkeypatch) -> None:
    _, _, student, course, lesson = _seed_catalog(db, "student-review")
    monkeypatch.setattr(get_settings(), "payment_instapay_account", "teacher@instapay")
    client = TestClient(app)
    _login(client, student, "student-review", "student-password")
    order = client.post(
        "/api/v1/payments/orders",
        json={
            "product_type": "lesson",
            "product_id": str(lesson.id),
            "payment_method": "instapay",
        },
    ).json()
    assert client.get("/api/v1/payments/orders").status_code == 403
    assert client.post(f"/api/v1/payments/orders/{order['id']}/approve", json={}).status_code == 403


def test_ai_subscription_unlocks_ai_but_not_unpurchased_paid_content(db, monkeypatch) -> None:
    _, teacher, student, course, lesson = _seed_catalog(db, "ai-sub")
    course.price_egp = 0
    lesson.price_egp = 0
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()
    monkeypatch.setattr(get_settings(), "payment_instapay_account", "teacher@instapay")
    monkeypatch.setattr(get_settings(), "student_ai_access_mode", "paid_content_or_subscription")
    assert can_access_lesson_content(db, student, lesson.id)
    assert not student_can_use_ai_for_lesson(db, student, lesson.id)

    student_client = TestClient(app)
    _login(student_client, student, "ai-sub", "student-password")
    order = student_client.post(
        "/api/v1/payments/orders",
        json={"product_type": "ai_subscription", "payment_method": "instapay"},
    ).json()
    teacher_client = TestClient(app)
    _login(teacher_client, teacher, "ai-sub", "teacher-password")
    assert teacher_client.post(f"/api/v1/payments/orders/{order['id']}/approve", json={}).status_code == 200

    db.expire_all()
    refreshed_student = db.get(User, student.id)
    assert student_can_use_ai_for_lesson(db, refreshed_student, lesson.id)
    entitlement = db.query(StudentEntitlement).filter(
        StudentEntitlement.student_id == student.id,
        StudentEntitlement.entitlement_type == EntitlementType.AI_GLOBAL,
    ).one()
    assert entitlement.expires_at is not None


def test_teacher_cannot_approve_another_teachers_course_order(db, monkeypatch) -> None:
    institution, _, student, course, lesson = _seed_catalog(db, "teacher-scope")
    other_teacher = User(
        institution_id=institution.id,
        username="other-teacher",
        email="other-teacher@example.com",
        display_name="Other Teacher",
        password_hash=hash_password("other-password"),
        role=UserRole.TEACHER,
    )
    db.add(other_teacher)
    db.commit()
    monkeypatch.setattr(get_settings(), "payment_instapay_account", "teacher@instapay")
    student_client = TestClient(app)
    _login(student_client, student, "teacher-scope", "student-password")
    order_id = student_client.post(
        "/api/v1/payments/orders",
        json={
            "product_type": "lesson",
            "product_id": str(lesson.id),
            "payment_method": "instapay",
        },
    ).json()["id"]

    reviewer_client = TestClient(app)
    _login(reviewer_client, other_teacher, "teacher-scope", "other-password")
    assert reviewer_client.post(f"/api/v1/payments/orders/{order_id}/approve", json={}).status_code == 404
    assert db.get(PaymentOrder, uuid.UUID(order_id)).status == PaymentStatus.PENDING
