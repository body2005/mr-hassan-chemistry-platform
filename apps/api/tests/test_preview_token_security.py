import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_preview_token, create_session_token
from app.main import app
from app.models.course import Course
from app.models.institution import Institution
from app.models.knowledge_center import KnowledgeSource, SourceRole, SourceStatus
from app.models.user import User, UserRole


@pytest.fixture
def setup_preview_test_env():
    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.slug == "test-preview-inst").first()
        if not inst:
            inst = Institution(name="Preview Test Inst", slug="test-preview-inst")
            db.add(inst)
            db.commit()
            db.refresh(inst)

        teacher = db.query(User).filter(User.email == "teacher_preview@test.com").first()
        if not teacher:
            teacher = User(
                institution_id=inst.id,
                email="teacher_preview@test.com",
                username="teacher_preview",
                password_hash="fakehash",
                display_name="Teacher Preview",
                role=UserRole.TEACHER,
            )
            db.add(teacher)
            db.commit()
            db.refresh(teacher)

        course = db.query(Course).filter(Course.code == "PREV101").first()
        if not course:
            course = Course(
                institution_id=inst.id,
                teacher_id=teacher.id,
                title="Preview Course",
                code="PREV101",
            )
            db.add(course)
            db.commit()
            db.refresh(course)

        source1 = db.query(KnowledgeSource).filter(KnowledgeSource.filename == "doc1.pdf").first()
        if not source1:
            source1 = KnowledgeSource(
                institution_id=inst.id,
                course_id=course.id,
                teacher_id=teacher.id,
                filename="doc1.pdf",
                file_format="pdf",
                storage_path="storage/test_doc1.pdf",
                size_bytes=100,
                checksum="abc",
                source_role=SourceRole.KNOWLEDGE,
                status=SourceStatus.INDEXED,
            )
            db.add(source1)
            db.commit()
            db.refresh(source1)

        source2 = db.query(KnowledgeSource).filter(KnowledgeSource.filename == "doc2.pdf").first()
        if not source2:
            source2 = KnowledgeSource(
                institution_id=inst.id,
                course_id=course.id,
                teacher_id=teacher.id,
                filename="doc2.pdf",
                file_format="pdf",
                storage_path="storage/test_doc2.pdf",
                size_bytes=100,
                checksum="def",
                source_role=SourceRole.KNOWLEDGE,
                status=SourceStatus.INDEXED,
            )
            db.add(source2)
            db.commit()
            db.refresh(source2)

        yield {
            "institution": inst,
            "teacher": teacher,
            "course": course,
            "source1": source1,
            "source2": source2,
        }


def test_preview_token_cannot_access_general_endpoints(setup_preview_test_env):
    data = setup_preview_test_env
    teacher = data["teacher"]
    source1 = data["source1"]
    source2 = data["source2"]

    # Generate a preview token scoped to source1
    preview_token = create_preview_token(user=teacher, source_id=source1.id, expires_in_seconds=300)

    client = TestClient(app)

    # 1. Preview Token must NOT be accepted on /auth/me (Bearer header or query param)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {preview_token}"})
    assert resp.status_code == 401, f"Expected 401 on /auth/me with preview token, got {resp.status_code}"

    resp_query = client.get(f"/api/v1/auth/me?token={preview_token}")
    assert resp_query.status_code == 401, f"Expected 401 on /auth/me?token=..., got {resp_query.status_code}"

    # 2. Preview Token must NOT be able to delete a source
    resp_del = client.delete(
        f"/api/v1/knowledge-center/sources/{source1.id}",
        headers={"Authorization": f"Bearer {preview_token}"},
    )
    assert resp_del.status_code == 401, f"Expected 401 on delete source, got {resp_del.status_code}"

    # 3. Preview Token must NOT be able to upload a source
    resp_up = client.post(
        "/api/v1/knowledge-center/sources/upload",
        headers={"Authorization": f"Bearer {preview_token}"},
    )
    assert resp_up.status_code == 401, f"Expected 401 on upload source, got {resp_up.status_code}"

    # 4. Preview Token must NOT be able to access teacher reports
    resp_rep = client.get(
        "/api/v1/reports/summary",
        headers={"Authorization": f"Bearer {preview_token}"},
    )
    assert resp_rep.status_code == 401, f"Expected 401 on reports summary, got {resp_rep.status_code}"

    # 5. Preview Token for source1 must NOT access preview for source2 (different source)
    resp_cross = client.get(
        f"/api/v1/knowledge-center/sources/{source2.id}/preview-file?token={preview_token}",
    )
    assert resp_cross.status_code in (403, 404), f"Expected 403/404 for different source, got {resp_cross.status_code}"


def test_session_token_still_works(setup_preview_test_env):
    data = setup_preview_test_env
    teacher = data["teacher"]
    session_token = create_session_token(teacher)

    client = TestClient(app)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {session_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == teacher.email
def test_preview_token_positive_flow_and_headers(setup_preview_test_env, tmp_path):
    data = setup_preview_test_env
    teacher = data["teacher"]
    source1 = data["source1"]

    # Write dummy content to source1 storage path
    import os
    os.makedirs(os.path.dirname(source1.storage_path), exist_ok=True)
    with open(source1.storage_path, "wb") as f:
        f.write(b"Hello World PDF simulation content for range test")

    preview_token = create_preview_token(user=teacher, source_id=source1.id, expires_in_seconds=300)
    client = TestClient(app)

    # Preview with token
    resp = client.get(f"/api/v1/knowledge-center/sources/{source1.id}/preview-file?token={preview_token}")
    assert resp.status_code == 200
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "inline" in resp.headers["Content-Disposition"]
    assert resp.headers["Accept-Ranges"] == "bytes"

    # Preview with Range header
    resp_range = client.get(
        f"/api/v1/knowledge-center/sources/{source1.id}/preview-file?token={preview_token}",
        headers={"Range": "bytes=0-10"},
    )
    assert resp_range.status_code == 206
    assert resp_range.headers["Content-Range"].startswith("bytes 0-10/")
    assert resp_range.content == b"Hello World"


def test_preview_page_renders_a_private_pdf_page(setup_preview_test_env):
    """A valid PDF page renders through the scoped token instead of returning 404."""
    import os
    from PIL import Image

    data = setup_preview_test_env
    teacher = data["teacher"]
    source = data["source1"]
    os.makedirs(os.path.dirname(source.storage_path), exist_ok=True)
    Image.new("RGB", (200, 200), "white").save(source.storage_path, "PDF")

    token = create_preview_token(user=teacher, source_id=source.id, expires_in_seconds=300)
    client = TestClient(app)
    response = client.get(
        f"/api/v1/knowledge-center/sources/{source.id}/preview-page/1?token={token}"
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content[:2] == b"\xff\xd8"
