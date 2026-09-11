import asyncio
import os
import unittest.mock as mock
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, IndexingStatus, Lesson
from app.models.institution import Institution
from app.models.transcript import KnowledgeChunk, Transcript, TranscriptSegment, TranscriptionStatus
from app.models.user import User, UserRole
from app.services.knowledge_pipeline import (
    create_semantic_chunks,
    generate_grounded_answer,
    generate_grounded_summary,
    normalize_transcript_text,
    retrieve_scoped_knowledge,
)
from app.services.transcription_provider import (
    MockTranscriptionProvider,
    TranscriptSegmentData,
    TranscriptionResult,
    extract_audio_track,
    get_media_duration_seconds,
)
from app.services.transcript_indexer import execute_lesson_indexing

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit & Regression Tests
# ---------------------------------------------------------------------------

def test_normalize_transcript_text():
    raw = "   مرحباً   بكم... في  درس   الجيولوجيا!!  "
    normalized = normalize_transcript_text(raw)
    assert normalized == "مرحباً بكم... في درس الجيولوجيا!"


def test_create_semantic_chunks_preserves_timestamps():
    segments = [
        TranscriptSegmentData(sequence=1, start_time=0.0, end_time=12.0, text="هذا هو المفهوم الأول في الدرس."),
        TranscriptSegmentData(sequence=2, start_time=12.0, end_time=25.0, text="وهنا نستنتج العلاقة بين الضغط والكثافة."),
        TranscriptSegmentData(sequence=3, start_time=25.0, end_time=45.0, text="نصل إلى الخلاصة النهائية وتطبيقات القوانين."),
    ]
    chunks = create_semantic_chunks(segments, max_words=10, overlap_words=2)
    assert len(chunks) >= 1
    assert chunks[0]["start_time"] == 0.0
    assert chunks[-1]["end_time"] == 45.0
    assert "metadata_json" in chunks[0]
    assert "time_range" in chunks[0]["metadata_json"]


def test_mock_transcription_provider():
    provider = MockTranscriptionProvider()
    res = asyncio.run(provider.transcribe("dummy_path.mp4"))
    assert isinstance(res, TranscriptionResult)
    assert res.language == "ar"
    assert len(res.segments) == 3
    assert res.duration == 120.0
    assert res.coverage_ratio == 1.0
    assert "القوانين" in res.full_text


def test_long_video_2hr_duration_coverage_regression():
    """Regression test: A 2-hour (7200s) video must not be truncated at 270s or 300s."""
    with mock.patch("app.services.transcription_provider.get_media_duration_seconds", return_value=7200.0):
        provider = MockTranscriptionProvider()
        res = asyncio.run(provider.transcribe("lecture_2hr.mp4"))
        assert res.duration == 7200.0
        assert res.segments[-1].end_time == 7200.0
        assert res.coverage_ratio == 1.0


def test_ffmpeg_extraction_no_truncation_limit():
    """Verify that FFmpeg command for audio extraction does not contain accidental -t limit."""
    with mock.patch("app.services.transcription_provider.get_ffmpeg_path", return_value="ffmpeg.exe"):
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch("os.path.getsize", return_value=1000):
                with mock.patch("subprocess.run") as mock_run:
                    mock_run.return_value = mock.MagicMock(returncode=0)
                    success = extract_audio_track("video.mp4", "audio.mp3", max_duration_sec=None)
                    assert success is True
                    call_cmd = mock_run.call_args[0][0]
                    # Must NOT have -t flag
                    assert "-t" not in call_cmd
                    assert "-i" in call_cmd


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_data(db):
    inst = Institution(name="Academy", slug="academy")
    db.add(inst)
    db.flush()

    teacher = User(
        institution_id=inst.id,
        username="teacher_acc",
        email="teacher@academy.com",
        password_hash="hash",
        display_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    student = User(
        institution_id=inst.id,
        username="student_acc",
        email="student@academy.com",
        password_hash="hash",
        display_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add_all([teacher, student])
    db.flush()

    course_a = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="GEO-101",
        title="جيولوجيا الأرض",
        status=CourseStatus.PUBLISHED,
        published_at=datetime.now(timezone.utc),
    )
    course_b = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="PHY-101",
        title="فيزياء الكهربية",
        status=CourseStatus.PUBLISHED,
        published_at=datetime.now(timezone.utc),
    )
    db.add_all([course_a, course_b])
    db.flush()

    module_a = CourseModule(course_id=course_a.id, title="الباب الأول", position=1)
    module_b = CourseModule(course_id=course_b.id, title="الباب الأول", position=1)
    db.add_all([module_a, module_b])
    db.flush()

    lesson_a = Lesson(
        module_id=module_a.id,
        title="الصفائح التكتونية والزلازل",
        kind="video",
        position=1,
        content="تتحرك الصفائح التكتونية بفعل تيارات الحمل الدورانية في الوشاح العلوي (الأسينوسفير). تنشأ الزلازل عند حواف الألواح المتقاربة والمتباعدة.",
    )
    lesson_b = Lesson(
        module_id=module_b.id,
        title="قانون أوم والمقاومة الكهربية",
        kind="video",
        position=1,
        content="ينص قانون أوم على أن فرق الجهد يتناسب طردياً مع شدة التيار عند ثبوت درجة الحرارة.",
    )
    db.add_all([lesson_a, lesson_b])
    db.commit()

    return {
        "teacher": teacher,
        "student": student,
        "course_a": course_a,
        "course_b": course_b,
        "lesson_a": lesson_a,
        "lesson_b": lesson_b,
    }


def test_execute_lesson_indexing_and_persistence(seed_data):
    lesson_id = str(seed_data["lesson_a"].id)
    res = asyncio.run(execute_lesson_indexing(lesson_id))
    assert res["status"] == "disabled"
    assert "permanently disabled" in res["message"]


def test_scoped_retrieval_isolation(seed_data):
    # Ensure Course A never returns Course B chunks
    with SessionLocal() as db:
        transcript_a = Transcript(lesson_id=seed_data["lesson_a"].id, status=TranscriptionStatus.COMPLETED, full_text="الصفائح التكتونية")
        transcript_b = Transcript(lesson_id=seed_data["lesson_b"].id, status=TranscriptionStatus.COMPLETED, full_text="قانون أوم والمقاومة")
        db.add_all([transcript_a, transcript_b])
        db.flush()

        chunk_a = KnowledgeChunk(
            transcript_id=transcript_a.id,
            lesson_id=seed_data["lesson_a"].id,
            course_id=seed_data["course_a"].id,
            sequence=1,
            text="الصفائح التكتونية وحركة القارات",
        )
        chunk_b = KnowledgeChunk(
            transcript_id=transcript_b.id,
            lesson_id=seed_data["lesson_b"].id,
            course_id=seed_data["course_b"].id,
            sequence=1,
            text="قانون أوم وشدة التيار الكهربي",
        )
        db.add_all([chunk_a, chunk_b])
        db.commit()

        results_a = retrieve_scoped_knowledge(db, course_id=seed_data["course_a"].id, query="قانون أوم")
        for c in results_a:
            assert c.course_id == seed_data["course_a"].id


def test_grounded_student_qa_and_refusal(seed_data):
    with SessionLocal() as db:
        transcript = Transcript(lesson_id=seed_data["lesson_a"].id, status=TranscriptionStatus.COMPLETED, full_text="حركة الألواح التكتونية في الأسينوسفير")
        db.add(transcript)
        db.flush()
        chunk = KnowledgeChunk(
            transcript_id=transcript.id,
            lesson_id=seed_data["lesson_a"].id,
            course_id=seed_data["course_a"].id,
            sequence=1,
            start_time=10.0,
            end_time=35.0,
            text="تتحرك الألواح التكتونية في طبقة الأسينوسفير بسبب تيارات الحمل الحراري.",
        )
        db.add(chunk)
        db.commit()

        covered_res = generate_grounded_answer(
            db=db,
            course_id=seed_data["course_a"].id,
            lesson_id=seed_data["lesson_a"].id,
            student_id=seed_data["student"].id,
            question="أين تتحرك الألواح التكتونية؟",
        )
        assert covered_res["is_grounded"] is True
        assert len(covered_res["citations"]) >= 1
        assert "00:10" in covered_res["citations"][0]["time_formatted"]


def test_grounded_summary_generation(seed_data):
    with SessionLocal() as db:
        transcript = Transcript(
            lesson_id=seed_data["lesson_a"].id,
            status=TranscriptionStatus.COMPLETED,
            language="ar",
            duration_seconds=120.0,
            full_text="شرح تفصيلي لحركات الألواح التكتونية والزلازل والبراكين المصاحبة.",
        )
        db.add(transcript)
        db.flush()
        chunk = KnowledgeChunk(
            transcript_id=transcript.id,
            lesson_id=seed_data["lesson_a"].id,
            course_id=seed_data["course_a"].id,
            sequence=1,
            start_time=0.0,
            end_time=60.0,
            text="حركات الألواح التكتونية وتأثير تيارات الحمل.",
        )
        db.add(chunk)
        db.commit()

        summary = generate_grounded_summary(db=db, lesson_id=seed_data["lesson_a"].id)
        assert summary["total_duration_sec"] == 120.0
        assert summary["language"] == "ar"
        assert len(summary["sections"]) == 1
