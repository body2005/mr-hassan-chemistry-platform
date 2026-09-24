# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import pytest
from app.services.document_parsers import (
    is_text_garbled,
    ocr_pdf_page,
    parse_pdf_document,
)


def test_is_text_garbled_detection():
    # 1. Exact user-reported mojibake lines from broken typesetting font
    mojibake_sample = """cR ÚeCG øjódG ΩÉüY (الصفحة 1)
ΩƒdG QÉûàùe Öàµe øjóàdGh (الصفحة 1)
ûjhQO ºµG óÑY ΩÉûg (الصفحة 1)"""
    assert is_text_garbled(mojibake_sample) is True

    # 2. CID font tokens (missing ToUnicode CMap in PDF)
    cid_sample = """(cid:103)(cid:164)(cid:43)(cid:121)(cid:135)(cid:71)(cid:42)(cid:3)(cid:121)(cid:127)(cid:125)(cid:72)(cid:3)(cid:103)(cid:77)(cid:52)(cid:162)(cid:159)(cid:153)(cid:47)
(cid:3) (cid:1010)(cid:999)(cid:980)(cid:991)(cid:909)(cid:3)(cid:993)(cid:1011)(cid:992)(cid:972)(cid:919)(cid:991)(cid:909)"""
    assert is_text_garbled(cid_sample) is True

    # 3. Reversed Arabic (visual order instead of logical RTL order)
    reversed_arabic_sample = "ةثيثلحا دوهجلل لاامكتساو ةيللمحاو ةيلماعلا تاريغتلما ةبكاولم ميلعتلا ريوطت راطإ ىف"
    assert is_text_garbled(reversed_arabic_sample) is True

    # 4. Direct Presentation Form glyph dump
    pres_forms_sample = "دردنا تﺔسﻋ ﺎيﺒﻄاهﻠﻟ ﻦعبﻤاﺣطﺮمﻟا راد"
    assert is_text_garbled(pres_forms_sample) is True

    # 5. Normal Arabic content (must NOT be flagged as garbled)
    normal_arabic = "تعتبر الجيولوجيا علم الأرض الذي يبحث في كل ما له علاقة بالأرض ومكوناتها وحركاتها وتاريخها وظواهرها الطبيعية."
    assert is_text_garbled(normal_arabic) is False

    # 6. Normal English content (must NOT be flagged as garbled)
    normal_english = "Geology is the study of the Earth, the materials of which it is made, the structure of those materials, and the processes acting upon them."
    assert is_text_garbled(normal_english) is False

    # 7. Normal mixed Arabic/English
    normal_mixed = "علم الجيولوجيا أو Geology هو علم دراسة الأرض والصخور والظواهر الطبيعية."
    assert is_text_garbled(normal_mixed) is False

    # 8. Very short or whitespace-only text
    assert is_text_garbled("") is False
    assert is_text_garbled("   ") is False
    assert is_text_garbled("short") is False



def test_ocr_page_extraction_on_real_geology_textbook():
    pdf_path = os.path.join(
        "storage", "knowledge_center", "courses",
        "85a134ed-9182-4ce7-ba5b-36955be3bbdf",
        "f456c273_كتاب الوزارة جيولوجيا تالتة ثانوي.pdf"
    )
    if not os.path.exists(pdf_path):
        pytest.skip("Textbook PDF not found in local storage")

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    # Extract OCR from Page 1 with bilingual lang='ara+eng'
    ocr_text = ocr_pdf_page(file_bytes, page_number=1, lang="ara+eng")
    assert len(ocr_text) > 50

    # Ensure valid Arabic words are extracted
    assert any(w in ocr_text for w in ["الجيولوجيا", "مصر", "التربية", "التعليم", "الكتاب"])
    # Ensure no CID font codes remain in the OCR output
    assert "(cid:" not in ocr_text


def test_garbling_triggers_ocr_in_parse_pdf_document(monkeypatch):
    from unittest.mock import MagicMock
    import pdfplumber

    fake_bytes = b"%PDF-1.4 mock pdf content"

    # Mock pdfplumber page with garbled text
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "cR ÚeCG øjódG ΩÉüY (cid:103)(cid:164) (cid:101)"
    mock_page.extract_tables.return_value = []
    mock_page.images = []

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf

    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: mock_pdf)
    monkeypatch.setattr(
        "app.services.document_parsers.ocr_pdf_page",
        lambda *args, **kwargs: "الجيولوجيا والعلوم البيئية للصف الثالث الثانوي"
    )

    doc = parse_pdf_document(fake_bytes, "broken_textbook.pdf")
    assert doc.extracted_via_ocr is True
    assert 1 in doc.ocr_pages
    assert "الجيولوجيا" in doc.pages[0].raw_text
    assert doc.metadata.get("extracted_via_ocr") is True


def test_parse_pdf_document_with_images_handles_bbox(monkeypatch):
    from unittest.mock import MagicMock
    import pdfplumber

    fake_bytes = b"%PDF-1.4 mock pdf content"

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "محتوى الصفحة التجريبي للدرس الأول"
    mock_page.extract_tables.return_value = []
    mock_page.images = [{"width": 100, "height": 100}]

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf

    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: mock_pdf)
    monkeypatch.setattr(
        "app.services.document_parsers.extract_pdf_page_images",
        lambda *args, **kwargs: [(b"fake_image_bytes_here" * 200, 120, 120, [10.0, 20.0, 130.0, 140.0])]
    )
    monkeypatch.setattr(
        "app.services.document_parsers.ocr_image_bytes",
        lambda *args, **kwargs: ("نص داخل الصورة", "test-engine")
    )

    doc = parse_pdf_document(fake_bytes, "book_with_images.pdf")
    assert len(doc.all_images) == 1
    assert doc.all_images[0].bbox == [10.0, 20.0, 130.0, 140.0]
    assert doc.all_images[0].ocr_text == "نص داخل الصورة"


def test_parse_pdf_document_passes_local_path_to_image_extractor(monkeypatch, tmp_path):
    """Image extraction must work for staged files, not only uploaded bytes."""
    from unittest.mock import MagicMock
    import pdfplumber

    staged_pdf = tmp_path / "staged.pdf"
    staged_pdf.write_bytes(b"%PDF-1.4 mock pdf content")
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "نص صالح للاختبار"
    mock_page.extract_tables.return_value = []
    mock_page.images = [{"width": 100, "height": 100}]
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: mock_pdf)

    received: dict[str, object] = {}

    def fake_extract(file_bytes, page_number, *, file_path=None):
        received.update(file_bytes=file_bytes, page_number=page_number, file_path=file_path)
        return []

    monkeypatch.setattr("app.services.document_parsers.extract_pdf_page_images", fake_extract)
    parse_pdf_document(file_path=str(staged_pdf), filename="staged.pdf")

    assert received == {
        "file_bytes": None,
        "page_number": 1,
        "file_path": str(staged_pdf),
    }


def test_pymupdf_page_raster_rendering_available(tmp_path):
    """PyMuPDF can rasterize a PDF page to a real JPEG (extraction OCR path)."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    pdf_path = tmp_path / "page.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "PDF page render")
    document.save(str(pdf_path))
    document.close()

    with fitz.open(str(pdf_path)) as doc:
        pix = doc[0].get_pixmap(dpi=120)
        rendered = pix.tobytes("jpeg")

    assert rendered is not None
    assert rendered.startswith(bytes([0xFF, 0xD8]))

