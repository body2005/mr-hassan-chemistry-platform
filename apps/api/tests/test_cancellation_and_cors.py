import os
import shutil
import uuid
import pytest
from unittest.mock import patch
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import app
from app.core.errors import OperationCancelledError
from app.models.course import Course, CourseStatus
from app.models.institution import Institution
from app.models.knowledge_center import KnowledgeSource, SourceRole, SourceStatus
from app.models.user import User, UserRole
from app.services.knowledge_center_service import (
    clear_source_tracking,
    is_source_cancelled,
    is_source_deleting,
    mark_parser_active,
    mark_parser_inactive,
    process_knowledge_source,
    register_cancellation,
    register_deleting,
)


@pytest.fixture
def auth_teacher_client(db):
    inst = Institution(name="???? ???????? ??????", slug="chem-inst-cancellation")
    db.add(inst)
    db.commit()

    teacher = User(
        institution_id=inst.id,
        username="chem_prof_cancel",
        email="prof_cancel@chem.edu",
        password_hash="argon2id=19=65536,t=3,p=4",
        display_name="?. ??? ????",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.commit()

    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="CHEM-CANCEL",
        title="Chemistry Lab Safety",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.commit()
    db.refresh(inst)
    db.refresh(teacher)
    db.refresh(course)

    client = TestClient(app, raise_server_exceptions=False)
    from app.api.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: teacher

    yield {"client": client, "course": course, "teacher": teacher, "inst": inst}

    app.dependency_overrides.clear()


def test_stop_indexing_endpoint_success_and_idempotency(auth_teacher_client, db):
    """Verifies stopping an ongoing indexing source is prompt, idempotent, and updates status."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    teacher = auth_teacher_client["teacher"]

    source_id = uuid.uuid4()
    source = KnowledgeSource(
        id=source_id,
        institution_id=course.institution_id,
        course_id=course.id,
        teacher_id=teacher.id,
        filename="lecture_chemistry.pdf",
        file_format="pdf",
        storage_path="storage/dummy_test.pdf",
        checksum="dummy_checksum_123",
        size_bytes=1024,
        source_role=SourceRole.KNOWLEDGE,
        status=SourceStatus.PROCESSING,
        progress_percent=45,
    )
    db.add(source)
    db.commit()

    origin = "https://mr-hassan-chemistry.vercel.app"

    # 1. Stop indexing request
    res = client.post(
        f"/api/v1/knowledge-center/sources/{source_id}/stop-indexing",
        headers={"Origin": origin},
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["status"] == "ok"
    assert is_source_cancelled(source_id) is True

    # Check CORS header is present
    assert res.headers.get("access-control-allow-origin") == origin

    # Check DB status
    db.expire_all()
    refreshed = db.get(KnowledgeSource, source_id)
    assert refreshed.status == SourceStatus.STOPPED

    # 2. Idempotent repeat request
    res2 = client.post(
        f"/api/v1/knowledge-center/sources/{source_id}/stop-indexing",
        headers={"Origin": origin},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "ok"


def test_delete_source_endpoint_processing_and_idempotency(auth_teacher_client, db, tmp_path):
    """Verifies deleting a processing source cooperatively terminates parser and deletes DB record idempotently."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    teacher = auth_teacher_client["teacher"]

    dummy_file = tmp_path / "test_cancel_doc.pdf"
    dummy_file.write_bytes(b"%PDF-1.4 dummy content")

    source_id = uuid.uuid4()
    source = KnowledgeSource(
        id=source_id,
        institution_id=course.institution_id,
        course_id=course.id,
        teacher_id=teacher.id,
        filename="lecture_chemistry_del.pdf",
        file_format="pdf",
        storage_path=str(dummy_file),
        checksum="dummy_checksum_del",
        size_bytes=1024,
        source_role=SourceRole.KNOWLEDGE,
        status=SourceStatus.PROCESSING,
        progress_percent=50,
    )
    db.add(source)
    db.commit()

    origin = "https://mr-hassan-chemistry.vercel.app"

    # 1. Delete source while PROCESSING
    res = client.delete(
        f"/api/v1/knowledge-center/sources/{source_id}",
        headers={"Origin": origin},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.headers.get("access-control-allow-origin") == origin

    # Source should be deleted from DB
    db.expire_all()
    deleted = db.get(KnowledgeSource, source_id)
    assert deleted is None

    # 2. Repeated delete call on already-deleted source must be idempotent (200 OK)
    res2 = client.delete(
        f"/api/v1/knowledge-center/sources/{source_id}",
        headers={"Origin": origin},
    )
    assert res2.status_code == 200
    assert res2.json()["success"] is True
    assert res2.json().get("status") == "already_deleted"


def test_delete_source_signals_deleting_flag_during_active_parser(auth_teacher_client, db, tmp_path):
    """Verifies register_deleting is set when deleting an actively indexing source."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    teacher = auth_teacher_client["teacher"]

    dummy_file = tmp_path / "active_parser_doc.pdf"
    dummy_file.write_bytes(b"%PDF-1.4 dummy content")

    source_id = uuid.uuid4()
    source = KnowledgeSource(
        id=source_id,
        institution_id=course.institution_id,
        course_id=course.id,
        teacher_id=teacher.id,
        filename="active_parser_doc.pdf",
        file_format="pdf",
        storage_path=str(dummy_file),
        checksum="active_checksum",
        size_bytes=2048,
        source_role=SourceRole.KNOWLEDGE,
        status=SourceStatus.PROCESSING,
        progress_percent=30,
    )
    db.add(source)
    db.commit()

    mark_parser_active(source_id)
    try:
        # Delete while parser marked active
        res = client.delete(
            f"/api/v1/knowledge-center/sources/{source_id}",
            headers={"Origin": "https://mr-hassan-chemistry.vercel.app"},
        )
        assert res.status_code == 200
        assert res.json()["success"] is True
    finally:
        mark_parser_inactive(source_id)
        clear_source_tracking(source_id)


def test_cors_headers_on_exception_and_error_responses(auth_teacher_client):
    """Ensures 404, 422, and unhandled 500 exceptions all return CORS headers."""
    client = auth_teacher_client["client"]
    origin = "https://mr-hassan-chemistry.vercel.app"

    # 404 Not Found error
    res_404 = client.get("/api/v1/knowledge-center/sources/non-existent-uuid-12345", headers={"Origin": origin})
    assert res_404.headers.get("access-control-allow-origin") == origin

    # OPTIONS preflight request
    res_options = client.options(
        "/api/v1/knowledge-center/sources/11111111-1111-1111-1111-111111111111/stop-indexing",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-csrf-token",
        },
    )
    assert res_options.status_code == 200
    assert res_options.headers.get("access-control-allow-origin") == origin
    assert "POST" in res_options.headers.get("access-control-allow-methods", "")
    allowed_headers = res_options.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers
    assert "x-csrf-token" in allowed_headers
    assert allowed_headers != "*"


def test_unhandled_500_exception_returns_json_with_cors(auth_teacher_client, db):
    """Verifies that an unhandled 500 exception returns structured JSON error and CORS headers."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    teacher = auth_teacher_client["teacher"]
    origin = "https://mr-hassan-chemistry.vercel.app"

    source_id = uuid.uuid4()
    source = KnowledgeSource(
        id=source_id,
        institution_id=course.institution_id,
        course_id=course.id,
        teacher_id=teacher.id,
        filename="lecture_crash_test.pdf",
        file_format="pdf",
        storage_path="storage/dummy_crash.pdf",
        checksum="dummy_checksum_crash",
        size_bytes=1024,
        source_role=SourceRole.KNOWLEDGE,
        status=SourceStatus.INDEXED,
        progress_percent=100,
    )
    db.add(source)
    db.commit()

    # Mock an internal error in delete_knowledge_source to simulate 500
    with patch("app.api.routes.knowledge_center.delete_knowledge_source", side_effect=RuntimeError("Database lock crash simulation")):
        res = client.delete(
            f"/api/v1/knowledge-center/sources/{source_id}",
            headers={"Origin": origin},
        )
        assert res.status_code == 500
        assert res.headers.get("access-control-allow-origin") == origin
        body = res.json()
        assert "error" in body
        assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"


def test_process_knowledge_source_respects_cancellation(auth_teacher_client, db, tmp_path):
    """Verifies process_knowledge_source halts immediately when cancelled and updates status."""
    course = auth_teacher_client["course"]
    teacher = auth_teacher_client["teacher"]

    dummy_file = tmp_path / "test_cancel_loop.txt"
    dummy_file.write_text("??? ?? ??????? ????????", encoding="utf-8")

    source_id = uuid.uuid4()
    source = KnowledgeSource(
        id=source_id,
        institution_id=course.institution_id,
        course_id=course.id,
        teacher_id=teacher.id,
        filename="test_cancel_loop.txt",
        file_format="txt",
        storage_path=str(dummy_file),
        checksum="checksum_cancel_loop",
        size_bytes=100,
        source_role=SourceRole.KNOWLEDGE,
        status=SourceStatus.QUEUED,
        progress_percent=0,
    )
    db.add(source)
    db.commit()

    # Register cancellation before processing
    register_cancellation(source_id)

    with pytest.raises(OperationCancelledError):
        process_knowledge_source(db, source_id)

    db.expire_all()
    refreshed = db.get(KnowledgeSource, source_id)
    assert refreshed.status == SourceStatus.STOPPED
    clear_source_tracking(source_id)
