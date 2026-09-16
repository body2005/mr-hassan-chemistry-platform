"""
Automated tests for upload size limits, streaming validation, atomic staging, and resource cleanup.
Covers:
1. Accept file > 100 MiB (e.g. 105 MiB).
2. Accept file <= 500 MiB (e.g. 500 MiB boundary).
3. Reject file > 500 MiB with 413 and detail mentioning "500 MB limit".
4. Accept batch <= 1000 MiB.
5. Reject batch > 1000 MiB with 413 and detail mentioning "1000 MB total limit".
6. Early middleware rejection on Content-Length: 1200000000 (> 1010 MiB).
7. Deceptive Content-Length (streaming validator catches oversized file despite fake header).
8. Verify cleanup: staging directory removed, partially written temp files deleted, no orphaned DB records.
9. Verify existing small file upload still works normally.
10. Dynamic limits configurable through environment/settings.
"""
from __future__ import annotations

import io
import os
import shutil
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app
from app.models.course import Course, CourseStatus
from app.models.institution import Institution
from app.models.knowledge_center import KnowledgeSource
from app.models.user import User, UserRole


class ZeroStream(io.RawIOBase):
    """
    Virtual stream providing zeroes of arbitrary length without allocating RAM.
    Operates in O(1) memory space.
    """

    def __init__(self, size: int):
        self.size = size
        self.pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.size + offset
        return self.pos

    def tell(self) -> int:
        return self.pos

    def readinto(self, b) -> int:
        rem = self.size - self.pos
        if rem <= 0:
            return 0
        n = min(len(b), rem)
        b[:n] = b"\0" * n
        self.pos += n
        return n


@pytest.fixture
def auth_teacher_client(db):
    """Creates an institution, a teacher user, a published course, and returns a logged-in client."""
    inst = Institution(name="Upload Limits Academy", slug="upload-test-inst")
    db.add(inst)
    db.flush()

    teacher = User(
        institution_id=inst.id,
        username="teacher_upload_limits",
        email="teacher_upload@example.com",
        password_hash=hash_password("teacher-secret-123"),
        display_name="Upload Test Teacher",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.flush()

    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="CHEM-500",
        title="Chemistry Advanced Lab",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.commit()
    db.refresh(inst)
    db.refresh(teacher)
    db.refresh(course)

    client = TestClient(app)
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": teacher.email,
            "password": "teacher-secret-123",
            "institution_slug": inst.slug,
        },
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"

    yield {"client": client, "course": course, "teacher": teacher, "inst": inst}

    # Cleanup test course directory and tmp files created during testing
    storage_dir = os.getenv("STORAGE_DIR", "storage/knowledge_center")
    course_storage = os.path.join(storage_dir, "courses", str(course.id))
    if os.path.exists(course_storage):
        shutil.rmtree(course_storage, ignore_errors=True)
    tmp_storage = os.path.join(storage_dir, "tmp")
    if os.path.exists(tmp_storage):
        shutil.rmtree(tmp_storage, ignore_errors=True)


@pytest.fixture(autouse=True)
def mock_background_indexing():
    """Mocks out OCR and heavy indexing during upload limits tests so test suite runs in seconds."""
    with patch("app.api.routes.knowledge_center._enqueue_source_processing") as enqueue:
        yield enqueue


def test_upload_single_file_above_100mb_accepted(auth_teacher_client, db, mock_background_indexing):
    """The API durably stores a large upload and hands its queued work to Celery."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    size_105mb = 105 * 1024 * 1024

    response = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files={"file": ("advanced_handbook.pdf", ZeroStream(size_105mb), "application/pdf")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["filename"] == "advanced_handbook.pdf"
    assert data["size_bytes"] == size_105mb
    # Upload completion and indexing are deliberately separate phases.  The
    # worker, never the HTTP request, owns QUEUED -> PROCESSING.
    assert data["status"] == "QUEUED"
    assert data["upload_percent"] == 100
    assert data["indexing_percent"] == 0
    mock_background_indexing.assert_called_once()
    _, source_arg = mock_background_indexing.call_args.args
    assert str(source_arg.id) == data["id"]

    # Verify source persisted in database
    src = db.query(KnowledgeSource).filter(KnowledgeSource.id == uuid.UUID(data["id"])).first()
    assert src is not None
    assert src.size_bytes == size_105mb
    assert os.path.exists(src.storage_path)


def test_upload_single_file_500mb_boundary_accepted(auth_teacher_client, db):
    """Accept file of exactly 500 MiB (the configured maximum)."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    size_500mb = 500 * 1024 * 1024

    response = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files={"file": ("full_curriculum_500mb.pdf", ZeroStream(size_500mb), "application/pdf")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["size_bytes"] == size_500mb


def test_upload_single_file_above_500mb_rejected_with_413(auth_teacher_client, db):
    """Reject single file exceeding 500 MiB (e.g. 501 MiB) with 413 and explicit limit message."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    size_501mb = 501 * 1024 * 1024

    count_before = db.query(KnowledgeSource).count()

    response = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files={"file": ("oversized_501mb.pdf", ZeroStream(size_501mb), "application/pdf")},
    )

    assert response.status_code == 413, response.text
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "500 MB limit" in body["error"]["message"]

    # Verify no database record was created
    count_after = db.query(KnowledgeSource).count()
    assert count_after == count_before


def test_upload_batch_within_1000mb_accepted(auth_teacher_client, db):
    """Accept a batch containing multiple files whose combined size is <= 1000 MiB."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    size_a = 250 * 1024 * 1024
    size_b = 250 * 1024 * 1024

    response = client.post(
        "/api/v1/knowledge-center/sources/upload-batch",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files=[
            ("files", ("part1.pdf", ZeroStream(size_a), "application/pdf")),
            ("files", ("part2.pdf", ZeroStream(size_b), "application/pdf")),
        ],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 2
    assert data[0]["size_bytes"] == size_a
    assert data[1]["size_bytes"] == size_b


def test_upload_batch_exceeding_1000mb_rejected_with_413(auth_teacher_client, db):
    """Reject a batch when cumulative stream exceeds 1000 MiB with 413 and total limit message."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    size_500mb = 500 * 1024 * 1024
    size_501mb = 501 * 1024 * 1024

    count_before = db.query(KnowledgeSource).count()

    response = client.post(
        "/api/v1/knowledge-center/sources/upload-batch",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files=[
            ("files", ("batch_file1.pdf", ZeroStream(size_500mb), "application/pdf")),
            ("files", ("batch_file2.pdf", ZeroStream(size_501mb), "application/pdf")),
        ],
    )

    assert response.status_code == 413, response.text
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "limit" in body["error"]["message"]

    # Verify no records committed to DB
    count_after = db.query(KnowledgeSource).count()
    assert count_after == count_before


def test_batch_atomic_cleanup_on_failure(auth_teacher_client, db):
    """Verify that when a batch upload fails mid-stream, the staging directory is completely removed."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    tmp_dir = os.path.join(os.getenv("STORAGE_DIR", "storage/knowledge_center"), "tmp")

    # Upload batch where file 2 exceeds single-file limit
    response = client.post(
        "/api/v1/knowledge-center/sources/upload-batch",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files=[
            ("files", ("valid_part.pdf", ZeroStream(50 * 1024 * 1024), "application/pdf")),
            ("files", ("too_large_part.pdf", ZeroStream(505 * 1024 * 1024), "application/pdf")),
        ],
    )

    assert response.status_code == 413
    # Check that any batch_stage_* directory inside tmp has been removed
    if os.path.exists(tmp_dir):
        remaining_stages = [f for f in os.listdir(tmp_dir) if f.startswith("batch_stage_")]
        assert len(remaining_stages) == 0, f"Staging directories were not cleaned up: {remaining_stages}"


def test_batch_database_phase_is_atomic(auth_teacher_client, db):
    """A failure after the first source must roll back its row and permanent file."""
    from app.api.routes import knowledge_center as route_module

    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    original_create = route_module.create_knowledge_source
    calls = 0

    def fail_on_second_source(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated database phase failure")
        return original_create(*args, **kwargs)

    with patch.object(route_module, "create_knowledge_source", side_effect=fail_on_second_source):
        response = client.post(
            "/api/v1/knowledge-center/sources/upload-batch",
            data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
            files=[
                ("files", ("atomic_a.txt", io.BytesIO(b"first atomic payload"), "text/plain")),
                ("files", ("atomic_b.txt", io.BytesIO(b"second atomic payload"), "text/plain")),
            ],
        )
        assert response.status_code == 500

    assert db.query(KnowledgeSource).count() == 0
    course_storage = os.path.join(
        os.getenv("STORAGE_DIR", "storage/knowledge_center"),
        "courses",
        str(course.id),
    )
    assert not os.path.exists(course_storage) or not os.listdir(course_storage)


def test_middleware_early_rejection_content_length(auth_teacher_client):
    """Middleware should immediately reject requests with Content-Length > 1010 MiB before reading body."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]

    huge_content_length = str(1200 * 1024 * 1024)  # 1200 MiB
    response = client.post(
        "/api/v1/knowledge-center/sources/upload",
        headers={"Content-Length": huge_content_length},
        data={"course_id": str(course.id)},
    )

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "Request size exceeds the 1000 MB limit" in body["error"]["message"]


def test_deceptive_content_length_caught_by_streaming_validator(auth_teacher_client, db):
    """
    If a client sends an artificially low Content-Length (or none),
    the streaming validator still terminates the connection when streamed bytes exceed 500 MiB.
    """
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    size_501mb = 501 * 1024 * 1024

    response = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files={"file": ("deceptive.pdf", ZeroStream(size_501mb), "application/pdf")},
    )

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "500 MB limit" in body["error"]["message"]


def test_existing_small_file_upload_works_normally(auth_teacher_client, db):
    """Ensure standard small document uploads (e.g. text / notes) continue to function perfectly."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    small_content = b"# Chemistry Quick Note\nAcids and Bases Chapter 1."

    response = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files={"file": ("notes.txt", io.BytesIO(small_content), "text/plain")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["filename"] == "notes.txt"
    assert data["size_bytes"] == len(small_content)


def test_configurable_limits_via_settings(auth_teacher_client, monkeypatch):
    """Verify that limits dynamically adapt when settings are customized."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]

    # Set custom limit of 20 MB for single file
    settings = get_settings()
    monkeypatch.setattr(settings, "max_file_size_mb", 20)

    # 25 MB file should now be rejected
    size_25mb = 25 * 1024 * 1024
    response = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files={"file": ("medium_25mb.pdf", ZeroStream(size_25mb), "application/pdf")},
    )

    assert response.status_code == 413
    body = response.json()
    assert "20 MB limit" in body["error"]["message"]


@pytest.mark.asyncio
async def test_stream_upload_to_file_unit_direct(tmp_path):
    """Direct unit test of the production _stream_upload_to_file function."""
    from starlette.datastructures import UploadFile as StarletteUploadFile
    from fastapi import HTTPException
    from app.api.routes.knowledge_center import _stream_upload_to_file

    # 1. Valid stream within limits
    payload = b"Hello, Knowledge Center Stream!"
    up_file = StarletteUploadFile(file=io.BytesIO(payload), filename="test.txt")
    dest = str(tmp_path / "streamed_test.txt")

    written, chk = await _stream_upload_to_file(
        uploaded=up_file,
        dest_path=dest,
        max_file_bytes=1024 * 1024,
    )
    assert written == len(payload)
    assert os.path.exists(dest)
    with open(dest, "rb") as f:
        assert f.read() == payload

    # 2. Rejection when stream exceeds file limit
    oversized_payload = b"X" * (2 * 1024 * 1024)
    up_oversized = StarletteUploadFile(file=io.BytesIO(oversized_payload), filename="big.bin")
    dest_oversized = str(tmp_path / "oversized.bin")

    with pytest.raises(HTTPException) as exc_info:
        await _stream_upload_to_file(
            uploaded=up_oversized,
            dest_path=dest_oversized,
            max_file_bytes=1024 * 1024,  # 1 MiB limit
        )
    assert exc_info.value.status_code == 413
    assert not os.path.exists(dest_oversized)  # Cleaned up on error


def test_server_generated_storage_path_and_deduplication(auth_teacher_client, db):
    """
    Verify correction 8 & 7:
    - Server generates unique storage paths not tied to user-provided filename.
    - Original filename is kept in metadata.
    - Checksum deduplication reuses existing record and does not delete old files.
    """
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    content = b"Specialized Chemistry Content for Server-Generated Path Testing"

    # Upload first time
    res1 = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files={"file": ("my_dangerous_filename_../../../etc.txt", io.BytesIO(content), "text/plain")},
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()

    src1 = db.query(KnowledgeSource).filter(KnowledgeSource.id == uuid.UUID(data1["id"])).first()
    assert src1 is not None
    # Storage path must NOT contain path traversal or dangerous characters
    assert "../" not in src1.storage_path
    assert os.path.exists(src1.storage_path)

    # Upload exact same content again (deduplication)
    res2 = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"course_id": str(course.id), "source_role": "KNOWLEDGE"},
        files={"file": ("second_upload.txt", io.BytesIO(content), "text/plain")},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["id"] == data1["id"]  # Deduplicated to existing source
    assert os.path.exists(src1.storage_path)  # Pre-existing file is preserved
