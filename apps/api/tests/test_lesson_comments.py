"""Discussion follows the SAME lesson entitlement/ownership policy as media."""
from datetime import datetime, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models.course import CourseModule, Enrollment, EnrollmentStatus, Lesson, LessonKind
from app.models.payment import EntitlementType, StudentEntitlement
from app.models.platform import LessonComment
from app.models.user import UserRole
from tests.test_security_and_tenancy import (
    csrf_headers, login, make_course, make_institution, make_user,
)


def discussion(db):
    inst = make_institution(db, "discussion")
    owner = make_user(db, inst.id, UserRole.TEACHER, "owner")
    course = make_course(db, inst, owner)
    module = CourseModule(course_id=course.id, title="Unit", position=1)
    db.add(module)
    db.flush()
    lesson = Lesson(module_id=module.id, title="Paid discussion", kind=LessonKind.VIDEO,
                    position=1, price_egp=25)
    db.add(lesson)
    db.flush()
    comment = LessonComment(institution_id=inst.id, lesson_id=lesson.id,
                            student_id=owner.id, body="Private lesson discussion")
    db.add(comment)
    db.commit()
    return inst, owner, course, lesson, comment


@pytest.mark.parametrize("role", ["student", "unenrolled", "teacher", "other_tenant", "other_platform_admin"])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_discussion_cannot_bypass_lesson_access(db, role, method):
    inst, _, course, lesson, _ = discussion(db)
    foreign = role in {"other_tenant", "other_platform_admin"}
    other = make_institution(db, "other-discussion") if foreign else inst
    reader_role = (UserRole.PLATFORM_ADMIN if role == "other_platform_admin" else
                   UserRole.TEACHER if role == "teacher" else UserRole.STUDENT)
    reader = make_user(db, other.id, reader_role, role)
    if role == "student":
        db.add(Enrollment(course_id=course.id, student_id=reader.id, status=EnrollmentStatus.ACTIVE))
        db.commit()
    with TestClient(app) as client:
        login(client, reader, other.slug)
        path = f"/api/v1/lessons/{lesson.id}/comments"
        response = (client.get(path) if method == "GET" else
                    client.post(path, json={"body": "Unauthorized write"}, headers=csrf_headers(client)))
        assert response.status_code == (404 if foreign else 403), response.text
        assert "Private lesson discussion" not in response.text
    assert db.scalar(select(func.count(LessonComment.id))) == 1


@pytest.mark.parametrize("payload", [
    {"body": 123}, {"body": ["text"]}, {"body": "Valid", "parent_id": "not-a-uuid"},
    {"body": "Valid", "parent_id": str(uuid.UUID(int=1))},
    {"body": "   "}, {"body": "x" * 2001}, {"body": None}, {"body": "Valid", "parent_id": 123},
])
def test_malformed_discussion_payload_is_422_not_500(db, payload):
    inst, owner, _, lesson, _ = discussion(db)
    with TestClient(app, raise_server_exceptions=False) as client:
        login(client, owner, inst.slug)
        response = client.post(f"/api/v1/lessons/{lesson.id}/comments", json=payload,
                               headers=csrf_headers(client))
        assert response.status_code == 422, response.text
    assert db.scalar(select(func.count(LessonComment.id))) == 1


def test_reply_to_reply_is_rejected_instead_of_becoming_invisible(db):
    inst, owner, _, lesson, comment = discussion(db)
    reply = LessonComment(institution_id=inst.id, lesson_id=lesson.id, student_id=owner.id,
                          parent_id=comment.id, body="Visible reply")
    db.add(reply)
    db.commit()
    with TestClient(app) as client:
        login(client, owner, inst.slug)
        response = client.post(f"/api/v1/lessons/{lesson.id}/comments",
                               json={"body": "Invisible grandchild", "parent_id": str(reply.id)},
                               headers=csrf_headers(client))
        assert response.status_code == 422, response.text
    assert db.scalar(select(func.count(LessonComment.id))) == 2


@pytest.mark.parametrize("role", ["owner", "paid_student"])
def test_authorized_discussion_persists_real_ids_and_replies(db, role):
    inst, owner, course, lesson, _ = discussion(db)
    writer = owner
    if role == "paid_student":
        writer = make_user(db, inst.id, UserRole.STUDENT, role)
        db.add(Enrollment(course_id=course.id, student_id=writer.id, status=EnrollmentStatus.ACTIVE))
        db.add(StudentEntitlement(institution_id=inst.id, student_id=writer.id,
                                 entitlement_type=EntitlementType.LESSON, resource_id=lesson.id,
                                 starts_at=datetime.now(timezone.utc)))
        db.commit()
    with TestClient(app) as client:
        login(client, writer, inst.slug)
        path = f"/api/v1/lessons/{lesson.id}/comments"
        comment = client.post(path, json={"body": "Real comment"}, headers=csrf_headers(client))
        assert comment.status_code == 201, comment.text
        parent = comment.json()
        uuid.UUID(parent["id"])
        reply = client.post(path, json={"body": "Real reply", "parent_id": parent["id"]},
                            headers=csrf_headers(client))
        assert reply.status_code == 201, reply.text
        tree = client.get(path)
        assert tree.status_code == 200
        saved = next(item for item in tree.json()["comments"] if item["id"] == parent["id"])
        assert saved["body"] == "Real comment"
        assert saved["replies"][0]["id"] == reply.json()["id"]
        assert saved["replies"][0]["body"] == "Real reply"
