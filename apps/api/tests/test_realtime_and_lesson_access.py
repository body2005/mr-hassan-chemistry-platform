from __future__ import annotations

import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.events import event_broker
from app.core.security import hash_password
from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Enrollment, EnrollmentStatus, Lesson, LessonKind
from app.models.institution import Institution
from app.models.platform import (
    Assignment,
    AssignmentStatus,
    AssignmentSubmission,
    DeliveryStatus,
    Notification,
    SubmissionStatus,
)
from app.models.payment import EntitlementType, PaymentOrder, PaymentStatus, StudentEntitlement
from app.models.user import User, UserRole
from app.services.payment_service import can_access_lesson_content


def _seed_test_env(db, slug: str = "rt-academy"):
    inst = Institution(name="Realtime Academy", slug=slug)
    db.add(inst)
    db.flush()

    teacher = User(
        institution_id=inst.id,
        username=f"teacher-{uuid.uuid4().hex[:6]}",
        email=f"teacher-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Mr. Hassan",
        password_hash=hash_password("teacher-pass"),
        role=UserRole.TEACHER,
    )
    student = User(
        institution_id=inst.id,
        username=f"student-{uuid.uuid4().hex[:6]}",
        email=f"student-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Ahmed Student",
        password_hash=hash_password("student-pass"),
        role=UserRole.STUDENT,
    )
    db.add_all([teacher, student])
    db.flush()

    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code=f"CHEM-{uuid.uuid4().hex[:5]}",
        title="Organic Chemistry",
        status=CourseStatus.PUBLISHED,
        price_egp=300,
    )
    db.add(course)
    db.flush()

    module = CourseModule(course_id=course.id, title="Unit 1: Hydrocarbons", position=1)
    db.add(module)
    db.flush()

    lesson = Lesson(
        module_id=module.id,
        title="Alkanes and Alkenes",
        kind=LessonKind.VIDEO,
        position=1,
        price_egp=60,
        content="Secret Alkane Formula Content",
        video_asset_key="/api/v1/lessons/alkanes/stream",
    )
    db.add(lesson)
    db.flush()

    assignment = Assignment(
        institution_id=inst.id,
        course_id=course.id,
        creator_id=teacher.id,
        title="Hydrocarbons Problem Set 1",
        prompt="Solve problems 1 through 10",
        status=AssignmentStatus.PUBLISHED,
        max_score=100.0,
    )
    db.add(assignment)
    db.commit()

    return inst, teacher, student, course, lesson, assignment


def _login(client: TestClient, user: User, slug: str, password: str) -> None:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password, "institution_slug": slug},
    )
    assert res.status_code == 200, res.text


def _csrf(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(get_settings().csrf_cookie_name)
    assert token
    return {"X-CSRF-Token": token}


def test_lesson_access_request_and_approval_flow(db) -> None:
    inst, teacher, student, course, lesson, _ = _seed_test_env(db, "access-flow")

    student_client = TestClient(app)
    _login(student_client, student, "access-flow", "student-pass")

    teacher_client = TestClient(app)
    _login(teacher_client, teacher, "access-flow", "teacher-pass")

    # 1. Before access: student cannot access lesson content
    assert not can_access_lesson_content(db, student, lesson.id)

    # 2. Student requests access to the locked lesson
    req_resp = student_client.post(
        f"/api/v1/lessons/{lesson.id}/access-requests",
        json={"student_note": "أريد فتح درس الألكانات للمذاكرة"},
        headers=_csrf(student_client),
    )
    assert req_resp.status_code == 201, req_resp.text
    req_data = req_resp.json()
    assert req_data["status"] == "pending"
    assert req_data["lesson_id"] == str(lesson.id)
    assert req_data["student_name"] == "Ahmed Student"
    request_id = req_data["id"]

    # 3. Verify notification was created for teacher in DB
    teacher_notif = db.scalar(
        select(Notification).where(
            Notification.recipient_id == teacher.id,
            Notification.action_url.contains(request_id),
        )
    )
    assert teacher_notif is not None
    assert "طلب إتاحة درس" in teacher_notif.title

    # 4. Teacher reviews and approves request
    approve_resp = teacher_client.post(
        f"/api/v1/lessons/access-requests/{request_id}/approve",
        json={"note": "تمت الموافقة، بالتوفيق في المذاكرة"},
        headers=_csrf(teacher_client),
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["status"] == "approved"

    # 5. Verify entitlement was created and student now has full access to the lesson
    db.expire_all()
    assert can_access_lesson_content(db, student, lesson.id)

    # 6. Verify student notification was generated
    student_notif = db.scalar(
        select(Notification).where(
            Notification.recipient_id == student.id,
            Notification.title.contains("تمت إتاحة درس"),
        )
    )
    assert student_notif is not None


def test_lesson_access_request_rejection_flow(db) -> None:
    inst, teacher, student, course, lesson, _ = _seed_test_env(db, "reject-flow")

    student_client = TestClient(app)
    _login(student_client, student, "reject-flow", "student-pass")

    teacher_client = TestClient(app)
    _login(teacher_client, teacher, "reject-flow", "teacher-pass")

    # Student requests access
    req_resp = student_client.post(
        f"/api/v1/lessons/{lesson.id}/access-requests",
        json={"student_note": "طلب إتاحة تجريبي"},
        headers=_csrf(student_client),
    )
    assert req_resp.status_code == 201
    request_id = req_resp.json()["id"]

    # Teacher rejects request
    reject_resp = teacher_client.post(
        f"/api/v1/lessons/access-requests/{request_id}/reject",
        json={"note": "يرجى تسليم واجب الدرس السابق أولاً"},
        headers=_csrf(teacher_client),
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    # Still cannot access content
    db.expire_all()
    assert not can_access_lesson_content(db, student, lesson.id)


def test_assignment_submission_and_grading_notifications(db) -> None:
    inst, teacher, student, course, lesson, assignment = _seed_test_env(db, "sub-flow")

    # Enroll student
    db.add(Enrollment(course_id=course.id, student_id=student.id, status=EnrollmentStatus.ACTIVE))
    db.commit()

    student_client = TestClient(app)
    _login(student_client, student, "sub-flow", "student-pass")

    teacher_client = TestClient(app)
    _login(teacher_client, teacher, "sub-flow", "teacher-pass")

    # 1. Student submits homework
    idempotency_key = str(uuid.uuid4())
    sub_resp = student_client.post(
        f"/api/v1/assignments/{assignment.id}/submissions",
        json={
            "answer_text": "Answers to problems 1-10",
            "idempotency_key": idempotency_key,
        },
        headers=_csrf(student_client),
    )
    assert sub_resp.status_code in {200, 201}, sub_resp.text
    sub_id = sub_resp.json()["id"]

    # 2. Verify notification dispatched to teacher
    t_notif = db.scalar(
        select(Notification).where(
            Notification.recipient_id == teacher.id,
            Notification.title.contains("تسليم واجب جديد"),
        )
    )
    assert t_notif is not None

    # 3. Teacher grades submission
    grade_resp = teacher_client.post(
        f"/api/v1/submissions/{sub_id}/grade",
        json={
            "final_score": 95,
            "teacher_feedback": "ممتاز جداً وإجابات دقيقة",
            "approve": True,
        },
        headers=_csrf(teacher_client),
    )
    assert grade_resp.status_code == 200, grade_resp.text
    assert grade_resp.json()["final_score"] == 95

    # 4. Verify notification dispatched to student
    s_notif = db.scalar(
        select(Notification).where(
            Notification.recipient_id == student.id,
            Notification.title.contains("الواجب"),
        )
    )
    assert s_notif is not None
    assert "95" in s_notif.message
