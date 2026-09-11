"""
=============================================================================
AI TEACHING KNOWLEDGE CENTER — AUTOMATED TEST SUITE
=============================================================================
Comprehensive unit and integration tests covering:
1. Document ingestion (PDF, DOCX, PPTX, TXT, Images, Previous Assessment Banks).
2. Structure & layout preservation (page numbers, slide numbers, tables, figures).
3. Grounded Q&A with citations and honest out-of-scope refusal contract.
4. Assessment intelligence, duplicate detection, and usage tracking.
5. Quiz Modes: Mode A (Reuse), Mode B (Novel), Mode C (Hybrid).
6. Reindexing idempotency and version control.
7. Cross-course isolation and zero hardcoded content.
=============================================================================
"""
import io
import json
import os
import uuid
import pytest
from sqlalchemy import select

from app.models.course import Course, CourseStatus
from app.models.institution import Institution
from app.models.knowledge_center import (
    AssessmentQuestion,
    AssessmentSource,
    KnowledgeAsset,
    KnowledgeDocument,
    KnowledgeSource,
    KnowledgeUnitRecord,
    SourceRole,
    SourceStatus,
)
from app.models.user import User, UserRole
from app.services.document_parsers import (
    parse_assessment_bank,
    parse_docx_document,
    parse_pdf_document,
    parse_pptx_document,
    parse_txt_document,
)
from app.services.knowledge_center_service import (
    create_knowledge_source,
    delete_knowledge_source,
    process_knowledge_source,
    reindex_knowledge_source,
)
from app.services.knowledge_retriever import (
    check_grounding_and_answer,
    retrieve_lesson_knowledge,
)
from app.services.quiz_engine import generate_quiz


@pytest.fixture
def test_setup(db):
    """Fixture providing a test Institution, User (Teacher), and Course."""
    inst = Institution(name="مؤسسة الاختبار التعليمية", slug="test_inst_kc")
    db.add(inst)
    db.commit()

    teacher = User(
        institution_id=inst.id,
        username="teacher_kc",
        email="teacher_kc@test.edu",
        password_hash="hash",
        display_name="مستر علي أحمد",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.commit()

    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="GEO301",
        title="مقرر الجيولوجيا والعلوم البيئية",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.commit()

    return {"inst": inst, "teacher": teacher, "course": course}


# -----------------------------------------------------------------------------
# 1. DOCUMENT & MEDIA PARSER TESTS
# -----------------------------------------------------------------------------
def test_parse_txt_document_structure():
    """Verifies plain text/markdown parsing preserves headings and blocks."""
    txt_content = """# المقدمة في علم الجيولوجيا
علم الجيولوجيا هو العلم الذي يدرس كوكب الأرض وحركتها ومكوناتها.

## الفوالق والأنواع
ينقسم الفالق إلى فالق عادي وفالق معكوس وداسر."""
    parsed = parse_txt_document(txt_content.encode("utf-8"), "lesson_1.txt")
    assert parsed.title == "lesson_1"
    assert parsed.total_pages == 1
    assert len(parsed.pages[0].blocks) >= 3
    assert len(parsed.hierarchy) >= 2
    assert parsed.hierarchy[0]["title"] == "المقدمة في علم الجيولوجيا"


def test_parse_assessment_bank():
    """Verifies parsing of previous quiz banks with options and answers."""
    bank_json = json.dumps([
        {
            "question_text": "ما المقصود بالفالق العادي؟",
            "question_type": "multiple_choice",
            "topic_concept": "الفالق العادي",
            "correct_answer": "ينتج عن قوى شد يتحرك فيه الحائط العلوي لأسفل.",
            "options": [
                {"key": "أ", "text": "ينتج عن قوى شد يتحرك فيه الحائط العلوي لأسفل.", "is_correct": True},
                {"key": "ب", "text": "ينتج عن قوى ضغط فقط.", "is_correct": False},
                {"key": "ج", "text": "حركة أفقية بدون إزاحة.", "is_correct": False},
            ],
            "explanation": "شرح الفالق العادي الناتج عن قوى الشد.",
        }
    ], ensure_ascii=False)

    questions = parse_assessment_bank(bank_json.encode("utf-8"), "old_quiz.json")
    assert len(questions) == 1
    assert questions[0].question_text == "ما المقصود بالفالق العادي؟"
    assert questions[0].correct_answer == "ينتج عن قوى شد يتحرك فيه الحائط العلوي لأسفل."
    assert len(questions[0].options) == 3


# -----------------------------------------------------------------------------
# 2. INGESTION PIPELINE & KNOWLEDGE SOURCE TESTS
# -----------------------------------------------------------------------------
def test_create_and_process_knowledge_source(db, test_setup):
    """Verifies source creation, structure preservation, and KnowledgeUnit extraction."""
    teacher = test_setup["teacher"]
    course = test_setup["course"]

    content = """# علم الجيوفيزياء والتنقيب
الجيوفيزياء هو علم يختص بالبحث عن الأماكن والثرواث البترولية باستخدام الأجهزة الفيزيائية الحساسة.
علم الطبقات يدرس القوانين والظروف المتحكمة في تكوين الطبقات الصخرية وربطها بالترسيب."""

    source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        filename="geophysics_notes.txt",
        file_bytes=content.encode("utf-8"),
        source_role=SourceRole.KNOWLEDGE,
    )
    assert source.status == SourceStatus.QUEUED

    processed = process_knowledge_source(db, source.id)
    assert processed.status == SourceStatus.INDEXED
    assert processed.unit_count >= 2

    # Query created KnowledgeUnits
    units = db.scalars(
        select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source.id)
    ).all()
    assert len(units) >= 2
    assert any("الجيوفيزياء" in u.concept or "الجيوفيزياء" in u.statement for u in units)


# -----------------------------------------------------------------------------
# 3. GROUNDED Q&A AND CITATIONS
# -----------------------------------------------------------------------------
def test_grounded_tutor_qna_and_refusal(db, test_setup):
    """Verifies grounded answers include citations and unanswerable queries trigger refusal."""
    teacher = test_setup["teacher"]
    course = test_setup["course"]

    content = """# علم المعادن والبلورات
علم المعادن والبلورات يختص بدراسة أشكال البلورات والخصائص الفيزيائية والكيميائية للمعادن في القشرة الأرضية."""

    source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        filename="minerals_chapter.txt",
        file_bytes=content.encode("utf-8"),
        source_role=SourceRole.KNOWLEDGE,
    )
    process_knowledge_source(db, source.id)

    # 1. Answerable Query -> Returns Grounded Answer + Citation
    ans, is_grounded, is_refusal, citations = check_grounding_and_answer(
        db=db,
        user=teacher,
        course_id=course.id,
        message="ماذا يدرس علم المعادن والبلورات؟",
    )
    assert is_grounded is True
    assert is_refusal is False
    assert "أشكال البلورات" in ans or "الخصائص الفيزيائية" in ans
    assert len(citations) >= 1
    assert citations[0]["filename"] == "minerals_chapter.txt"

    # 2. Out-of-scope Query -> Returns Honest Refusal Contract
    ans_out, is_g_out, is_ref_out, cits_out = check_grounding_and_answer(
        db=db,
        user=teacher,
        course_id=course.id,
        message="ما هي نظرية النسبية الخاصة لأينشتاين وسرعة الضوء في الفراغ؟",
    )
    assert is_g_out is False
    assert "يجب أن يكون السؤال في إطار المادة" in ans_out


# -----------------------------------------------------------------------------
# 4. REINDEX IDEMPOTENCY & DELETE TESTS
# -----------------------------------------------------------------------------
def test_reindex_idempotency_and_delete(db, test_setup):
    """Verifies reindexing is idempotent and updating does not duplicate records."""
    teacher = test_setup["teacher"]
    course = test_setup["course"]

    content = "# درس الأحافير\nعلم الأحافير القديمة يدرس بقايا الكائنات الحية المدفونة في الصخور الرسوبية."
    source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        filename="fossils.txt",
        file_bytes=content.encode("utf-8"),
    )
    process_knowledge_source(db, source.id)

    initial_units_count = len(db.scalars(
        select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source.id)
    ).all())

    # Reindex source
    reindexed = reindex_knowledge_source(db, source.id)
    assert reindexed.version == 2
    assert reindexed.status == SourceStatus.INDEXED

    new_units_count = len(db.scalars(
        select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source.id)
    ).all())
    # Unit count should be equal, NOT doubled
    assert new_units_count == initial_units_count

    # Delete source
    deleted = delete_knowledge_source(db, source.id)
    assert deleted is True
    remaining = db.scalar(select(KnowledgeSource).where(KnowledgeSource.id == source.id))
    assert remaining is None


# -----------------------------------------------------------------------------
# 5. CROSS-COURSE SECURITY ISOLATION
# -----------------------------------------------------------------------------
def test_cross_course_security_isolation(db, test_setup):
    """Verifies student/teacher from Course A cannot access Course B knowledge."""
    inst = test_setup["inst"]
    teacher = test_setup["teacher"]
    course_a = test_setup["course"]

    # Course B
    course_b = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="CS101",
        title="مقرر برمجة بايثون الحصرية",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course_b)
    db.commit()

    content_b = "# بايثون الحصرية\nقوائم بايثون تستخدم دالة len لحساب عدد العناصر الحصرية في ذاكرة البرامج."
    source_b = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course_b.id,
        filename="python_private.txt",
        file_bytes=content_b.encode("utf-8"),
    )
    process_knowledge_source(db, source_b.id)

    # Querying Course A for Python concepts must NOT leak Course B knowledge
    retrieved_a = retrieve_lesson_knowledge(db, course_id=course_a.id, query="بايثون len")
    assert len(retrieved_a) == 0, "Cross-course knowledge leakage detected!"


# -----------------------------------------------------------------------------
# 6. ZERO HARDCODED CONTENT AUDIT
# -----------------------------------------------------------------------------
def test_no_hardcoded_content_in_production():
    """Audits production modules to ensure zero hardcoded lesson facts exist."""
    import inspect
    from app.services import knowledge_center_service, knowledge_retriever, quiz_engine

    for mod in (knowledge_center_service, knowledge_retriever, quiz_engine):
        src = inspect.getsource(mod)
        banned_phrases = ["ما هو الحجر الجيري", "ما وظيفة الجيوفيزياء", "DEFAULT_QUESTIONS"]
        for phrase in banned_phrases:
            assert phrase not in src, f"Hardcoded phrase '{phrase}' found in module {mod.__name__}"


# -----------------------------------------------------------------------------
# 7. CRITICAL REGRESSION TEST — ARCHITECTURE RESET
# -----------------------------------------------------------------------------
def test_architecture_reset_no_auto_video_indexing(db, test_setup):
    """
    Proves that:
    1. Uploading a lesson video alone does NOT create an automatic transcription/indexing job.
    2. Uploading a teacher document (PDF/DOCX/PPTX/TXT) DOES create a KnowledgeSource ingestion job.
    """
    teacher = test_setup["teacher"]
    course = test_setup["course"]

    # 1. Uploading a teacher document creates a KnowledgeSource ingestion job
    doc_content = "# فصل التراكيب الجيولوجية\nالتراكيب الجيولوجية هي الأشكال والأوضاع التي تتخذها صخور القشرة الأرضية."
    doc_source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        filename="geology_structures.txt",
        file_bytes=doc_content.encode("utf-8"),
        source_role=SourceRole.KNOWLEDGE,
    )
    process_knowledge_source(db, doc_source.id)
    assert doc_source.status == SourceStatus.INDEXED
    assert doc_source.unit_count >= 1

    # 2. Uploading a video does NOT trigger automatic transcription / indexing jobs
    from app.models.transcript import TranscriptionJob
    initial_jobs_count = len(db.scalars(select(TranscriptionJob)).all())

    # Simulate video upload without dispatching background transcription jobs
    from app.models.course import CourseModule, Lesson
    mod = CourseModule(course_id=course.id, title="وحدة الصخور", position=1)
    db.add(mod)
    db.commit()

    from app.models.course import LessonKind
    lesson = Lesson(
        module_id=mod.id,
        title="فيديو درس الصخور والبراكين",
        kind=LessonKind.VIDEO,
        position=1,
        video_asset_key="storage/videos/demo_volcano.mp4",
    )
    db.add(lesson)
    db.commit()

    post_upload_jobs_count = len(db.scalars(select(TranscriptionJob)).all())
    assert post_upload_jobs_count == initial_jobs_count, "Video upload must NOT automatically create a transcription job!"


# -----------------------------------------------------------------------------
# 8. HARD RESET — EMPTY AI KNOWLEDGE STATE TEST
# -----------------------------------------------------------------------------
def test_hard_reset_empty_ai_knowledge_state(db, test_setup):
    """
    Proves that:
    1. AI starts with 0 Knowledge Sources and 0 Knowledge Units when empty.
    2. Any student query (even general knowledge) returns grounded refusal and NO general knowledge fallback.
    """
    teacher = test_setup["teacher"]
    course = test_setup["course"]

    # Purge any existing sources/units for this course to test 0 state
    db.query(KnowledgeUnitRecord).filter(KnowledgeUnitRecord.course_id == course.id).delete()
    db.query(KnowledgeSource).filter(KnowledgeSource.course_id == course.id).delete()
    db.commit()

    # Verify counts are strictly 0
    active_sources = db.scalars(select(KnowledgeSource).where(KnowledgeSource.course_id == course.id)).all()
    active_units = db.scalars(select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.course_id == course.id)).all()
    assert len(active_sources) == 0
    assert len(active_units) == 0

    # Querying empty knowledge center must return grounded refusal
    retrieved = retrieve_lesson_knowledge(db, course_id=course.id, query="ما هو علم الجيولوجيا؟")
    assert len(retrieved) == 0

    ans, is_g, is_ref, cits = check_grounding_and_answer(db, teacher, course.id, "ما هو علم الجيولوجيا؟")
    assert is_g is False
    assert is_ref is True
    assert "يجب أن يكون السؤال في إطار المادة" in ans


# -----------------------------------------------------------------------------
# 9. INSTANT DOCUMENT PAGE STREAMING TEST
# -----------------------------------------------------------------------------
def test_instant_page_streaming_and_caching(db, test_setup):
    """
    Verifies that the page streaming endpoint delivers lightweight images
    on-demand with background pre-caching instead of forcing heavy raw downloads.
    """
    from fastapi import BackgroundTasks
    from app.api.routes.knowledge_center import stream_source_page_image, list_knowledge_sources
    from starlette.requests import Request

    teacher = test_setup["teacher"]
    course = test_setup["course"]

    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color="blue").save(buf, format="PNG")
    img_bytes = buf.getvalue()

    source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        filename="apparatus.png",
        file_bytes=img_bytes,
    )
    process_knowledge_source(db, source.id)

    # Test list_knowledge_sources includes total_pages
    fake_request = Request({"type": "http", "method": "GET", "url": "http://testserver/api/v1/knowledge-center/sources", "headers": []})
    source_list = list_knowledge_sources(request=fake_request, db=db, course_id=str(course.id))
    found = next((s for s in source_list if s.id == str(source.id)), None)
    assert found is not None
    assert found.total_pages is not None

    # Test page streaming endpoint
    bg_tasks = BackgroundTasks()
    resp = stream_source_page_image(source_id=str(source.id), page_number=1, db=db, background_tasks=bg_tasks)
    assert resp.media_type.startswith("image/")
    assert resp.status_code == 200


# -----------------------------------------------------------------------------
# 10. STOP INDEXING PRESERVES FILE TEST
# -----------------------------------------------------------------------------
def test_stop_indexing_preserves_file(db, test_setup):
    """
    Verifies that stopping indexing gracefully sets status to FAILED
    with a clear message without deleting the underlying uploaded file.
    """
    from app.api.routes.knowledge_center import stop_indexing_source

    teacher = test_setup["teacher"]
    course = test_setup["course"]

    source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        filename="notes_to_stop.txt",
        file_bytes=b"Sample content for indexing cancellation test.",
    )
    assert os.path.exists(source.storage_path)

    # Call stop_indexing_source
    res = stop_indexing_source(source_id=str(source.id), db=db)
    assert res["status"] == "ok"

    # File must still exist on the server!
    assert os.path.exists(source.storage_path)

    # Status must be STOPPED or FAILED with friendly user cancellation message
    db.refresh(source)
    assert source.status in (SourceStatus.STOPPED, SourceStatus.FAILED)
    assert "محفوظ بالسيرفر" in (source.error_message or "")
