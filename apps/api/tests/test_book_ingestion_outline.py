from __future__ import annotations

import io

from PIL import Image
from sqlalchemy import select

from app.models.course import Course, CourseStatus
from app.models.institution import Institution
from app.models.knowledge_center import KnowledgeOutlineNode, KnowledgeUnitRecord
from app.models.user import User, UserRole
from app.services import document_parsers
from app.services.knowledge_center_service import create_knowledge_source, process_knowledge_source


def test_image_source_keeps_ocr_text_as_searchable_page_content(monkeypatch) -> None:
    image = Image.new("RGB", (40, 40), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    monkeypatch.setattr(
        document_parsers,
        "ocr_image_bytes",
        lambda _: ("القيمة المكتوبة داخل الرسم هي 25", "test-ocr"),
    )

    parsed = document_parsers.parse_image_asset(buffer.getvalue(), "diagram.png")

    assert parsed.pages[0].raw_text == "القيمة المكتوبة داخل الرسم هي 25"
    assert parsed.all_images[0].ocr_text == "القيمة المكتوبة داخل الرسم هي 25"
    assert parsed.all_images[0].ocr_engine == "test-ocr"


def test_book_outline_links_content_to_most_specific_heading(db) -> None:
    institution = Institution(name="Outline School", slug="outline-school")
    db.add(institution)
    db.flush()
    teacher = User(
        institution_id=institution.id,
        username="outline-teacher",
        email="outline@example.com",
        password_hash="hash",
        display_name="Outline Teacher",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.flush()
    course = Course(
        institution_id=institution.id,
        teacher_id=teacher.id,
        code="BIO-OUTLINE",
        title="Biology Outline",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.commit()
    source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        filename="biology_book.md",
        file_bytes=(
            "# الوحدة الأولى: الخلية\n"
            "## الدرس الأول: البناء والوظيفة\n"
            "### الغشاء البلازمي\n"
            "الغشاء البلازمي ينظم مرور المواد إلى الخلية وخارجها.\n"
        ).encode("utf-8"),
    )

    process_knowledge_source(db, source.id)

    nodes = db.scalars(
        select(KnowledgeOutlineNode)
        .where(KnowledgeOutlineNode.source_id == source.id)
        .order_by(KnowledgeOutlineNode.position)
    ).all()
    units = db.scalars(
        select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source.id)
    ).all()

    assert any(node.node_kind == "unit" for node in nodes)
    assert any(node.node_kind == "lesson" for node in nodes)
    assert any(node.node_kind == "topic" for node in nodes)
    assert any(unit.outline_node_id for unit in units)
