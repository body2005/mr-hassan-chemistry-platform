"""
=============================================================================
AI TEACHING KNOWLEDGE CENTER — DATABASE MODELS
=============================================================================
Database schema for Knowledge Sources, Ingested Documents, Knowledge Assets (Media/Images),
Structured Educational Knowledge Units, Assessment Banks, Questions, and Usage History.
=============================================================================
"""
from __future__ import annotations

import uuid
from datetime import datetime
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_values


class SourceRole(StrEnum):
    # Canonical upload roles. Legacy values remain readable so existing rows can
    # be migrated forward without breaking historical audit records.
    COURSE_KNOWLEDGE = "COURSE_KNOWLEDGE"
    LESSON_MATERIAL = "LESSON_MATERIAL"
    QUIZ_IMPORT = "QUIZ_IMPORT"
    ASSESSMENT = "ASSESSMENT"

    # Legacy roles (not accepted by new upload endpoints).
    KNOWLEDGE = "KNOWLEDGE"
    ANSWER_KEY = "ANSWER_KEY"
    REFERENCE = "REFERENCE"
    MEDIA = "MEDIA"
    VIDEO_TRANSCRIPT = "VIDEO_TRANSCRIPT"
    TEACHER_NOTE = "TEACHER_NOTE"


class SourceStatus(StrEnum):
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    CANCELLED = "CANCELLED"
    DELETING = "DELETING"


class KnowledgeSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks teacher-provided educational source files and attachments."""

    __tablename__ = "knowledge_sources"
    __table_args__ = (
        Index("ix_knowledge_sources_course", "course_id"),
        Index("ix_knowledge_sources_lesson", "lesson_id"),
        Index("ix_knowledge_sources_teacher", "teacher_id"),
        Index("ix_knowledge_sources_status", "status"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=True
    )
    grade_level: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(30), nullable=False)  # pdf, docx, pptx, txt, md, image, quiz_bank
    mime_type: Mapped[str | None] = mapped_column(String(120))
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    source_role: Mapped[str] = mapped_column(String(30), default=SourceRole.COURSE_KNOWLEDGE, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    checksum: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default=SourceStatus.QUEUED, nullable=False)
    upload_percent: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    indexing_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_generation: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    processing_attempt_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, nullable=False)
    active_task_id: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)

    unit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preview_total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)

    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Metadata for an ingested document (PDF, DOCX, PPTX, TXT)."""

    __tablename__ = "knowledge_documents"

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str | None] = mapped_column(String(150))
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False)
    total_pages: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_slides: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hierarchy_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeOutlineNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A navigable book outline extracted from a source document.

    Nodes are deliberately source-scoped: a teacher can upload several editions
    of the same book without mixing their units, lessons, or topics.
    """

    __tablename__ = "knowledge_outline_nodes"
    __table_args__ = (
        Index("ix_knowledge_outline_source_position", "source_id", "position"),
        Index("ix_knowledge_outline_course_kind", "course_id", "node_kind"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_outline_nodes.id", ondelete="CASCADE"), index=True
    )
    node_kind: Mapped[str] = mapped_column(String(20), nullable=False)  # book|unit|lesson|topic
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    start_page: Mapped[int | None] = mapped_column(Integer)
    end_page: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeLessonRelation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Evidence-preserving links between source-scoped lesson outline nodes."""

    __tablename__ = "knowledge_lesson_relations"
    __table_args__ = (
        UniqueConstraint("from_outline_node_id", "to_outline_node_id", "relation_type", name="uq_knowledge_lesson_relation"),
        Index("ix_knowledge_lesson_relations_source", "source_id", "relation_type"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=True
    )
    from_outline_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_outline_nodes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    to_outline_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_outline_nodes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)  # previous|next|prerequisite|depends_on|related_to|builds_on|same_topic
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    evidence_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeConcept(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Canonical concept node used by the course-scoped knowledge graph."""

    __tablename__ = "knowledge_concepts"
    __table_args__ = (
        UniqueConstraint("course_id", "normalized_label", name="uq_knowledge_concepts_course_label"),
        Index("ix_knowledge_concepts_course_label", "course_id", "label"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(300), nullable=False)
    concept_type: Mapped[str] = mapped_column(String(40), default="concept", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeConceptLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Provenance-safe link from a concept to a unit, question, or image."""

    __tablename__ = "knowledge_concept_links"
    __table_args__ = (
        UniqueConstraint("concept_id", "entity_type", "entity_id", name="uq_knowledge_concept_link"),
        Index("ix_knowledge_concept_links_entity", "entity_type", "entity_id"),
    )

    concept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_concepts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)  # unit|question|asset
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeConceptRelation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Directed, evidence-carrying concept-to-concept relationship."""

    __tablename__ = "knowledge_concept_relations"
    __table_args__ = (
        UniqueConstraint("from_concept_id", "to_concept_id", "source_id", "relation_type", name="uq_knowledge_concept_relation"),
    )

    from_concept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_concepts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True
    )
    to_concept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_concepts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(50), default="related_to", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    evidence_unit_ids_json: Mapped[list | None] = mapped_column(JSON)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeQueryEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Course-scoped retrieval telemetry; stores no generated answer text."""

    __tablename__ = "knowledge_query_events"
    __table_args__ = (
        Index("ix_knowledge_query_events_course_created", "course_id", "created_at"),
        Index("ix_knowledge_query_events_outline", "outline_node_id"),
    )

    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL"), index=True
    )
    outline_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_outline_nodes.id", ondelete="SET NULL"), index=True
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)  # supported|partial|not_found
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeConversationTurn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Conversation memory kept separate from book knowledge and source content."""

    __tablename__ = "knowledge_conversation_turns"
    __table_args__ = (
        Index("ix_knowledge_conversation_session", "user_id", "course_id", "session_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(120), nullable=False)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_unit_ids_json: Mapped[list | None] = mapped_column(JSON)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)


class KnowledgeAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """First-class media assets (diagrams, charts, figures, question images)."""

    __tablename__ = "knowledge_assets"
    __table_args__ = (
        Index("ix_knowledge_assets_source", "source_id"),
        Index("ix_knowledge_assets_kind", "asset_kind"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    outline_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_outline_nodes.id", ondelete="SET NULL"), index=True
    )

    page_number: Mapped[int | None] = mapped_column(Integer)
    slide_number: Mapped[int | None] = mapped_column(Integer)

    asset_kind: Mapped[str] = mapped_column(String(40), default="figure", nullable=False)  # diagram, chart, figure, map, question_image, formula, table_image
    caption: Mapped[str | None] = mapped_column(Text)
    surrounding_text: Mapped[str | None] = mapped_column(Text)

    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeUnitRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Database record for a structured educational Knowledge Unit."""

    __tablename__ = "knowledge_units_records"
    __table_args__ = (
        Index("ix_ku_records_course", "course_id"),
        Index("ix_ku_records_lesson", "lesson_id"),
        Index("ix_ku_records_source", "source_id"),
        Index("ix_ku_records_concept", "concept"),
    )

    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=True
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(30), default="document", nullable=False)

    concept: Mapped[str] = mapped_column(String(255), nullable=False)
    knowledge_type: Mapped[str] = mapped_column(String(40), default="fact", nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text)

    keywords_json: Mapped[list | None] = mapped_column(JSON)
    entities_json: Mapped[list | None] = mapped_column(JSON)
    relationships_json: Mapped[list | None] = mapped_column(JSON)

    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    semantic_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="SET NULL")
    )
    outline_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_outline_nodes.id", ondelete="SET NULL"), index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer)
    slide_number: Mapped[int | None] = mapped_column(Integer)
    block_id: Mapped[str | None] = mapped_column(String(100))

    source_segment_ids_json: Mapped[list | None] = mapped_column(JSON)
    source_media_ids_json: Mapped[list | None] = mapped_column(JSON)
    embedding_json: Mapped[list | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class KnowledgeQuestionRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Database record for pre-existing questions extracted directly from documents."""

    __tablename__ = "knowledge_question_records"
    __table_args__ = (
        Index("ix_kq_records_course", "course_id"),
        Index("ix_kq_records_lesson", "lesson_id"),
        Index("ix_kq_records_source", "source_id"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="SET NULL"), index=True
    )
    outline_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_outline_nodes.id", ondelete="SET NULL"), index=True
    )

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    question_type: Mapped[str] = mapped_column(String(30), default="multiple_choice", nullable=False)
    options_json: Mapped[list | None] = mapped_column(JSON)
    correct_answer: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)

    page_number: Mapped[int | None] = mapped_column(Integer)
    slide_number: Mapped[int | None] = mapped_column(Integer)
    image_asset_ids_json: Mapped[list | None] = mapped_column(JSON)
    raw_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    classification_confidence: Mapped[str] = mapped_column(String(20), default="high", nullable=False)  # high, uncertain
    needs_answer_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class KnowledgeQuestionImageLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Verified relationship between one extracted question and one source image."""

    __tablename__ = "knowledge_question_image_links"
    __table_args__ = (
        UniqueConstraint("question_record_id", "asset_id", name="uq_knowledge_question_image_link"),
        Index("ix_knowledge_question_image_links_question", "question_record_id", "position"),
    )

    question_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_question_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_assets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)  # explicit_reference|visual_context|textual_match
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_json: Mapped[dict | None] = mapped_column(JSON)


class AssessmentSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Source container for uploaded/imported quizzes, exams, and homework."""

    __tablename__ = "assessment_sources"

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assessment_type: Mapped[str] = mapped_column(String(30), default="quiz", nullable=False)  # quiz, exam, homework, bank
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(30), default="resolving", nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="needs_review", nullable=False)
    answer_key_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="SET NULL"), index=True
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class AssessmentQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Individual questions extracted from assessment sources (Question Bank)."""

    __tablename__ = "assessment_questions"
    __table_args__ = (
        Index("ix_assessment_questions_source", "assessment_source_id"),
        Index("ix_assessment_questions_course", "course_id"),
        Index("ix_assessment_questions_norm_hash", "normalized_hash"),
    )

    assessment_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    outline_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_outline_nodes.id", ondelete="SET NULL"), index=True
    )

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(30), default="multiple_choice", nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    learning_objective: Mapped[str] = mapped_column(String(100), default="understanding", nullable=False)
    topic_concept: Mapped[str] = mapped_column(String(255), nullable=False)
    points: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(30), default="extracted_question", nullable=False)

    correct_answer: Mapped[str | None] = mapped_column(Text)
    answer_source: Mapped[str | None] = mapped_column(String(40))
    answer_status: Mapped[str] = mapped_column(String(40), default="needs_review", nullable=False)
    answer_provenance_json: Mapped[dict | None] = mapped_column(JSON)
    options_json: Mapped[list | None] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    source_pages_json: Mapped[list | None] = mapped_column(JSON)
    rubric_json: Mapped[dict | None] = mapped_column(JSON)
    media_ids_json: Mapped[list | None] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(30), default="needs_review", nullable=False)

    normalized_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    semantic_fingerprint: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class AssessmentQuestionUsage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks historical usage of questions in generated quizzes & assignments to prevent duplicates."""

    __tablename__ = "assessment_question_usages"
    __table_args__ = (
        Index("ix_question_usages_question", "question_id"),
        Index("ix_question_usages_course", "course_id"),
    )

    question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_questions.id", ondelete="SET NULL"), index=True
    )
    quiz_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quizzes.id", ondelete="SET NULL"), index=True
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL"), index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )

    usage_context: Mapped[str] = mapped_column(String(50), default="quiz_generation", nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
