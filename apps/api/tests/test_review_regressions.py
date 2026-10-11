"""Regression coverage for the independent 8558cf4 review; real login + CSRF."""
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models.course import Enrollment
from app.models.extended import Grade
from app.models.platform import Quiz, QuizStatus
from app.models.user import UserRole
from test_security_and_tenancy import make_institution, make_user, make_course, login, csrf_headers


def setup_domain(db):
    a, b = make_institution(db, "review-a"), make_institution(db, "review-b")
    owner = make_user(db, b.id, UserRole.TEACHER, "owner")
    foreign = make_user(db, a.id, UserRole.TEACHER, "foreign")
    colleague = make_user(db, b.id, UserRole.TEACHER, "colleague")
    student = make_user(db, b.id, UserRole.STUDENT, "student")
    course = make_course(db, b, owner)
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()
    return a, b, owner, foreign, colleague, student, course


def client(user, slug):
    return login(TestClient(app, raise_server_exceptions=False), user, slug)


def post(c, path, payload):
    return c.post(path, json=payload, headers=csrf_headers(c))


@pytest.mark.parametrize("attacker", ["foreign", "colleague"])
def test_grade_write_requires_student_tenant_and_course_owner(db, attacker):
    a, b, owner, foreign, colleague, student, course = setup_domain(db)
    payload = dict(student_id=str(student.id), course_id=str(course.id),
                   item_type="course", item_id=None, score=90, max_score=100)
    first = post(client(owner, b.slug), "/api/v1/grades", payload)
    assert first.status_code == 201, first.text
    c = client(foreign if attacker == "foreign" else colleague, a.slug if attacker == "foreign" else b.slug)
    response = post(c, "/api/v1/grades", {**payload, "score": 1})
    assert response.status_code in {403, 404}, response.text
    db.expire_all()
    rows = db.query(Grade).filter(Grade.student_id == student.id).all()
    assert len(rows) == 1 and rows[0].is_current and rows[0].score == 90


@pytest.mark.parametrize("viewer", ["student", "colleague"])
def test_versioned_question_answers_are_private(db, viewer):
    a, b, owner, foreign, colleague, student, course = setup_domain(db)
    c = client(owner, b.slug)
    created = post(c, "/api/v1/questions/versioned", dict(course_id=str(course.id),
                   question_type="mcq", prompt="Private question", options=["First", "Second", "Third"],
                   correct_answer="C", explanation="Private answer"))
    assert created.status_code == 201, created.text
    path = f'/api/v1/questions/{created.json()["question_id"]}/versions'
    assert c.get(path).status_code == 200
    other = client(student if viewer == "student" else colleague, b.slug)
    assert other.get(path).status_code in {403, 404}
    assert post(other, path, {"correct_answer": "A"}).status_code in {403, 404}


def test_report_keys_are_scoped_to_requester_and_payload(db):
    a, b, owner, foreign, colleague, student, course = setup_domain(db)
    payload = dict(report_kind="course", params={"course": str(course.id)}, format="xlsx", idempotency_key="review-shared-key")
    c = client(owner, b.slug)
    first = post(c, "/api/v1/reports/jobs", payload)
    assert first.status_code == 202, first.text
    assert post(c, "/api/v1/reports/jobs", payload).json()["id"] == first.json()["id"]
    assert post(c, "/api/v1/reports/jobs", {**payload, "format": "pdf"}).status_code == 409
    for other, slug in [(foreign, a.slug), (colleague, b.slug)]:
        o = client(other, slug)
        independent = post(o, "/api/v1/reports/jobs", payload)
        assert independent.status_code == 202, independent.text
        assert independent.json()["id"] != first.json()["id"]
        assert independent.json()["object_key"] is None
        assert o.get(f'/api/v1/reports/jobs/{first.json()["id"]}').status_code == 404


@pytest.mark.parametrize("item_type", ["course", "quiz"])
def test_grade_revisions_preserve_history_and_one_current_row(db, item_type):
    a, b, owner, foreign, colleague, student, course = setup_domain(db)
    quiz = Quiz(institution_id=b.id, course_id=course.id, creator_id=owner.id, title="Review quiz", status=QuizStatus.PUBLISHED)
    db.add(quiz)
    db.commit()
    payload = dict(student_id=str(student.id), course_id=str(course.id), item_type=item_type,
                   item_id=str(quiz.id) if item_type == "quiz" else None, max_score=100)
    c = client(owner, b.slug)
    for score in (90, 95, 98):
        response = post(c, "/api/v1/grades", {**payload, "score": score})
        assert response.status_code == 201, response.text
    rows = db.query(Grade).filter(Grade.student_id == student.id).all()
    assert sorted(r.score for r in rows) == [90, 95, 98]
    assert [r.score for r in rows if r.is_current] == [98]
