"""Permanent regressions for ECC-03; disposable SQLite and synthetic sessions only."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import create_session_token
from app.main import app
from app.models import Course, Enrollment, Institution, User
from app.models.teacher_tracking import TeacherTrackingColumn
from app.models.user import UserRole


def seed(db):
    institutions = [Institution(name=name, slug=name) for name in ("tracking-a", "tracking-b")]
    db.add_all(institutions)
    db.flush()
    users = []
    for index, role in enumerate(
        (
            UserRole.TEACHER,
            UserRole.TEACHER,
            UserRole.STUDENT,
            UserRole.STUDENT,
            UserRole.TEACHER,
            UserRole.STUDENT,
        )
    ):
        institution = institutions[index >= 4]
        user = User(
            institution_id=institution.id,
            username=f"u{index}",
            email=f"u{index}@example.test",
            display_name=f"User {index}",
            password_hash="unused",
            role=role,
        )
        db.add(user)
        users.append(user)
    db.flush()
    for teacher, student in ((users[0], users[2]), (users[1], users[2]), (users[4], users[5])):
        course = Course(
            institution_id=teacher.institution_id,
            teacher_id=teacher.id,
            code=str(teacher.id),
            title="Tracking course",
        )
        db.add(course)
        db.flush()
        db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()
    return users


def client(user=None, cookie=False):
    instance = TestClient(app)
    if user:
        token = create_session_token(user)
        if cookie:
            instance.cookies.set(get_settings().session_cookie_name, token)
        else:
            instance.headers["Authorization"] = f"Bearer {token}"
    return instance


def column(api, **overrides):
    response = api.post(
        "/api/v1/teacher-tracking/columns",
        json={
            "name": "Parent contacted",
            "data_type": "text",
            "academic_year": "1st_secondary",
            "table_context": "submissions",
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_columns_and_values_survive_new_session_and_are_teacher_tenant_isolated(db):
    teacher, other, student, _, cross_teacher, _ = seed(db)
    api = client(teacher)
    definition = column(api)
    path = f"/api/v1/teacher-tracking/columns/{definition['id']}/students/{student.id}"
    saved = api.put(path, json={"value": "Called guardian"})
    assert saved.status_code == 200, saved.text
    restored = client(teacher).get("/api/v1/teacher-tracking").json()
    assert restored["columns"][0]["name"] == "Parent contacted"
    assert restored["values"][str(student.id)][definition["id"]] == "Called guardian"
    for outsider in (other, cross_teacher):
        isolated = client(outsider)
        assert isolated.get("/api/v1/teacher-tracking").json() == {"columns": [], "values": {}}
        assert isolated.put(path, json={"value": "overwrite"}).status_code == 404
        assert (
            isolated.delete(f"/api/v1/teacher-tracking/columns/{definition['id']}").status_code
            == 404
        )


def test_tracking_denies_unrelated_student_and_withdrawn_enrollment(db):
    teacher, _, student, unrelated, _, cross_student = seed(db)
    api = client(teacher)
    definition = column(api)
    for outsider in (unrelated, cross_student, teacher):
        assert (
            api.put(
                f"/api/v1/teacher-tracking/columns/{definition['id']}/students/{outsider.id}",
                json={"value": "private"},
            ).status_code
            == 404
        )
    enrollment = db.query(Enrollment).filter(Enrollment.student_id == student.id).first()
    enrollment.status = "withdrawn"
    db.commit()
    assert (
        api.put(
            f"/api/v1/teacher-tracking/columns/{definition['id']}/students/{student.id}",
            json={"value": "private"},
        ).status_code
        == 404
    )


def test_tracking_requires_auth_teacher_role_and_cookie_csrf(db):
    teacher, _, student, *_ = seed(db)
    assert client().get("/api/v1/teacher-tracking").status_code == 401
    assert client(student).get("/api/v1/teacher-tracking").status_code == 403
    api = client(teacher, cookie=True)
    payload = {
        "name": "Note",
        "data_type": "text",
        "academic_year": "all",
        "table_context": "students",
    }
    assert api.post("/api/v1/teacher-tracking/columns", json=payload).status_code == 403
    api.cookies.set(get_settings().csrf_cookie_name, "tracking-test-csrf")
    created = api.post(
        "/api/v1/teacher-tracking/columns",
        json=payload,
        headers={"X-CSRF-Token": "tracking-test-csrf"},
    )
    assert created.status_code == 201
    column_id = created.json()["id"]
    cell_path = f"/api/v1/teacher-tracking/columns/{column_id}/students/{student.id}"
    delete_path = f"/api/v1/teacher-tracking/columns/{column_id}"
    assert api.put(cell_path, json={"value": "note"}).status_code == 403
    assert api.delete(delete_path).status_code == 403
    headers = {"X-CSRF-Token": "tracking-test-csrf"}
    assert api.put(cell_path, json={"value": "note"}, headers=headers).status_code == 200
    assert api.delete(delete_path, headers=headers).status_code == 204


def test_tracking_validates_types_limits_and_delete_does_not_delete_student(db):
    teacher, _, student, *_ = seed(db)
    api = client(teacher)
    definition = column(api, data_type="percentage")
    path = f"/api/v1/teacher-tracking/columns/{definition['id']}/students/{student.id}"
    for value in (-1, 101, "not numeric", True):
        assert api.put(path, json={"value": value}).status_code == 422
    assert api.put(path, json={"value": 0}).status_code == 200
    assert (
        api.post(
            "/api/v1/teacher-tracking/columns",
            json={
                "name": "x" * 121,
                "data_type": "text",
                "academic_year": "all",
                "table_context": "students",
            },
        ).status_code
        == 422
    )
    assert api.delete(f"/api/v1/teacher-tracking/columns/{definition['id']}").status_code == 204
    assert client(teacher).get("/api/v1/teacher-tracking").json() == {"columns": [], "values": {}}
    assert db.get(User, student.id) is not None


def test_tracking_column_limit_and_forged_ownership_are_rejected(db):
    teacher, other, *_ = seed(db)
    api = client(teacher)
    payload = {
        "name": "Note",
        "data_type": "text",
        "academic_year": "all",
        "table_context": "students",
    }
    assert (
        api.post(
            "/api/v1/teacher-tracking/columns", json={**payload, "teacher_id": str(other.id)}
        ).status_code
        == 422
    )
    db.add_all(
        [
            TeacherTrackingColumn(
                institution_id=teacher.institution_id, teacher_id=teacher.id, **payload
            )
            for _ in range(50)
        ]
    )
    db.commit()
    assert api.post("/api/v1/teacher-tracking/columns", json=payload).status_code == 409


def test_tracking_cells_preserve_false_zero_and_validate_text_and_numbers(db):
    teacher, _, student, *_ = seed(db)
    api = client(teacher)
    for data_type, valid, invalid in (
        ("checkbox", False, "false"),
        ("number", 0, 1_000_000_001),
        ("text", "", "x" * 2001),
    ):
        definition = column(api, data_type=data_type)
        path = f"/api/v1/teacher-tracking/columns/{definition['id']}/students/{student.id}"
        assert api.put(path, json={"value": invalid}).status_code == 422
        assert api.put(path, json={"value": valid}).json() == {"value": valid}
        assert (
            client(teacher)
            .get("/api/v1/teacher-tracking")
            .json()["values"][str(student.id)][definition["id"]]
            == valid
        )
        assert api.put(path, json={"value": valid}).status_code == 200


def test_tracking_read_hides_cells_when_student_no_longer_in_teacher_scope(db):
    teacher, _, student, *_ = seed(db)
    api = client(teacher)
    definition = column(api)
    assert (
        api.put(
            f"/api/v1/teacher-tracking/columns/{definition['id']}/students/{student.id}",
            json={"value": "private"},
        ).status_code
        == 200
    )
    for enrollment in db.query(Enrollment).filter(Enrollment.student_id == student.id):
        enrollment.status = "withdrawn"
    db.commit()
    snapshot = api.get("/api/v1/teacher-tracking").json()
    assert snapshot["columns"][0]["id"] == definition["id"]
    assert snapshot["values"] == {}
