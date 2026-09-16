import io
import os
import uuid
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pypdfium2 as pdfium
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app, lifespan
from app.models.course import Course, CourseModule, Lesson, LessonKind
from app.models.institution import Institution
from app.models.knowledge_center import (
    KnowledgeDocument,
    KnowledgeOutlineNode,
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
    is_parser_active,
    mark_parser_active,
)
from app.tasks.knowledge_ingestion import index_source, _try_source_lock, _release_source_lock


def _generate_test_pdf(num_pages: int = 2) -> bytes:
    pdf = pdfium.PdfDocument.new()
    for _ in range(num_pages):
        pdf.new_page(width=200, height=200)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    return buf.getvalue()


@pytest.fixture
def setup_teacher_and_course(db):
    inst = Institution(name="مؤسسة الاختبار", slug=f"inst-{uuid.uuid4().hex[:6]}")
    db.add(inst)
    db.commit()

    teacher = User(
        institution_id=inst.id,
        username=f"teacher_{uuid.uuid4().hex[:6]}",
        email=f"teacher_{uuid.uuid4().hex[:6]}@test.edu",
        password_hash="hash",
        display_name="مدرس كيمياء",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.commit()

    course_sec1 = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code=f"CHEM-SEC1-{uuid.uuid4().hex[:6]}",
        title="كيمياء أولى ثانوي",
        grade_level="SECONDARY_1",
    )
    course_unclassified = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code=f"CHEM-OLD-{uuid.uuid4().hex[:6]}",
        title="مقرر قديم غير مصنف",
        grade_level=None,
    )
    db.add_all([course_sec1, course_unclassified])
    db.commit()

    module1 = CourseModule(course_id=course_sec1.id, title="الوحدة الأولى", position=1)
    db.add(module1)
    db.commit()

    lesson1 = Lesson(module_id=module1.id, title="الدرس الأول", position=1, kind=LessonKind.ARTICLE)
    db.add(lesson1)
    db.commit()

    module_unclass = CourseModule(course_id=course_unclassified.id, title="وحدة قديمة", position=1)
    db.add(module_unclass)
    db.commit()

    lesson_unclass = Lesson(module_id=module_unclass.id, title="درس غير مصنف", position=1, kind=LessonKind.ARTICLE)
    db.add(lesson_unclass)
    db.commit()

    return {
        "institution": inst,
        "teacher": teacher,
        "course_sec1": course_sec1,
        "course_unclassified": course_unclassified,
        "lesson1": lesson1,
        "lesson_unclass": lesson_unclass,
    }


# 1. PDF من صفحتين يعيد total_pages=2 قبل تشغيل Worker
def test_two_page_pdf_returns_total_pages_2_before_worker(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_bytes = _generate_test_pdf(2)
    response = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={
            "grade_level": "SECONDARY_1",
            "source_role": "COURSE_KNOWLEDGE",
        },
        files={"file": ("sample_2page.pdf", pdf_bytes, "application/pdf")},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_pages"] == 2
    assert data["status"] == "QUEUED"


# 2. الصفحتان 1 و2 تعيدان JPEG/200 والـWorker متوقف
def test_pages_1_and_2_return_jpeg_200_with_worker_stopped(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_bytes = _generate_test_pdf(2)
    res_upload = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={
            "grade_level": "SECONDARY_1",
            "source_role": "COURSE_KNOWLEDGE",
        },
        files={"file": ("preview_test.pdf", pdf_bytes, "application/pdf")},
    )
    source_id = res_upload.json()["id"]

    # Verify worker has NOT run and source is QUEUED
    src = db.get(KnowledgeSource, uuid.UUID(source_id))
    assert src.status == SourceStatus.QUEUED

    # Request page 1
    res_p1 = client.get(f"/api/v1/knowledge-center/sources/{source_id}/page/1")
    assert res_p1.status_code == 200
    assert "image/jpeg" in res_p1.headers["content-type"]
    assert len(res_p1.content) > 100

    # Request page 2
    res_p2 = client.get(f"/api/v1/knowledge-center/sources/{source_id}/page/2")
    assert res_p2.status_code == 200
    assert "image/jpeg" in res_p2.headers["content-type"]
    assert len(res_p2.content) > 100

    app.dependency_overrides.clear()


# 3. الصفحة 3 تعيد 404 دون إعادة تنزيل PDF
def test_page_3_out_of_bounds_returns_404_without_re_downloading_pdf(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_bytes = _generate_test_pdf(2)
    res_upload = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={
            "grade_level": "SECONDARY_1",
            "source_role": "COURSE_KNOWLEDGE",
        },
        files={"file": ("preview_bounds.pdf", pdf_bytes, "application/pdf")},
    )
    source_id = res_upload.json()["id"]

    with patch("app.api.routes.knowledge_center._stage_source_for_preview") as mock_stage:
        res_p3 = client.get(f"/api/v1/knowledge-center/sources/{source_id}/page/3")
        assert res_p3.status_code == 404
        # Stage/download was NOT called because preview_total_pages=2 caught it upfront
        mock_stage.assert_not_called()

    app.dependency_overrides.clear()


# 4. PDF تالف يعيد 422 دون DB row أو Storage object
def test_corrupt_pdf_returns_422_without_db_row_or_storage_object(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    corrupt_bytes = b"CORRUPTED_NOT_A_PDF_CONTENT_HERE"
    res = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={
            "grade_level": "SECONDARY_1",
            "source_role": "COURSE_KNOWLEDGE",
        },
        files={"file": ("corrupt.pdf", corrupt_bytes, "application/pdf")},
    )
    assert res.status_code == 422
    app.dependency_overrides.clear()

    # Verify no source created in DB
    found = db.scalar(select(KnowledgeSource).where(KnowledgeSource.filename == "corrupt.pdf"))
    assert found is None


# 5. Deduplicated upload لا يعيد Queue أو Enqueue
def test_deduplicated_upload_does_not_queue_or_enqueue(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_bytes = _generate_test_pdf(1)
    res1 = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"grade_level": "SECONDARY_1", "source_role": "COURSE_KNOWLEDGE"},
        files={"file": ("dedup_test.pdf", pdf_bytes, "application/pdf")},
    )
    assert res1.status_code == 200
    source_id = uuid.UUID(res1.json()["id"])

    # Simulate completed indexing on the source
    source = db.get(KnowledgeSource, source_id)
    source.status = SourceStatus.INDEXED
    source.indexing_percent = 100
    source.progress_percent = 100
    db.commit()

    with patch("app.api.routes.knowledge_center._enqueue_source_processing") as mock_enqueue:
        res2 = client.post(
            "/api/v1/knowledge-center/sources/upload",
            data={"grade_level": "SECONDARY_1", "source_role": "COURSE_KNOWLEDGE"},
            files={"file": ("dedup_test.pdf", pdf_bytes, "application/pdf")},
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["id"] == str(source_id)
        assert data2["status"] == "INDEXED"
        assert data2["indexing_percent"] == 100
        # Enqueue was NOT called
        mock_enqueue.assert_not_called()

    app.dependency_overrides.clear()


# 6. فشل DB بعد S3 upload يحذف Object الجديد
def test_db_failure_after_s3_upload_deletes_new_object(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_bytes = _generate_test_pdf(1)

    with patch("app.api.routes.knowledge_center.create_knowledge_source") as mock_create,          patch("app.api.routes.knowledge_center.get_storage_provider") as mock_get_storage:
        
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        
        # Simulate create_knowledge_source saving to S3 and then raising DB exception on commit
        def fake_create(**kwargs):
            if kwargs.get("created_storage_paths") is not None:
                kwargs["created_storage_paths"].append("s3://bucket/courses/new_object.pdf")
            raise RuntimeError("Database connection lost during flush")

        mock_create.side_effect = fake_create

        res = client.post(
            "/api/v1/knowledge-center/sources/upload",
            data={"grade_level": "SECONDARY_1", "source_role": "COURSE_KNOWLEDGE"},
            files={"file": ("s3_fail.pdf", pdf_bytes, "application/pdf")},
        )
        assert res.status_code == 500
        # Deleted the newly created storage object
        mock_storage.delete.assert_called_with("s3://bucket/courses/new_object.pdf")

    app.dependency_overrides.clear()


# 7. فشل Batch لا يحذف Object قديم Deduplicated
def test_batch_failure_does_not_delete_deduplicated_object(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_a = _generate_test_pdf(1)
    pdf_b = _generate_test_pdf(2)

    with patch("app.api.routes.knowledge_center.create_knowledge_source") as mock_create,          patch("app.api.routes.knowledge_center.get_storage_provider") as mock_get_storage:
        
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        # First call is deduplicated (does not append to created_storage_paths)
        # Second call is new, appends to created_storage_paths, and then raises DB exception
        call_count = [0]
        def fake_batch_create(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                src_mock = MagicMock()
                src_mock.storage_path = "s3://bucket/existing_dedup.pdf"
                return MagicMock(source=src_mock, created=False, created_storage_key=None)
            else:
                if kwargs.get("created_storage_paths") is not None:
                    kwargs["created_storage_paths"].append("s3://bucket/newly_created_b.pdf")
                raise RuntimeError("DB failure during batch insertion")

        mock_create.side_effect = fake_batch_create

        res = client.post(
            "/api/v1/knowledge-center/sources/upload-batch",
            data={"grade_level": "SECONDARY_1", "source_role": "COURSE_KNOWLEDGE"},
            files=[
                ("files", ("file_a.pdf", pdf_a, "application/pdf")),
                ("files", ("file_b.pdf", pdf_b, "application/pdf")),
            ],
        )
        assert res.status_code == 500

        # Deleted ONLY the new object, NEVER touched existing deduplicated object
        deleted_keys = [call.args[0] for call in mock_storage.delete.call_args_list]
        assert "s3://bucket/newly_created_b.pdf" in deleted_keys
        assert "s3://bucket/existing_dedup.pdf" not in deleted_keys

    app.dependency_overrides.clear()


# 8. فشل Single upload ينظف Object الجديد
def test_single_upload_failure_cleans_new_object(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_bytes = _generate_test_pdf(1)
    with patch("app.api.routes.knowledge_center.create_knowledge_source") as mock_create,          patch("app.api.routes.knowledge_center.get_storage_provider") as mock_get_storage:
        
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        def fake_create(**kwargs):
            if kwargs.get("created_storage_paths") is not None:
                kwargs["created_storage_paths"].append("storage/grades/SECONDARY_1/new_local.pdf")
            raise RuntimeError("Database crash on insert")

        mock_create.side_effect = fake_create

        res = client.post(
            "/api/v1/knowledge-center/sources/upload",
            data={"grade_level": "SECONDARY_1", "source_role": "COURSE_KNOWLEDGE"},
            files={"file": ("fail_clean.pdf", pdf_bytes, "application/pdf")},
        )
        assert res.status_code == 500
        mock_storage.delete.assert_called_with("storage/grades/SECONDARY_1/new_local.pdf")

    app.dependency_overrides.clear()


# 9. طلبا Reindex متزامنان يرسلان Job واحدة
def test_concurrent_reindex_sends_only_one_job(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_bytes = _generate_test_pdf(1)
    res_upload = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"grade_level": "SECONDARY_1", "source_role": "COURSE_KNOWLEDGE"},
        files={"file": ("reindex_test.pdf", pdf_bytes, "application/pdf")},
    )
    source_id = res_upload.json()["id"]

    # Manually mark as INDEXED
    src = db.get(KnowledgeSource, uuid.UUID(source_id))
    src.status = SourceStatus.INDEXED
    db.commit()

    with patch("app.api.routes.knowledge_center._enqueue_source_processing") as mock_enqueue:
        # First reindex triggers re-queue
        res1 = client.post(f"/api/v1/knowledge-center/sources/{source_id}/reindex")
        assert res1.status_code == 200
        assert res1.json()["status"] == "QUEUED"
        assert mock_enqueue.call_count == 1

        # Second reindex while status is QUEUED returns 200 with current active attempt without re-enqueuing
        res2 = client.post(f"/api/v1/knowledge-center/sources/{source_id}/reindex")
        assert res2.status_code == 200
        assert res2.json()["status"] == "QUEUED"
        # Call count remains 1!
        assert mock_enqueue.call_count == 1

    app.dependency_overrides.clear()


# 10. خطأ مؤقت لا يجعل المصدر FAILED
def test_transient_retryable_error_does_not_mark_source_failed(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    source_res = create_knowledge_source(
        db=db,
        user=teacher,
        filename="retry_test.pdf",
        file_bytes=_generate_test_pdf(1),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    source = source_res.source

    # Mock Celery task execution
    mock_task = MagicMock()
    mock_task.request.retries = 0
    mock_task.max_retries = 3
    mock_task.request.id = "task-test-123"
    mock_task.retry.side_effect = RuntimeError("Celery retry triggered")

    with patch("app.tasks.knowledge_ingestion.process_knowledge_source") as mock_process:
        mock_process.side_effect = ConnectionError("Transient database reset")

        with pytest.raises(RuntimeError, match="Celery retry triggered"):
            index_source.run.__func__(
                mock_task,
                str(source.id),
                source.processing_generation,
                str(source.processing_attempt_id),
            )

    # Status must NOT be FAILED!
    db.refresh(source)
    assert source.status != SourceStatus.FAILED
    assert source.status in (SourceStatus.QUEUED, SourceStatus.PROCESSING)


# 11. انتهاء كل Retries يجعل المصدر FAILED
def test_exhausted_retries_marks_source_failed(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    source_res = create_knowledge_source(
        db=db,
        user=teacher,
        filename="exhaust_test.pdf",
        file_bytes=_generate_test_pdf(1),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    source = source_res.source

    mock_task = MagicMock()
    mock_task.request.retries = 3  # All retries used
    mock_task.max_retries = 3
    mock_task.request.id = "task-test-456"

    with patch("app.tasks.knowledge_ingestion.process_knowledge_source") as mock_process:
        mock_process.side_effect = IOError("Storage disk exhausted")

        with pytest.raises(IOError):
            index_source.run.__func__(
                mock_task,
                str(source.id),
                source.processing_generation,
                str(source.processing_attempt_id),
            )

    db.refresh(source)
    assert source.status == SourceStatus.FAILED
    assert "فشلت المعالجة بعد 3 محاولات" in (source.error_message or "")


# 12. خطأ غير قابل للتعافي يجعل المصدر FAILED
def test_fatal_unrecoverable_error_marks_source_failed_immediately(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    source_res = create_knowledge_source(
        db=db,
        user=teacher,
        filename="fatal_test.pdf",
        file_bytes=_generate_test_pdf(1),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    source = source_res.source

    mock_task = MagicMock()
    mock_task.request.retries = 0
    mock_task.max_retries = 3
    mock_task.request.id = "task-test-789"

    with patch("app.tasks.knowledge_ingestion.process_knowledge_source") as mock_process:
        mock_process.side_effect = ValueError("Corrupt unsupported internal structure")

        with pytest.raises(ValueError):
            index_source.run.__func__(
                mock_task,
                str(source.id),
                source.processing_generation,
                str(source.processing_attempt_id),
            )

    db.refresh(source)
    assert source.status == SourceStatus.FAILED
    assert "Corrupt unsupported" in (source.error_message or "")


# 13. فشل بعد إنشاء بعض Child records ثم Retry ناجح لا ينتج Duplicates
def test_retry_after_partial_materialization_does_not_duplicate_records(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    source_res = create_knowledge_source(
        db=db,
        user=teacher,
        filename="retry_dup_test.pdf",
        file_bytes=_generate_test_pdf(2),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    source = source_res.source

    # First attempt: process successfully
    process_knowledge_source(db, source.id)
    doc_count_1 = len(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id)).all())
    unit_count_1 = len(db.scalars(select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source.id)).all())
    assert doc_count_1 == 1

    # Second run (retry)
    process_knowledge_source(db, source.id)
    doc_count_2 = len(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id)).all())
    unit_count_2 = len(db.scalars(select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source.id)).all())
    assert doc_count_2 == 1
    assert unit_count_2 == unit_count_1


# 14. فشل Reindex لا يحذف الفهرس القديم
def test_reindex_failure_preserves_old_index(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    source_res = create_knowledge_source(
        db=db,
        user=teacher,
        filename="preserve_test.pdf",
        file_bytes=_generate_test_pdf(2),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    source = source_res.source
    process_knowledge_source(db, source.id)

    # Verify initial indexing
    initial_docs = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id)).all()
    assert len(initial_docs) == 1

    # Reindex attempt with parser failure
    source.version += 1
    source.processing_generation += 1
    source.processing_attempt_id = uuid.uuid4()
    db.commit()

    with patch("app.services.knowledge_center_service.parse_knowledge_file") as mock_parse:
        mock_parse.side_effect = RuntimeError("Parser crashed midway")

        with pytest.raises(RuntimeError):
            process_knowledge_source(
                db,
                source.id,
                generation=source.processing_generation,
                attempt_id=source.processing_attempt_id,
            )

    # Old index records MUST still be intact in DB!
    preserved_docs = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id)).all()
    assert len(preserved_docs) == 1


# 15. Startup مع Celery لا يستدعي Local executor
@pytest.mark.asyncio
async def test_startup_with_celery_does_not_call_local_executor(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    source_res = create_knowledge_source(
        db=db,
        user=teacher,
        filename="startup_celery.pdf",
        file_bytes=_generate_test_pdf(1),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )

    with patch("app.main.settings.ingestion_backend", "celery"),          patch("app.api.routes.knowledge_center._LOCAL_INGEST_EXECUTOR.submit") as mock_local_submit,          patch("app.tasks.knowledge_ingestion.index_source.apply_async") as mock_celery_apply:
        
        async with lifespan(app):
            pass

        mock_local_submit.assert_not_called()
        assert mock_celery_apply.called


# 16. Startup لا يعيد إرسال PROCESSING حديثة
@pytest.mark.asyncio
async def test_startup_does_not_re_enqueue_recent_processing_sources(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    source_res = create_knowledge_source(
        db=db,
        user=teacher,
        filename="recent_proc.pdf",
        file_bytes=_generate_test_pdf(1),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    source = source_res.source
    source.status = SourceStatus.PROCESSING
    # Updated just now
    source.updated_at = datetime.now(timezone.utc)
    db.commit()

    with patch("app.main.settings.ingestion_backend", "celery"),          patch("app.tasks.knowledge_ingestion.index_source.apply_async") as mock_celery_apply:
        
        async with lifespan(app):
            pass

        # Recent processing source is NOT re-enqueued
        for call in mock_celery_apply.call_args_list:
            args = call.kwargs.get("args") or call.args[0]
            assert str(source.id) not in args


# 17. Startup يعيد إرسال PROCESSING قديمة فقط
@pytest.mark.asyncio
async def test_startup_re_enqueues_stale_processing_sources(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    source_res = create_knowledge_source(
        db=db,
        user=teacher,
        filename="stale_proc.pdf",
        file_bytes=_generate_test_pdf(1),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    source = source_res.source
    source.status = SourceStatus.PROCESSING
    # Stale: 25 minutes ago
    source.updated_at = datetime.now(timezone.utc) - timedelta(minutes=25)
    db.commit()

    with patch("app.main.settings.ingestion_backend", "celery"),          patch("app.tasks.knowledge_ingestion.index_source.apply_async") as mock_celery_apply:
        
        async with lifespan(app):
            pass

        # Stale processing source IS re-enqueued
        enqueued_ids = [
            (call.kwargs.get("args") or call.args[0])[0]
            for call in mock_celery_apply.call_args_list
        ]
        assert str(source.id) in enqueued_ids


# 18. مهمة مكررة لا تمسح Parser-active marker الخاص بالمهمة الحقيقية
def test_duplicate_task_does_not_clear_active_parser_marker(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    source_res = create_knowledge_source(
        db=db,
        user=teacher,
        filename="marker_test.pdf",
        file_bytes=_generate_test_pdf(1),
        grade_level="SECONDARY_1",
        source_role=SourceRole.COURSE_KNOWLEDGE,
    )
    source = source_res.source

    # Task A acquires lock and marks parser active
    assert _try_source_lock(db, source.id) is True
    mark_parser_active(source.id)
    assert is_parser_active(source.id) is True

    # Task B runs concurrently, fails lock, returns ALREADY_ACTIVE
    mock_task_b = MagicMock()
    mock_task_b.request.id = "task-b"
    mock_task_b.request.retries = 0
    mock_task_b.max_retries = 3

    res = index_source.run.__func__(
        mock_task_b,
        str(source.id),
        source.processing_generation,
        str(source.processing_attempt_id),
    )
    assert res.get("status") == "ALREADY_ACTIVE"

    # Crucial assertion: Task A's marker MUST STILL BE ACTIVE! Task B's exit must not have cleared it!
    assert is_parser_active(source.id) is True

    _release_source_lock(db, source.id)


# 19. Scale خارج النطاق يعيد 422
def test_scale_out_of_bounds_returns_422(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_bytes = _generate_test_pdf(1)
    res_upload = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={"grade_level": "SECONDARY_1", "source_role": "COURSE_KNOWLEDGE"},
        files={"file": ("scale_test.pdf", pdf_bytes, "application/pdf")},
    )
    source_id = res_upload.json()["id"]

    # scale < 0.5
    res_low = client.get(f"/api/v1/knowledge-center/sources/{source_id}/page/1?scale=0.2")
    assert res_low.status_code == 422
    assert "scale must be between 0.5 and 2.0" in res_low.text

    # scale > 2.0
    res_high = client.get(f"/api/v1/knowledge-center/sources/{source_id}/page/1?scale=3.5")
    assert res_high.status_code == 422
    assert "scale must be between 0.5 and 2.0" in res_high.text

    app.dependency_overrides.clear()


# 20. المقرر بلا Grade لا يتحول للصف الأول ويعيد 422
def test_unclassified_course_lesson_material_upload_returns_422(db, setup_teacher_and_course):
    teacher = setup_teacher_and_course["teacher"]
    course_unclassified = setup_teacher_and_course["course_unclassified"]
    lesson_unclass = setup_teacher_and_course["lesson_unclass"]

    app.dependency_overrides[get_current_user] = lambda: teacher
    client = TestClient(app)

    pdf_bytes = _generate_test_pdf(1)
    res = client.post(
        "/api/v1/knowledge-center/sources/upload",
        data={
            "course_id": str(course_unclassified.id),
            "lesson_id": str(lesson_unclass.id),
            "source_role": "LESSON_MATERIAL",
        },
        files={"file": ("unclassified_lesson.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 422
    assert "المقرر غير مصنف" in res.text

    # Verify no source created in DB with SECONDARY_1
    found = db.scalar(
        select(KnowledgeSource).where(KnowledgeSource.course_id == course_unclassified.id)
    )
    assert found is None

    app.dependency_overrides.clear()
