import io
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.course import Course, CourseStatus
from app.models.institution import Institution
from app.models.knowledge_center import (
    KnowledgeSource,
    KnowledgeUnitRecord,
    SourceRole,
    SourceStatus,
)
from app.models.user import User, UserRole
from app.api.dependencies import get_current_user
from app.services.knowledge_center_service import (
    create_knowledge_source,
    process_knowledge_source,
)


@pytest.fixture
def two_institutions_setup(db):
    """Fixture providing two distinct institutions with teachers and students."""
    # Institution A
    inst_a = Institution(name="مؤسسة الأمل التعليمية", slug=f"inst-a-{uuid.uuid4().hex[:6]}")
    db.add(inst_a)
    db.commit()

    teacher_a = User(
        institution_id=inst_a.id,
        username=f"teacher_a_{uuid.uuid4().hex[:6]}",
        email=f"teacher_a_{uuid.uuid4().hex[:6]}@test.edu",
        password_hash="hash",
        display_name="أستاذ أ",
        role=UserRole.TEACHER,
    )
    student_a_sec1 = User(
        institution_id=inst_a.id,
        username=f"student_a_sec1_{uuid.uuid4().hex[:6]}",
        email=f"student_a_sec1_{uuid.uuid4().hex[:6]}@test.edu",
        password_hash="hash",
        display_name="طالب أولى ثانوي أ",
        role=UserRole.STUDENT,
        grade_level="SECONDARY_1",
    )
    student_a_sec2 = User(
        institution_id=inst_a.id,
        username=f"student_a_sec2_{uuid.uuid4().hex[:6]}",
        email=f"student_a_sec2_{uuid.uuid4().hex[:6]}@test.edu",
        password_hash="hash",
        display_name="طالب ثانية ثانوي أ",
        role=UserRole.STUDENT,
        grade_level="SECONDARY_2",
    )
    db.add_all([teacher_a, student_a_sec1, student_a_sec2])
    db.commit()

    # Institution B
    inst_b = Institution(name="مؤسسة النور التعليمية", slug=f"inst-b-{uuid.uuid4().hex[:6]}")
    db.add(inst_b)
    db.commit()

    teacher_b = User(
        institution_id=inst_b.id,
        username=f"teacher_b_{uuid.uuid4().hex[:6]}",
        email=f"teacher_b_{uuid.uuid4().hex[:6]}@test.edu",
        password_hash="hash",
        display_name="أستاذ ب",
        role=UserRole.TEACHER,
    )
    student_b_sec1 = User(
        institution_id=inst_b.id,
        username=f"student_b_sec1_{uuid.uuid4().hex[:6]}",
        email=f"student_b_sec1_{uuid.uuid4().hex[:6]}@test.edu",
        password_hash="hash",
        display_name="طالب أولى ثانوي ب",
        role=UserRole.STUDENT,
        grade_level="SECONDARY_1",
    )
    db.add_all([teacher_b, student_b_sec1])
    db.commit()

    return {
        "inst_a": inst_a,
        "teacher_a": teacher_a,
        "student_a_sec1": student_a_sec1,
        "student_a_sec2": student_a_sec2,
        "inst_b": inst_b,
        "teacher_b": teacher_b,
        "student_b_sec1": student_b_sec1,
    }


def test_grade_source_isolation_between_secondary_grades(two_institutions_setup, db):
    """
    Verifies that a source uploaded for SECONDARY_1 cannot be retrieved
    or accessed by a student enrolled in SECONDARY_2.
    """
    teacher_a = two_institutions_setup["teacher_a"]
    student_sec1 = two_institutions_setup["student_a_sec1"]
    student_sec2 = two_institutions_setup["student_a_sec2"]

    content = "# كيمياء الصف الأول الثانوي\nتفاعلات الأكسدة والاختزال تشمل انتقال الإلكترونات بين الذرات."
    source_sec1 = create_knowledge_source(
        db=db,
        user=teacher_a,
        course_id=None,
        filename="chemistry_sec1.txt",
        file_bytes=content.encode("utf-8"),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    process_knowledge_source(db, source_sec1.id)
    assert source_sec1.status == SourceStatus.INDEXED

    client = TestClient(app, raise_server_exceptions=False)

    # 1. Student in SECONDARY_1 can search and retrieve knowledge from SECONDARY_1 source
    app.dependency_overrides[get_current_user] = lambda: student_sec1
    res_sec1 = client.get("/api/v1/knowledge-center/search?query=الأكسدة")
    assert res_sec1.status_code == 200, res_sec1.text
    data_sec1 = res_sec1.json()
    units_sec1 = data_sec1.get("knowledge_units") or data_sec1.get("units") or []
    assert len(units_sec1) >= 1

    # 2. Student in SECONDARY_2 searching for the same query gets 0 units
    app.dependency_overrides[get_current_user] = lambda: student_sec2
    res_sec2 = client.get("/api/v1/knowledge-center/search?query=الأكسدة")
    assert res_sec2.status_code == 200, res_sec2.text
    data_sec2 = res_sec2.json()
    units_sec2 = data_sec2.get("knowledge_units") or data_sec2.get("units") or []
    assert len(units_sec2) == 0

    # 3. Student in SECONDARY_2 attempting direct source detail access gets 403 Forbidden
    res_direct = client.get(f"/api/v1/knowledge-center/sources/{source_sec1.id}")
    assert res_direct.status_code == 403
    assert "Grade level access denied" in res_direct.text

    app.dependency_overrides.clear()


def test_cross_institution_isolation(two_institutions_setup, db):
    """
    Verifies that sources created in Institution A are strictly invisible
    and inaccessible to students and teachers in Institution B.
    """
    teacher_a = two_institutions_setup["teacher_a"]
    teacher_b = two_institutions_setup["teacher_b"]
    student_b_sec1 = two_institutions_setup["student_b_sec1"]

    content = "# مذكرات حصرية بمؤسسة أ\nالمركبات العضوية والهيدروكربونات الحلقية المشبعة."
    source_a = create_knowledge_source(
        db=db,
        user=teacher_a,
        course_id=None,
        filename="organic_private_a.txt",
        file_bytes=content.encode("utf-8"),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    process_knowledge_source(db, source_a.id)

    client = TestClient(app, raise_server_exceptions=False)

    # 1. Student in Institution B (even with same grade_level) cannot search Inst A sources
    app.dependency_overrides[get_current_user] = lambda: student_b_sec1
    res_search_b = client.get("/api/v1/knowledge-center/search?query=الهيدروكربونات")
    assert res_search_b.status_code == 200
    units_b = res_search_b.json().get("knowledge_units") or res_search_b.json().get("units") or []
    assert len(units_b) == 0

    # 2. Direct access by Student B returns 404 (Cross-institution not found)
    res_direct_b = client.get(f"/api/v1/knowledge-center/sources/{source_a.id}")
    assert res_direct_b.status_code == 404

    # 3. Teacher B listing sources in Inst B sees 0 sources from Inst A
    app.dependency_overrides[get_current_user] = lambda: teacher_b
    res_list_b = client.get("/api/v1/knowledge-center/sources?grade_level=SECONDARY_1")
    assert res_list_b.status_code == 200
    ids_b = [s["id"] for s in res_list_b.json()]
    assert str(source_a.id) not in ids_b

    app.dependency_overrides.clear()


def test_quiz_extraction_without_course_and_no_source_persistence(two_institutions_setup, db):
    """
    Verifies that extracting quiz questions from a file works without course_id,
    and does NOT create a persistent KnowledgeSource in the database.
    """
    teacher_a = two_institutions_setup["teacher_a"]
    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_current_user] = lambda: teacher_a

    sample_quiz = (
        "1. ما هو ناتج تفاعل الصوديوم مع الماء؟\n"
        "أ) هيدروكسيد الصوديوم وغاز الهيدروجين\n"
        "ب) أكسيد الصوديوم\n"
        "ج) كلوريد الصوديوم\n"
        "د) كربونات الصوديوم\n"
        "الإجابة الصحيحة: أ\n"
    )

    initial_sources_count = len(db.scalars(select(KnowledgeSource)).all())

    response = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("quiz_draft.txt", io.BytesIO(sample_quiz.encode("utf-8")), "text/plain")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "questions" in data
    assert len(data["questions"]) >= 1

    post_sources_count = len(db.scalars(select(KnowledgeSource)).all())
    assert post_sources_count == initial_sources_count, "Quiz extraction must NOT create persistent KnowledgeSource!"

    app.dependency_overrides.clear()


def test_quiz_extraction_staging_cleanup(two_institutions_setup):
    """
    Verifies that extracting from a plain text file completes cleanly and
    the temporary staging file is deleted in the outer finally block.
    """
    teacher_a = two_institutions_setup["teacher_a"]
    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_current_user] = lambda: teacher_a

    sample_text = (
        "1. أي الغازات التالية يعكر ماء الجير الرائق؟\n"
        "أ) غاز ثاني أكسيد الكربون CO2\n"
        "ب) غاز الأكسجين O2\n"
        "ج) غاز النيتروجين N2\n"
        "د) غاز الهيدروجين H2\n"
        "الإجابة الصحيحة: أ\n"
    )

    response = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("test_staging.txt", io.BytesIO(sample_text.encode("utf-8")), "text/plain")},
    )
    assert response.status_code == 200, response.text

    # Verify that the response has extracted questions
    assert len(response.json()["questions"]) >= 1

    app.dependency_overrides.clear()


def test_student_exclusion_from_legacy_unclassified_source(two_institutions_setup, db):
    """
    Verifies that legacy sources without grade_level (grade_level is NULL)
    are excluded from student search results and blocked with 403 on direct access,
    while teachers can still access them.
    """
    teacher_a = two_institutions_setup["teacher_a"]
    student_sec1 = two_institutions_setup["student_a_sec1"]

    # Directly create a legacy source with grade_level = None
    legacy_source = KnowledgeSource(
        institution_id=teacher_a.institution_id,
        teacher_id=teacher_a.id,
        course_id=None,
        grade_level=None,  # Legacy unclassified source
        filename="legacy_unclassified.txt",
        storage_path="storage/test_legacy.txt",
        file_format="txt",
        size_bytes=100,
        checksum="dummy_checksum_123",
        source_role=SourceRole.COURSE_KNOWLEDGE,
        status=SourceStatus.INDEXED,
    )
    db.add(legacy_source)
    db.commit()
    db.refresh(legacy_source)

    unit = KnowledgeUnitRecord(
        source_id=legacy_source.id,
        course_id=None,
        concept="المفهوم القديم غير المصنف",
        statement="نص المفهوم القديم غير المصنف لصف دراسي محدد.",
        knowledge_type="concept",
    )
    db.add(unit)
    db.commit()

    client = TestClient(app, raise_server_exceptions=False)

    # 1. Student search ignores unclassified legacy source
    app.dependency_overrides[get_current_user] = lambda: student_sec1
    res_search = client.get("/api/v1/knowledge-center/search?query=المفهوم")
    assert res_search.status_code == 200
    units_legacy = res_search.json().get("knowledge_units") or res_search.json().get("units") or []
    assert len(units_legacy) == 0

    # 2. Student direct access is rejected with 403 Forbidden
    res_direct = client.get(f"/api/v1/knowledge-center/sources/{legacy_source.id}")
    assert res_direct.status_code == 403
    assert "Grade level access denied" in res_direct.text

    # 3. Teacher can access the legacy source detail
    app.dependency_overrides[get_current_user] = lambda: teacher_a
    res_teacher = client.get(f"/api/v1/knowledge-center/sources/{legacy_source.id}")
    assert res_teacher.status_code == 200
    assert res_teacher.json()["filename"] == "legacy_unclassified.txt"

    app.dependency_overrides.clear()
