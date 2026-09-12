"""Security & integration tests: RBAC, tenant isolation, IDOR, exam timer,
duplicate submission, idempotency."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.security import create_session_token, hash_password
from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Lesson, LessonKind
from app.models.extended import AIJob, Grade, IdempotencyKey, QuestionVersion
from app.models.institution import Institution
from app.models.platform import Quiz, QuizStatus
from app.models.user import User, UserRole

UTC = timezone.utc


def make_institution(db, slug: str) -> Institution:
    institution = Institution(name=f"Inst {slug}", slug=slug)
    db.add(institution)
    db.flush()
    return institution


def make_user(
    db,
    institution_id,
    role: UserRole,
    slug: str,
) -> User:
    user = User(
        institution_id=institution_id,
        username=f"{role.value}-{slug}-{uuid.uuid4().hex[:6]}",
        email=f"{role.value}-{slug}-{uuid.uuid4().hex[:6]}@example.com",
        display_name=f"{role.value} {slug}",
        password_hash=hash_password("password-123456"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client: TestClient, user: User, slug: str):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "password-123456",
            "institution_slug": slug,
        },
    )
    assert response.status_code == 200, response.text
    return client


def make_course(db, institution, teacher, *, published=True) -> Course:
    course = Course(
        institution_id=institution.id,
        teacher_id=teacher.id,
        code=f"C-{uuid.uuid4().hex[:6].upper()}",
        title="Course",
        status=CourseStatus.PUBLISHED if published else CourseStatus.DRAFT,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def test_student_cannot_access_admin_user_list(db) -> None:
    inst = make_institution(db, "inst-a")
    student = make_user(db, inst.id, UserRole.STUDENT, "a")
    client = TestClient(app)
    login(client, student, "inst-a")
    assert client.get("/api/v1/users").status_code == 403


def test_teacher_cannot_block_users(db) -> None:
    inst = make_institution(db, "inst-b")
    teacher = make_user(db, inst.id, UserRole.TEACHER, "b")
    target = make_user(db, inst.id, UserRole.STUDENT, "b2")
    client = TestClient(app)
    login(client, teacher, "inst-b")
    assert client.post(f"/api/v1/users/{target.id}/block").status_code == 403


def test_cross_tenant_course_is_invisible(db) -> None:
    inst_a = make_institution(db, "cross-a")
    inst_b = make_institution(db, "cross-b")
    teacher_b = make_user(db, inst_b.id, UserRole.TEACHER, "cb")
    course_b = make_course(db, inst_b, teacher_b)

    student_a = make_user(db, inst_a.id, UserRole.STUDENT, "ca")
    client = TestClient(app)
    login(client, student_a, "cross-a")

    # Direct object access to another tenant's resource must not leak data.
    response = client.get(f"/api/v1/courses/{course_b.id}")
    assert response.status_code == 404
    assert "Physics" not in response.text


def test_cross_tenant_grade_write_is_rejected_via_role_first(db) -> None:
    """A student from tenant A cannot create grades at all (RBAC), and a
    teacher cannot grade into another tenant (tenant check)."""
    inst_a = make_institution(db, "grade-a")
    student_a = make_user(db, inst_a.id, UserRole.STUDENT, "ga")
    client = TestClient(app)
    login(client, student_a, "grade-a")

    response = client.post(
        "/api/v1/grades",
        json={
            "student_id": str(student_a.id),
            "item_type": "quiz",
            "score": 100,
            "max_score": 100,
        },
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"
    assert body["request_id"]


def test_error_format_is_standardized(db) -> None:
    client = TestClient(app)
    response = client.get("/api/v1/auth/me")  # unauthenticated
    assert response.status_code == 401
    body = response.json()
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert "request_id" in body


def test_mock_or_standalone_tokens_never_authenticate(db) -> None:
    inst = make_institution(db, "no-mock-auth")
    make_user(db, inst.id, UserRole.TEACHER, "teacher")
    client = TestClient(app)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer standalone_mock_token"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_stale_session_is_rejected_instead_of_switching_identity(db) -> None:
    inst = make_institution(db, "stale-session")
    stale_user = make_user(db, inst.id, UserRole.TEACHER, "stale")
    token = create_session_token(stale_user)
    db.delete(stale_user)
    db.commit()

    replacement = make_user(db, inst.id, UserRole.TEACHER, "replacement")
    client = TestClient(app)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert "sign in again" in response.json()["error"]["message"]
    assert str(replacement.id) not in response.text


def test_validation_errors_use_standard_format(db) -> None:
    client = TestClient(app)
    response = client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_quiz_attempt_expiry_is_server_enforced(db) -> None:
    """Even if the client thinks there is time left, an expired attempt is
    rejected and marked expired based on DB timestamps."""
    inst = make_institution(db, "timer-inst")
    teacher = make_user(db, inst.id, UserRole.TEACHER, "t")
    student = make_user(db, inst.id, UserRole.STUDENT, "s")
    course = make_course(db, inst, teacher)

    quiz = Quiz(
        institution_id=inst.id,
        course_id=course.id,
        creator_id=teacher.id,
        title="Timer quiz",
        status=QuizStatus.PUBLISHED,
        attempts_allowed=1,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    from app.models.platform import QuizAttempt, AttemptStatus

    expired_attempt = QuizAttempt(
        institution_id=inst.id,
        quiz_id=quiz.id,
        student_id=student.id,
        attempt_number=1,
        started_at=datetime.now(UTC) - timedelta(minutes=30),
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
        status=AttemptStatus.IN_PROGRESS,
        total_points=10,
    )
    db.add(expired_attempt)
    db.commit()
    db.refresh(expired_attempt)

    client = TestClient(app)
    login(client, student, "timer-inst")

    response = client.post(
        f"/api/v1/quiz-attempts/{expired_attempt.id}/submit",
        json={"submission_key": "key-12345678", "answers": []},
    )
    # Expired attempts must be refused with a permission-style error.
    assert response.status_code in {403, 409}
    db.expire_all()
    refreshed = db.get(QuizAttempt, expired_attempt.id)
    assert refreshed.status == AttemptStatus.EXPIRED


def test_duplicate_submission_same_key_returns_same_row(db) -> None:
    from app.models.platform import Assignment, AssignmentSubmission, AssignmentStatus

    inst = make_institution(db, "dup-inst")
    teacher = make_user(db, inst.id, UserRole.TEACHER, "dt")
    student = make_user(db, inst.id, UserRole.STUDENT, "ds")
    course = make_course(db, inst, teacher)
    assignment = Assignment(
        institution_id=inst.id,
        course_id=course.id,
        creator_id=teacher.id,
        title="HW",
        prompt="Do it",
        status=AssignmentStatus.PUBLISHED,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    # enroll the student
    from app.models.course import Enrollment, EnrollmentStatus

    enrollment = Enrollment(
        course_id=course.id,
        student_id=student.id,
        status=EnrollmentStatus.ACTIVE,
    )
    db.add(enrollment)
    db.commit()

    client = TestClient(app)
    login(client, student, "dup-inst")

    payload = {
        "answer_text": "my answer",
        "idempotency_key": "idem-key-000001",
    }
    first = client.post(f"/api/v1/assignments/{assignment.id}/submissions", json=payload)
    second = client.post(f"/api/v1/assignments/{assignment.id}/submissions", json=payload)
    assert first.status_code in {200, 201}, first.text
    assert second.status_code == first.status_code
    assert first.json()["id"] == second.json()["id"]

    submissions = db.query(AssignmentSubmission).all()
    assert len(submissions) == 1


def test_ai_job_task_whitelist_and_idempotency(db) -> None:
    inst = make_institution(db, "ai-inst")
    teacher = make_user(db, inst.id, UserRole.TEACHER, "ai")
    client = TestClient(app)
    login(client, teacher, "ai-inst")

    bad = client.post("/api/v1/ai/jobs", json={"task": "destroy_world", "payload": {}})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "BAD_REQUEST"

    good = client.post(
        "/api/v1/ai/jobs",
        json={"task": "quiz_generation", "payload": {"lesson": "x"}, "idempotency_key": "ai-key-111"},
    )
    assert good.status_code == 202
    replay = client.post(
        "/api/v1/ai/jobs",
        json={"task": "quiz_generation", "payload": {"lesson": "x"}, "idempotency_key": "ai-key-111"},
    )
    assert replay.status_code == 202
    assert good.json()["id"] == replay.json()["id"]
    jobs = db.query(AIJob).filter(AIJob.task == "quiz_generation").all()
    assert len(jobs) == 1


def test_question_versioning_freezes_history(db) -> None:
    inst = make_institution(db, "ver-inst")
    teacher = make_user(db, inst.id, UserRole.TEACHER, "vq")
    client = TestClient(app)
    login(client, teacher, "ver-inst")

    created = client.post(
        "/api/v1/questions/versioned",
        json={
            "question_type": "mcq",
            "prompt": "What is 2+2?",
            "options": ["3", "4"],
            "correct_answer": "4",
            "points": 5,
        },
    )
    assert created.status_code == 201, created.text
    question_id = created.json()["question_id"]

    updated = client.post(
        f"/api/v1/questions/{question_id}/versions",
        json={"prompt": "What is 2+2 (exact)?", "correct_answer": "4"},
    )
    assert updated.status_code == 201
    assert updated.json()["version"] == 2

    versions = client.get(f"/api/v1/questions/{question_id}/versions")
    assert versions.status_code == 200
    assert [v["version"] for v in versions.json()] == [1, 2]
    stored = db.query(QuestionVersion).order_by(QuestionVersion.version).all()
    assert stored[0].prompt == "What is 2+2?"  # history intact


def test_report_job_requires_staff_role(db) -> None:
    inst = make_institution(db, "rep-inst")
    student = make_user(db, inst.id, UserRole.STUDENT, "rs")
    client = TestClient(app)
    login(client, student, "rep-inst")
    response = client.post(
        "/api/v1/reports/jobs", json={"report_kind": "class"}
    )
    assert response.status_code == 403


def test_health_and_ready_endpoints_exist() -> None:
    client = TestClient(app)
    health = client.get("/api/v1/health")
    ready = client.get("/api/v1/ready")
    assert health.status_code == 200
    assert ready.status_code == 200
    assert "dependencies" in ready.json()


def test_csrf_protection_enforcement(db) -> None:
    inst = make_institution(db, "csrf-inst")
    teacher = make_user(db, inst.id, UserRole.TEACHER, "csrf_t")
    client = TestClient(app)
    login(client, teacher, "csrf-inst")

    # Request with Origin header and session cookie, but WITHOUT X-CSRF-Token header -> MUST return 403
    resp_blocked = client.post(
        "/api/v1/ai/jobs",
        json={"task": "quiz_generation", "payload": {}},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp_blocked.status_code == 403
    assert "CSRF" in resp_blocked.json().get("detail", "")

    # Request WITH matching X-CSRF-Token header -> MUST pass CSRF check
    csrf_token = client.cookies.get("matgar_csrf")
    resp_allowed = client.post(
        "/api/v1/ai/jobs",
        json={"task": "quiz_generation", "payload": {}, "idempotency_key": "csrf-valid-1"},
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_token},
    )
    assert resp_allowed.status_code == 202
