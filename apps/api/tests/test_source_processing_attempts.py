import uuid

import pytest

from app.models.course import Course, CourseStatus
from app.models.institution import Institution
from app.models.knowledge_center import KnowledgeSource, SourceRole, SourceStatus
from app.models.user import User, UserRole
from app.services.knowledge_center_service import (
    StaleProcessingAttemptError,
    _advance_indexing_progress,
)


def _source(db) -> KnowledgeSource:
    institution = Institution(name="Attempt Test", slug=f"attempt-{uuid.uuid4().hex[:8]}")
    db.add(institution)
    db.flush()
    teacher = User(
        institution_id=institution.id,
        username=f"teacher-{uuid.uuid4().hex[:8]}",
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.test",
        display_name="Attempt Teacher",
        password_hash="test",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.flush()
    course = Course(
        institution_id=institution.id,
        teacher_id=teacher.id,
        code=f"CHEM-{uuid.uuid4().hex[:6]}",
        title="Attempt Course",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.flush()
    source = KnowledgeSource(
        institution_id=institution.id,
        course_id=course.id,
        teacher_id=teacher.id,
        filename="attempt.txt",
        file_format="txt",
        storage_path="unused/attempt.txt",
        size_bytes=10,
        source_role=SourceRole.COURSE_KNOWLEDGE,
        checksum=uuid.uuid4().hex,
        status=SourceStatus.PROCESSING,
        upload_percent=100,
        indexing_percent=40,
        progress_percent=40,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def test_progress_is_monotonic_within_same_attempt(db):
    source = _source(db)
    _advance_indexing_progress(
        db,
        source,
        source.processing_generation,
        source.processing_attempt_id,
        20,
    )
    db.refresh(source)
    assert source.indexing_percent == 40
    assert source.progress_percent == 40


def test_stale_attempt_cannot_update_new_generation(db):
    source = _source(db)
    old_generation = source.processing_generation
    old_attempt_id = source.processing_attempt_id
    source.processing_generation += 1
    source.processing_attempt_id = uuid.uuid4()
    source.indexing_percent = 5
    source.progress_percent = 5
    db.commit()

    with pytest.raises(StaleProcessingAttemptError):
        _advance_indexing_progress(
            db,
            source,
            old_generation,
            old_attempt_id,
            99,
        )

    refreshed = db.get(KnowledgeSource, source.id)
    assert refreshed.processing_generation == old_generation + 1
    assert refreshed.indexing_percent == 5
