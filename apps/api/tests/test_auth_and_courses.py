from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Enrollment, Lesson, LessonKind
from app.models.institution import Institution
from app.models.platform import AIInvocation, AssignmentSubmission, QuizAttempt
from app.models.progress import LessonProgress, VideoEvent
from app.models.user import User, UserRole


def register(client: TestClient, email: str, institution_slug: str = "demo"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Student One",
            "email": email,
            "password": "a-strong-password",
            "institution_slug": institution_slug,
        },
    )


def seed_teacher_and_course(db, institution_slug: str = "academy-a") -> tuple[User, Course]:
    institution = Institution(name="Academy A", slug=institution_slug)
    db.add(institution)
    db.flush()
    teacher = User(
        institution_id=institution.id,
        username=f"teacher-{uuid.uuid4().hex[:8]}",
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Teacher One",
        password_hash=hash_password("teacher-password"),
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.flush()
    course = Course(
        institution_id=institution.id,
        teacher_id=teacher.id,
        code="PHY-101",
        title="Physics Foundations",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.commit()
    db.refresh(teacher)
    db.refresh(course)
    return teacher, course


def test_register_login_me_and_logout() -> None:
    client = TestClient(app)

    response = register(client, "student@example.com")
    assert response.status_code == 201
    assert "matgar_session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "password" not in response.json()["user"]

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "student@example.com"

    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_password_is_hashed_and_duplicate_registration_is_rejected(db) -> None:
    client = TestClient(app)
    assert register(client, "student@example.com").status_code == 201
    assert register(client, "student@example.com").status_code == 409

    user = db.query(User).filter(User.email == "student@example.com").one()
    assert user.password_hash != "a-strong-password"
    assert user.password_hash.startswith("$argon2")


def test_teacher_can_create_and_publish_course_but_student_cannot() -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        teacher, _ = seed_teacher_and_course(db)

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": teacher.email,
            "password": "teacher-password",
            "institution_slug": "academy-a",
        },
    )
    assert login.status_code == 200
    created = client.post(
        "/api/v1/courses",
        json={"code": "PHY-102", "title": "Motion"},
    )
    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    course_id = created.json()["id"]
    assert client.post(f"/api/v1/courses/{course_id}/publish").status_code == 200

    register_response = register(client, "student2@example.com", "academy-a")
    assert register_response.status_code == 201
    assert client.post("/api/v1/courses", json={"code": "NO", "title": "Denied"}).status_code == 403
    courses = client.get("/api/v1/courses").json()
    assert courses["pagination"]["total"] == 2
    enrollment = client.post(f"/api/v1/courses/{course_id}/enroll")
    assert enrollment.status_code == 200
    second_enrollment = client.post(f"/api/v1/courses/{course_id}/enroll")
    assert second_enrollment.json()["id"] == enrollment.json()["id"]


def test_course_isolation_between_institutions(db) -> None:
    _, course = seed_teacher_and_course(db, "academy-a")
    client_a = TestClient(app)
    client_b = TestClient(app)
    assert register(client_a, "a@example.com", "academy-a").status_code == 201
    assert register(client_b, "b@example.com", "academy-b").status_code == 201

    assert client_a.get(f"/api/v1/courses/{course.id}").status_code == 200
    assert client_b.get(f"/api/v1/courses/{course.id}").status_code == 404


def test_video_telemetry_is_batched_deduplicated_and_enrollment_scoped(db) -> None:
    _, course = seed_teacher_and_course(db, "academy-video")
    module = CourseModule(course_id=course.id, title="Module 1", position=1)
    db.add(module)
    db.flush()
    lesson = Lesson(
        module_id=module.id,
        title="Lesson 1",
        kind=LessonKind.VIDEO,
        position=1,
        video_duration_seconds=100,
    )
    db.add(lesson)
    db.commit()

    client = TestClient(app)
    assert register(client, "video-student@example.com", "academy-video").status_code == 201
    student = db.query(User).filter(User.email == "video-student@example.com").one()
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()

    event = {
        "client_event_id": "event-video-001",
        "lesson_id": str(lesson.id),
        "event_type": "play",
        "position_seconds": 25,
        "watched_delta_seconds": 10,
        "duration_seconds": 100,
    }
    first = client.post("/api/v1/telemetry/video-events", json={"events": [event]})
    assert first.status_code == 202
    assert first.json() == {"accepted": 1, "duplicates": 0}

    second = client.post("/api/v1/telemetry/video-events", json={"events": [event]})
    assert second.status_code == 202
    assert second.json() == {"accepted": 0, "duplicates": 1}
    assert db.query(VideoEvent).count() == 1
    progress = db.query(LessonProgress).one()
    assert progress.watched_duration_seconds == 10
    assert progress.completion_percent == 25


def test_quiz_is_server_timed_and_submission_is_idempotent(db) -> None:
    teacher, course = seed_teacher_and_course(db, "academy-quiz")
    teacher_client = TestClient(app)
    assert (
        teacher_client.post(
            "/api/v1/auth/login",
            json={
                "email": teacher.email,
                "password": "teacher-password",
                "institution_slug": "academy-quiz",
            },
        ).status_code
        == 200
    )
    question = teacher_client.post(
        "/api/v1/questions",
        json={
            "course_id": str(course.id),
            "question_type": "multiple_choice",
            "prompt": "2 + 2?",
            "options": ["3", "4"],
            "correct_answer": "4",
            "points": 5,
        },
    )
    assert question.status_code == 201
    quiz = teacher_client.post(
        "/api/v1/quizzes",
        json={
            "course_id": str(course.id),
            "title": "Foundations Check",
            "duration_seconds": 120,
            "question_ids": [question.json()["id"]],
        },
    )
    assert quiz.status_code == 201
    assert teacher_client.post(f"/api/v1/quizzes/{quiz.json()['id']}/publish").status_code == 200

    student_client = TestClient(app)
    assert register(student_client, "quiz-student@example.com", "academy-quiz").status_code == 201
    student = db.query(User).filter(User.email == "quiz-student@example.com").one()
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()
    attempt = student_client.post(f"/api/v1/quizzes/{quiz.json()['id']}/attempts")
    assert attempt.status_code == 200
    submission = student_client.post(
        f"/api/v1/quiz-attempts/{attempt.json()['id']}/submit",
        json={
            "submission_key": "quiz-submit-001",
            "answers": [{"question_id": question.json()["id"], "answer": "4"}],
        },
    )
    assert submission.status_code == 200
    assert submission.json()["score"] == 5
    duplicate = student_client.post(
        f"/api/v1/quiz-attempts/{attempt.json()['id']}/submit",
        json={"submission_key": "quiz-submit-001", "answers": []},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == attempt.json()["id"]
    assert db.query(QuizAttempt).count() == 1


def test_assignment_versions_are_preserved_and_grading_is_server_side(db) -> None:
    teacher, course = seed_teacher_and_course(db, "academy-assignment")
    teacher_client = TestClient(app)
    teacher_client.post(
        "/api/v1/auth/login",
        json={
            "email": teacher.email,
            "password": "teacher-password",
            "institution_slug": "academy-assignment",
        },
    )
    assignment = teacher_client.post(
        "/api/v1/assignments",
        json={"course_id": str(course.id), "title": "Essay", "prompt": "Explain gravity"},
    )
    assert assignment.status_code == 201
    assert (
        teacher_client.post(f"/api/v1/assignments/{assignment.json()['id']}/publish").status_code
        == 200
    )
    student_client = TestClient(app)
    register(student_client, "assignment-student@example.com", "academy-assignment")
    student = db.query(User).filter(User.email == "assignment-student@example.com").one()
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()
    first = student_client.post(
        f"/api/v1/assignments/{assignment.json()['id']}/submissions",
        json={"answer_text": "first", "idempotency_key": "assignment-submit-01"},
    )
    second = student_client.post(
        f"/api/v1/assignments/{assignment.json()['id']}/submissions",
        json={"answer_text": "first", "idempotency_key": "assignment-submit-01"},
    )
    third = student_client.post(
        f"/api/v1/assignments/{assignment.json()['id']}/submissions",
        json={"answer_text": "revised", "idempotency_key": "assignment-submit-02"},
    )
    assert first.status_code == second.status_code == third.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert third.json()["version"] == 2
    graded = teacher_client.post(
        f"/api/v1/submissions/{first.json()['id']}/grade",
        json={"final_score": 80, "teacher_feedback": "Good", "approve": True},
    )
    assert graded.status_code == 200
    assert graded.json()["status"] == "approved"
    assert db.query(AssignmentSubmission).count() == 2


def test_ai_provider_failure_is_recorded_and_never_silently_falls_back(db) -> None:
    client = TestClient(app)
    assert register(client, "ai-student@example.com", "academy-ai").status_code == 201
    response = client.post(
        "/api/v1/ai/invocations",
        json={
            "task": "tutor",
            "prompt": "Return a JSON answer",
            "provider": "not-configured",
            "prompt_version": "v1",
        },
    )
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "unsupported_provider"
    invocation = db.query(AIInvocation).one()
    assert invocation.status == "failed"
    assert invocation.output_json is None
