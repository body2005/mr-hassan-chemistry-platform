from __future__ import annotations

import os
from pathlib import Path
import pytest
from sqlalchemy import select

from app.models.course import Course, CourseStatus
from app.models.institution import Institution
from app.models.knowledge_center import (
    AssessmentSource,
    KnowledgeQuestionRecord,
    KnowledgeSource,
    SourceRole,
    SourceStatus,
)
from app.models.user import User, UserRole
from app.services.document_parsers import (
    normalize_arabic_presentation_forms,
    parse_pdf_document,
)
from app.services.exam_processing import (
    _extract_question_number,
    materialize_assessment_questions,
    split_assessment_question_blocks,
)
from app.services.knowledge_center_service import (
    assemble_document_questions,
    create_knowledge_source,
    process_knowledge_source,
)

PDF_REAL_PATH = (
    Path(__file__).parent.parent
    / "storage"
    / "knowledge_center"
    / "courses"
    / "85a134ed-9182-4ce7-ba5b-36955be3bbdf"
    / "7d1b3d88_049fd658-0ccc-4840-b2b4-2335cfd5b0ec.pdf"
)


def test_real_exam_pdf_parsing_and_assembly():
    assert PDF_REAL_PATH.exists(), f"Real exam PDF missing at {PDF_REAL_PATH}"

    parsed_doc = parse_pdf_document(file_path=str(PDF_REAL_PATH))
    assert parsed_doc.total_pages == 4
    # PyMuPDF extracts directly so OCR is not needed for this PDF
    assert not parsed_doc.extracted_via_ocr

    questions = assemble_document_questions(parsed_doc)
    assert len(questions) == 14, f"Expected 14 questions, got {len(questions)}"

    # 1. Verify 12 MCQs
    for i in range(12):
        q = questions[i]
        assert q["question_type"] == "MCQ", f"Question {i+1} should be MCQ, got {q['question_type']}"
        assert q["options"] is not None, f"Question {i+1} options are None"
        opt_keys = [opt["key"] for opt in q["options"]]
        assert opt_keys == ["أ", "ب", "ج", "د"], f"Question {i+1} options should be [أ, ب, ج, د], got {opt_keys}"

    # 2. Verify Question 1 has no admin metadata header leaked
    q1 = questions[0]
    assert "وزارة التربية" not in q1["question_text"]
    assert "الدرجة العظمى" not in q1["question_text"]
    assert "عنصر انتقالي رئيسي" in q1["question_text"]

    # 3. Verify Question 2 preserved compound (B) without confusing it with option (ب)
    q2 = questions[1]
    assert "أكسالات الحديد الثنائي" in q2["question_text"]
    assert len(q2["options"]) == 4

    # 4. Verify chemical formulas preserved
    q5 = questions[4]
    assert "N2(g) + 3H2(g) ⇌ 2NH3(g)" in q5["question_text"]

    q14 = questions[13]
    assert "Fe²⁺" in q14["question_text"]

    # 5. Verify Essay questions (Q13 and Q14)
    q13 = questions[12]
    assert q13["question_type"] == "ESSAY"
    assert "السؤال الأول" in q13["question_text"]
    assert "مبتدئًا بالميثان" in q13["question_text"]
    assert "الجاماكسان" in q13["question_text"]

    assert q14["question_type"] == "ESSAY"
    assert "السؤال الثاني" in q14["question_text"]
    # All 3 sub-questions must be present
    assert "احسب القوة الدافعة الكهربية للخلية" in q14["question_text"]
    assert "هل يصدر عن هذه الخلية تيار كهربي تلقائي" in q14["question_text"]
    assert "حدد اتجاه سريان الإلكترونات" in q14["question_text"]


def test_typo_correction_and_boundary_decimals():
    # 1. Typo correction
    raw_sample = "فلز الأومنيوم يتفاعل مع كلوريد أومنيوم"
    cleaned = normalize_arabic_presentation_forms(raw_sample)
    assert "الألومنيوم" in cleaned
    assert "ألومنيوم" in cleaned
    assert "الأومنيوم" not in cleaned

    # 2. Negative lookahead on decimal numbers (0.5, 4.5)
    sample_text = """
1. السؤال الأول:
عينة كتلتها 0.5 g تفاعلت مع 0.25 mol/L حمض.
2. السؤال الثاني:
عند إمرار 4.5 A تيار كهربي ترسب 0.5 Faraday.
"""
    blocks = split_assessment_question_blocks(sample_text)
    assert len(blocks) == 2, f"Expected 2 blocks, got {len(blocks)}"

    # 3. Arabic ordinals extraction
    assert _extract_question_number("السؤال الأول: وضح الآتي") == "1"
    assert _extract_question_number("السؤال الثاني: احسب ما يلي") == "2"
    assert _extract_question_number("سؤال 10: اختر") == "10"


def test_real_exam_end_to_end_ingestion(db):
    inst = Institution(name="Exam Inst", slug="exam-inst")
    db.add(inst)
    db.flush()

    teacher = User(
        institution_id=inst.id,
        username="exam-teacher",
        email="exam-teacher@example.com",
        password_hash="hash",
        display_name="Exam Teacher",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.flush()

    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="CHEM-EXAM-101",
        title="Thanaweya Chemistry",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.flush()

    with open(PDF_REAL_PATH, "rb") as f:
        pdf_bytes = f.read()

    source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        file_bytes=pdf_bytes,
        filename="7d1b3d88_049fd658-0ccc-4840-b2b4-2335cfd5b0ec.pdf",
        source_role=SourceRole.ASSESSMENT,
    )
    db.commit()

    processed_source = process_knowledge_source(db=db, source_id=source.id)
    assert processed_source.status in ("indexed", SourceStatus.INDEXED)

    q_records = db.scalars(
        select(KnowledgeQuestionRecord)
        .where(KnowledgeQuestionRecord.source_id == source.id)
        .order_by(KnowledgeQuestionRecord.question_order.asc())
    ).all()

    assert len(q_records) == 14, f"Expected 14 records in DB, found {len(q_records)}"

    # Materialize assessment
    assessment = materialize_assessment_questions(
        db=db,
        source=processed_source,
        assessment_type="exam",
    )
    assert assessment.total_questions == 14
