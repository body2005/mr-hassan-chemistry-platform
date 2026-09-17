from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.user import Gender, Religion, User


def payload(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "display_name": "طالب تجريبي كامل",
        "email": "student.registration@example.com",
        "password": "a-strong-password",
        "institution_slug": "registration-test",
        "grade_level": "SECONDARY_3",
        "student_phone": "٠١٠ ١٢٣٤-٥٦٧٨",
        "guardian_phone": "011-1234-5678",
        "national_id": "30301010101010",
        "governorate": "CAIRO",
        "school_name": "  مدرسة تجريبية 2 الثانوية  ",
        "gender": "FEMALE",
        "religion": "CHRISTIAN",
    }
    data.update(changes)
    return data


def test_registration_persists_all_student_fields_and_me_returns_private_data(db) -> None:
    client = TestClient(app)
    response = client.post("/api/v1/auth/register", json=payload())
    assert response.status_code == 201, response.text
    body = response.json()["user"]
    assert body["grade_level"] == "SECONDARY_3"
    assert body["governorate"] == "CAIRO"
    assert body["school_name"] == "مدرسة تجريبية 2 الثانوية"
    assert body["national_id"] == "30301010101010"
    assert body["religion"] == "CHRISTIAN"

    stored = db.query(User).filter(User.email == "student.registration@example.com").one()
    assert stored.grade_level == "SECONDARY_3"
    assert stored.student_phone == "01012345678"
    assert stored.guardian_phone == "01112345678"
    assert stored.national_id == "30301010101010"
    assert stored.governorate == "CAIRO"
    assert stored.school_name == "مدرسة تجريبية 2 الثانوية"
    assert stored.gender == Gender.FEMALE
    assert stored.religion == Religion.CHRISTIAN

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["national_id"] == "30301010101010"


def test_registration_rejects_unknown_and_invalid_sensitive_values() -> None:
    client = TestClient(app)
    assert client.post("/api/v1/auth/register", json=payload(governorate="MOON")).status_code == 422
    assert client.post("/api/v1/auth/register", json=payload(email="gender@example.com", gender="UNKNOWN")).status_code == 422
    assert client.post("/api/v1/auth/register", json=payload(email="religion@example.com", religion="UNKNOWN")).status_code == 422
    assert client.post("/api/v1/auth/register", json=payload(email="id@example.com", national_id="1234")).status_code == 422
    assert client.post("/api/v1/auth/register", json=payload(email="extra@example.com", ignored_by_server="no")).status_code == 422


def test_duplicate_national_id_is_conflict_only_inside_same_institution() -> None:
    client = TestClient(app)
    assert client.post("/api/v1/auth/register", json=payload()).status_code == 201
    duplicate = client.post("/api/v1/auth/register", json=payload(email="duplicate@example.com"))
    assert duplicate.status_code == 409
    assert "uq_" not in duplicate.text

    other_institution = client.post(
        "/api/v1/auth/register",
        json=payload(email="other@example.com", institution_slug="another-registration-test"),
    )
    assert other_institution.status_code == 201
