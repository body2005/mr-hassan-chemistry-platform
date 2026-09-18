import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Lesson, Enrollment, EnrollmentStatus
from app.models.knowledge_center import KnowledgeSource, KnowledgeUnitRecord, SourceRole, SourceStatus
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.api.dependencies import get_current_user


@pytest.fixture
def auth_teacher_client(db):
    inst = Institution(name="Test Institute", slug=f"chem-inst-{uuid.uuid4().hex[:8]}")
    db.add(inst)
    db.commit()

    teacher = User(
        institution_id=inst.id,
        username=f"teacher_{uuid.uuid4().hex[:6]}",
        email=f"teacher_{uuid.uuid4().hex[:6]}@chem.edu",
        password_hash="dummy_hash",
        display_name="Dr. Test",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.commit()

    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="CHEM-TEST",
        title="Chemistry Testing Course",
        grade_level="SECONDARY_1",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.commit()
    db.refresh(inst)
    db.refresh(teacher)
    db.refresh(course)

    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_current_user] = lambda: teacher

    yield {"client": client, "course": course, "teacher": teacher, "inst": inst}

    app.dependency_overrides.clear()


def test_lesson_material_upload_validation(auth_teacher_client, db):
    """Verifies LESSON_MATERIAL requires lesson_id (422), but succeeds when lesson_id is provided."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]

    module = CourseModule(course_id=course.id, title="Module 1", position=1)
    db.add(module)
    db.commit()
    db.refresh(module)

    lesson = Lesson(
        module_id=module.id,
        title="Lesson 1",
        kind="video",
        position=1,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    import pypdfium2 as pdfium
    _pdf = pdfium.PdfDocument.new()
    _pdf.new_page(width=100, height=100)
    _buf = io.BytesIO()
    _pdf.save(_buf)
    _pdf.close()
    file_content = _buf.getvalue()

    # 1. Uploading LESSON_MATERIAL without lesson_id must fail with 422
    res_fail = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={
            "course_id": str(course.id),
            "source_role": "LESSON_MATERIAL",
        },
        files={"file": ("note.pdf", io.BytesIO(file_content), "application/pdf")},
    )
    assert res_fail.status_code == 422, f"Expected 422, got {res_fail.status_code}: {res_fail.text}"
    assert "lesson_id is required" in res_fail.text

    # 2. Uploading LESSON_MATERIAL with lesson_id succeeds
    res_ok = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={
            "course_id": str(course.id),
            "lesson_id": str(lesson.id),
            "source_role": "LESSON_MATERIAL",
        },
        files={"file": ("note.pdf", io.BytesIO(file_content), "application/pdf")},
    )
    assert res_ok.status_code == 200, f"Expected 200, got {res_ok.status_code}: {res_ok.text}"
    source_data = res_ok.json()
    assert source_data["source_role"] == "LESSON_MATERIAL"
    assert source_data["lesson_id"] == str(lesson.id)
    assert source_data["status"] == "QUEUED"
    assert source_data["upload_percent"] == 100
    assert source_data["indexing_percent"] == 0
    assert source_data["processing_generation"] == 1
    assert source_data["processing_attempt_id"]


def test_lesson_material_exclusion_from_general_knowledge_list(auth_teacher_client, db):
    """Ensures LESSON_MATERIAL does not appear in general KC list, but does appear when lesson_id is specified."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    teacher = auth_teacher_client["teacher"]

    module = CourseModule(course_id=course.id, title="Mod", position=1)
    db.add(module)
    db.commit()
    db.refresh(module)

    lesson = Lesson(module_id=module.id, title="Les", kind="video", position=1)
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    # General course knowledge source
    src_kc = KnowledgeSource(
        institution_id=course.institution_id,
        course_id=course.id,
        teacher_id=teacher.id,
        filename="textbook.pdf",
        file_format="pdf",
        storage_path="storage/kc_test.pdf",
        checksum="kc_checksum_123",
        size_bytes=1000,
        source_role=SourceRole.COURSE_KNOWLEDGE,
        status=SourceStatus.INDEXED,
    )
    # Lesson material source
    src_mat = KnowledgeSource(
        institution_id=course.institution_id,
        course_id=course.id,
        lesson_id=lesson.id,
        teacher_id=teacher.id,
        filename="lesson_note.pdf",
        file_format="pdf",
        storage_path="storage/mat_test.pdf",
        checksum="mat_checksum_123",
        size_bytes=500,
        source_role=SourceRole.LESSON_MATERIAL,
        status=SourceStatus.INDEXED,
    )
    db.add_all([src_kc, src_mat])
    db.commit()

    # 1. Query /knowledge-center/sources without lesson_id: only src_kc is returned
    res_general = client.get(f"/api/v1/knowledge-center/sources?course_id={course.id}")
    assert res_general.status_code == 200
    general_ids = [s["id"] for s in res_general.json()]
    assert str(src_kc.id) in general_ids
    assert str(src_mat.id) not in general_ids

    # 2. Query /knowledge-center/sources with lesson_id: src_mat is returned
    res_lesson = client.get(f"/api/v1/knowledge-center/sources?lesson_id={lesson.id}")
    assert res_lesson.status_code == 200
    lesson_ids = [s["id"] for s in res_lesson.json()]
    assert str(src_mat.id) in lesson_ids


def test_unified_source_detail_endpoint(auth_teacher_client, db):
    """Verifies GET /sources/{source_id} returns both top-level metadata and inspect hierarchy."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]
    teacher = auth_teacher_client["teacher"]

    src = KnowledgeSource(
        institution_id=course.institution_id,
        course_id=course.id,
        teacher_id=teacher.id,
        filename="chemistry_unit1.pdf",
        file_format="pdf",
        storage_path="storage/unit1.pdf",
        checksum="unit1_checksum",
        size_bytes=2048,
        source_role=SourceRole.COURSE_KNOWLEDGE,
        status=SourceStatus.INDEXED,
        progress_percent=100,
    )
    db.add(src)
    db.commit()
    db.refresh(src)

    res = client.get(f"/api/v1/knowledge-center/sources/{src.id}")
    assert res.status_code == 200
    data = res.json()

    # Metadata fields expected by uploadManager / poller
    assert data["id"] == str(src.id)
    assert data["status"] == "INDEXED"
    assert data["progress_percent"] == 100
    assert data["filename"] == "chemistry_unit1.pdf"
    assert data["file_format"] == "pdf"
    assert data["size_bytes"] == 2048
    assert "file_url" in data

    # Detail fields expected by AIKnowledgeCenterView inspect modal
    assert "units" in data
    assert "outline" in data
    assert "images" in data


def test_lesson_material_student_access_and_download(db, tmp_path):
    """Verifies that an enrolled student can see materials in /courses and download them, but non-enrolled gets 403."""
    from app.core.security import hash_password

    inst = Institution(name="Test Student Inst", slug=f"chem-inst-{uuid.uuid4().hex[:8]}")
    db.add(inst)
    db.commit()

    teacher = User(
        institution_id=inst.id,
        email="teacher_mat@example.com",
        username="teacher_mat",
        password_hash=hash_password("Pass123!"),
        display_name="Teacher Mat",
        role=UserRole.TEACHER,
        is_active=True,
    )
    student_enrolled = User(
        institution_id=inst.id,
        email="student_enrolled@example.com",
        username="student_enrolled",
        password_hash=hash_password("Pass123!"),
        display_name="Enrolled Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    student_other = User(
        institution_id=inst.id,
        email="student_other@example.com",
        username="student_other",
        password_hash=hash_password("Pass123!"),
        display_name="Other Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add_all([teacher, student_enrolled, student_other])
    db.commit()
    db.refresh(teacher)
    db.refresh(student_enrolled)
    db.refresh(student_other)

    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="CHEM-FREE",
        title="Free Chemistry Course",
        price_egp=0,
        status="published",
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    module = CourseModule(course_id=course.id, title="Module 1", position=1)
    db.add(module)
    db.commit()

    lesson = Lesson(module_id=module.id, title="Free Lesson", kind="video", position=1, price_egp=0)
    db.add(lesson)
    db.commit()

    # Enroll student_enrolled
    enrollment = Enrollment(
        course_id=course.id,
        student_id=student_enrolled.id,
        status=EnrollmentStatus.ACTIVE,
    )
    db.add(enrollment)
    db.commit()

    # Create dummy storage file
    storage_file = tmp_path / "actual_lesson_note.pdf"
    storage_file.write_bytes(b"%PDF-1.4 chemistry real notes content")

    src = KnowledgeSource(
        institution_id=inst.id,
        course_id=course.id,
        lesson_id=lesson.id,
        teacher_id=teacher.id,
        filename="actual_lesson_note.pdf",
        file_format="pdf",
        storage_path=str(storage_file),
        checksum="real_note_chk",
        size_bytes=len(b"%PDF-1.4 chemistry real notes content"),
        source_role=SourceRole.LESSON_MATERIAL,
        status=SourceStatus.INDEXED,
    )
    db.add(src)
    db.commit()

    client = TestClient(app, raise_server_exceptions=False)

    # 1. Test GET /courses for enrolled student -> materials must be present
    enrolled_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": student_enrolled.email,
            "password": "Pass123!",
            "institution_slug": inst.slug,
        },
    )
    assert enrolled_login.status_code == 200, enrolled_login.text
    res_courses = client.get("/api/v1/courses")
    assert res_courses.status_code == 200
    courses_data = res_courses.json()["items"]
    target_course = next(c for c in courses_data if c["id"] == str(course.id))
    target_lesson = target_course["modules"][0]["lessons"][0]
    assert len(target_lesson["materials"]) == 1
    assert target_lesson["materials"][0]["filename"] == "actual_lesson_note.pdf"

    # 2. Test download by enrolled student -> 200 OK with binary content
    res_dl_ok = client.get(f"/api/v1/knowledge-center/sources/{src.id}/download")
    assert res_dl_ok.status_code == 200
    assert b"%PDF-1.4 chemistry real notes content" in res_dl_ok.content

    # 3. Test download by non-enrolled student -> 403 Forbidden
    client.cookies.clear()
    other_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": student_other.email,
            "password": "Pass123!",
            "institution_slug": inst.slug,
        },
    )
    assert other_login.status_code == 200, other_login.text
    res_dl_forbidden = client.get(f"/api/v1/knowledge-center/sources/{src.id}/download")
    assert res_dl_forbidden.status_code == 403


def test_extract_quiz_from_file_is_temporary_and_does_not_require_course(auth_teacher_client, db):
    """Extraction is an independent temporary draft; a course is optional."""
    client = auth_teacher_client["client"]
    course = auth_teacher_client["course"]

    sample_text = (
        "1. ما هو الرمز الكيميائي لعنصر الصوديوم؟\n"
        "أ) Na\n"
        "ب) K\n"
        "ج) Cl\n"
        "د) Fe\n"
        "الإجابة الصحيحة: أ\n"
    )

    res_without_course = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("quiz.txt", io.BytesIO(sample_text.encode("utf-8")), "text/plain")},
    )
    assert res_without_course.status_code == 200, res_without_course.text
    assert len(res_without_course.json()["questions"]) >= 1

    res = client.post(
        "/api/v1/quiz/extract-from-file",
        data={"course_id": str(course.id)},
        files={"file": ("quiz.txt", io.BytesIO(sample_text.encode("utf-8")), "text/plain")},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "questions" in data
    assert len(data["questions"]) >= 1

    # Quiz extraction is request-scoped. It must not create a KnowledgeSource
    # or general-RAG units merely to assemble a draft.
    assert db.scalar(
        select(KnowledgeSource)
        .where(KnowledgeSource.course_id == course.id)
        .limit(1)
    ) is None
    assert db.scalar(select(KnowledgeUnitRecord).limit(1)) is None

    general = client.get(f"/api/v1/knowledge-center/sources?course_id={course.id}")
    assert general.status_code == 200
    assert general.json() == []


def test_extract_quiz_rejects_lesson_without_course(auth_teacher_client):
    client = auth_teacher_client["client"]
    response = client.post(
        "/api/v1/quiz/extract-from-file",
        data={"lesson_id": str(uuid.uuid4())},
        files={"file": ("quiz.txt", io.BytesIO(b"1. What is sodium?"), "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "COURSE_REQUIRED_FOR_LESSON"
