"""Regression suite over the blind science-exam fixtures (tests/fixtures/blind_inputs).

These are unseen-by-design files, copied verbatim into fixtures, covering:
text-layer PDFs (incl. Arabic presentation forms + two-column layout),
an image-only PDF (OCR path), and a negative case (summary with no questions).

The contract enforced here is *structural only*: counts, per-file type
sequences, and the review flags for OCR-backed pages.  No question text is
pinned by keyword; new files must yield new questions from their own content.
"""
import os

import pytest

from app.services.document_parsers import parse_pdf_document
from app.services.exam_text_extractor import segment_exam_document

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "blind_inputs")

# Per-file structural contract: question count and expected type sequence.
# (Count + type order only; stems are never pinned by content keywords.)
EXPECTED = {
    "01_physics_text_pdf.pdf": ["MCQ"] * 4 + ["TRUE_FALSE"] * 3 + ["FILL_BLANK"] * 3 + ["ESSAY"] * 2,
    "02_mathematics_two_columns_pdf.pdf": ["MCQ"] * 4 + ["TRUE_FALSE"] * 2 + ["FILL_BLANK"] * 2 + ["ESSAY"] * 2,
    "03_geology_text_pdf.pdf": ["MCQ"] * 3 + ["TRUE_FALSE"] * 2 + ["FILL_BLANK"] * 3 + ["ESSAY"] * 2,
    "04_integrated_science_text_pdf.pdf": ["MCQ"] * 3 + ["TRUE_FALSE"] * 3 + ["FILL_BLANK"] * 3 + ["ESSAY"] * 3,
    "05_biology_image_only_pdf.pdf": ["MCQ"] * 3 + ["TRUE_FALSE"] * 2 + ["FILL_BLANK"] * 2 + ["ESSAY"] * 3,
    "06_no_questions_negative_pdf.pdf": [],
}


def _extract(fname: str):
    path = os.path.join(FIXTURES_DIR, fname)
    with open(path, "rb") as f:
        doc = parse_pdf_document(f.read(), "application/pdf", fname)
    return doc, segment_exam_document(doc, filename=fname)


@pytest.mark.parametrize("fname", sorted(EXPECTED.keys()))
def test_question_count_and_type_sequence(fname: str) -> None:
    _doc, questions = _extract(fname)
    assert [q["canonical_type"] for q in questions] == EXPECTED[fname], (
        f"{fname}: type sequence mismatch"
    )


def test_physics_presentation_forms_use_text_layer_not_ocr() -> None:
    """Arabic presentation forms (U+FBxx/FExx) in the text layer are legitimate
    glyphs: the garble check must measure on NFKC, so the page must NOT fall
    back to OCR (which produced glad/Vaso/Gaurd artifacts historically)."""
    doc, questions = _extract("01_physics_text_pdf.pdf")
    assert doc.ocr_pages == []
    assert all(q["text_source"] == "text_layer" for q in questions)
    # Sanity: every question must be readable Arabic (no Latin OCR debris).
    for q in questions:
        assert "glad" not in q["question_text"]
        assert "Gaurd" not in q["question_text"]


def test_two_column_mathematics_splits_right_then_left() -> None:
    """The gutter detector must split the two-column sheet into its full
    ordered question set (1..10), never a single merged MCQ."""
    _doc, questions = _extract("02_mathematics_two_columns_pdf.pdf")
    assert len(questions) == 10
    mcqs = [q for q in questions if q["canonical_type"] == "MCQ"]
    assert len(mcqs) == 4
    assert all(len(q["options"] or []) == 4 for q in mcqs)


def test_end_of_paper_trailer_never_enters_a_stem() -> None:
    """'انتهت الورقة' must close the paper (block boundary) and never leak
    into any question stem - historically it glued onto the last essay."""
    for fname in sorted(EXPECTED.keys()):
        _doc, questions = _extract(fname)
        for q in questions:
            assert "انتهت الورقة" not in q["question_text"], f"{fname}: trailer leaked into a stem"


def test_negative_summary_yields_zero_questions() -> None:
    _doc, questions = _extract("06_no_questions_negative_pdf.pdf")
    assert questions == []


def test_ocr_pages_marked_for_content_review() -> None:
    """Every question sourced from an OCR-backed page carries
    text_source='ocr' and needs_content_review=True: unreadable OCR output
    surfaces for teacher review instead of being silently trusted."""
    doc, questions = _extract("05_biology_image_only_pdf.pdf")
    assert set(doc.ocr_pages) == {1, 2}
    assert questions
    assert all(q["text_source"] == "ocr" for q in questions)
    assert all(q["needs_content_review"] is True for q in questions)


def test_text_layer_pages_not_flagged_for_content_review() -> None:
    for fname in [
        "01_physics_text_pdf.pdf",
        "02_mathematics_two_columns_pdf.pdf",
        "03_geology_text_pdf.pdf",
        "04_integrated_science_text_pdf.pdf",
    ]:
        _doc, questions = _extract(fname)
        assert questions
        assert all(
            q["text_source"] == "text_layer" and q["needs_content_review"] is False
            for q in questions
        ), f"{fname}: text-layer questions must not need content review"


def test_tf_questions_without_printed_options_have_no_synthesized_options() -> None:
    """Papers print no option rows for judge statements; the extractor must
    not fabricate صح/خطأ options for them (no invented answer model)."""
    _doc, questions = _extract("03_geology_text_pdf.pdf")
    tf = [q for q in questions if q["canonical_type"] == "TRUE_FALSE"]
    assert len(tf) == 2
    assert all(q["options"] in (None, []) for q in tf)
