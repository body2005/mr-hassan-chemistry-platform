"""
=============================================================================
AI TEACHING KNOWLEDGE CENTER — DOCUMENT & MEDIA PARSERS
=============================================================================
Structure-preserving parsers for PDF, DOCX, PPTX, TXT/Markdown, Images, and Assessment Banks.
Preserves page numbers, slide numbers, headings, tables, figures, embedded images, and captions.
=============================================================================
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


@dataclass
class ParsedImage:
    """An image extracted from a document or uploaded asset."""
    id: str
    page_number: int | None = None
    slide_number: int | None = None
    asset_kind: str = "figure"  # diagram, chart, figure, map, question_image, formula, illustration
    caption: str | None = None
    surrounding_text: str | None = None
    image_bytes: bytes | None = None
    storage_path: str | None = None
    width: int | None = None
    height: int | None = None
    checksum: str = ""
    ocr_text: str | None = None
    ocr_engine: str | None = None
    bbox: list[float] | None = None
    role: str = "unknown"  # question_attachment, question_reference, supporting_visual, decorative, unknown


@dataclass
class ParsedTable:
    """A table extracted from a document."""
    page_number: int | None = None
    slide_number: int | None = None
    caption: str | None = None
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class ParsedBlock:
    """A text block within a page/slide."""
    block_id: str
    block_type: str  # heading, paragraph, list, table, note, code
    text: str
    level: int = 1  # heading level or list depth
    page_number: int | None = None
    slide_number: int | None = None
    media_ids: list[str] = field(default_factory=list)


@dataclass
class ParsedPage:
    """A page or slide within a document."""
    page_number: int | None = None
    slide_number: int | None = None
    title: str | None = None
    blocks: list[ParsedBlock] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    images: list[ParsedImage] = field(default_factory=list)
    raw_text: str = ""
    extracted_via_ocr: bool = False


@dataclass
class ParsedDocument:
    """Complete structured representation of an ingested document."""
    title: str
    author: str | None = None
    doc_type: str = "document"  # pdf, docx, pptx, txt, md, image, assessment
    total_pages: int = 1
    total_slides: int = 0
    pages: list[ParsedPage] = field(default_factory=list)
    all_tables: list[ParsedTable] = field(default_factory=list)
    all_images: list[ParsedImage] = field(default_factory=list)
    hierarchy: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    extracted_via_ocr: bool = False
    ocr_pages: list[int] = field(default_factory=list)



@dataclass
class ParsedAssessmentQuestion:
    """A question extracted from a previous quiz, exam, or homework bank."""
    question_text: str
    question_type: str  # multiple_choice, true_false, essay, fill_in_blank, ordering
    difficulty: str = "medium"
    learning_objective: str = "understanding"
    topic_concept: str = "عام"
    correct_answer: str | None = None
    options: list[dict[str, Any]] = field(default_factory=list)
    explanation: str | None = None
    media_ids: list[str] = field(default_factory=list)
    raw_text: str = ""


def is_chemical_equation_line(text: str) -> bool:
    """Detects if a line looks like a chemical equation or reaction formula."""
    t = text.strip()
    if not t or len(t) < 3:
        return False
    has_arrow = any(a in t for a in ["->", "→", "<=>", "⇌", "—>"])
    has_math_or_chem = any(sym in t for sym in ["+", "="])
    has_known_chem_tokens = bool(re.search(r"\b(?:HCl|NaOH|NaCl|H2O|Zn|ZnCl2|H2|CaCO3|CO2|O2|H2SO4|CuSO4|NH3|CH4|Fe|AgNO3|Cu|Al|FeCl3|Fe2O3|BaCl2|Na2SO4)\b", t))
    has_formula_pattern = bool(re.search(r"^[A-Z][a-z]?\d*(?:\s*[\+\=]\s*[A-Z][a-z]?\d*)+", t))
    return (has_arrow and (has_math_or_chem or has_known_chem_tokens)) or (has_known_chem_tokens and (has_arrow or has_math_or_chem)) or has_formula_pattern


def is_text_garbled(text: str) -> bool:
    """
    Detects whether extracted PDF text is garbled, corrupt, or mojibake.
    Common with legacy Arabic typesetting PDFs that lack proper ToUnicode CMaps,
    resulting in CID tokens (e.g. `(cid:103)`) or arbitrary Latin/Greek glyph mappings.
    """
    if not text or len(text.strip()) < 10:
        return False

    # Check 1: CID font tokens (e.g. (cid:103)(cid:164)...)
    cid_matches = len(re.findall(r'\(cid:\d+\)', text))
    if cid_matches >= 3:
        return True

    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return False
    total_non_ws = len(non_ws)

    std_arabic_chars = sum(1 for c in non_ws if '\u0600' <= c <= '\u06FF')
    pres_arabic_chars = sum(1 for c in non_ws if '\uFB50' <= c <= '\uFDFF' or '\uFE70' <= c <= '\uFEFF')
    all_arabic_chars = sum(
        1 for c in non_ws
        if ('\u0600' <= c <= '\u06FF' or
            '\u0750' <= c <= '\u077F' or
            '\u08A0' <= c <= '\u08FF' or
            '\uFB50' <= c <= '\uFDFF' or
            '\uFE70' <= c <= '\uFEFF')
    )
    arabic_ratio = all_arabic_chars / total_non_ws
    std_arabic_ratio = std_arabic_chars / total_non_ws
    pres_arabic_ratio = pres_arabic_chars / total_non_ws

    # Check 2: High density of mojibake glyphs common in broken Arabic font encodings
    # (Greek math symbols like Ω, accented Latin-1 high-bytes like É, ü, ø, ó, Ñ, º, Ú, û, µ)
    mojibake_chars = sum(
        1 for c in non_ws
        if c in 'ΩµÉüøóÑºÚûô§±×÷°¿¡¢£¤¥©®¶' or ('\u00C0' <= c <= '\u00FF') or ('\u0370' <= c <= '\u03FF')
    )
    mojibake_ratio = mojibake_chars / total_non_ws
    if mojibake_ratio > 0.05 and std_arabic_ratio < 0.40:
        return True

    # Check 3: Broken font presentation form glyphs dumped directly instead of logical Unicode
    if pres_arabic_ratio > 0.20:
        return True

    words = [w.strip('.,()!?[]:\"\'') for w in text.split()]
    words = [w for w in words if w]
    if len(words) > 5:
        # Check 4: Mixed fragmented non-words (single Latin letters separated by spaces e.g. 'c R Ú e C G')
        single_char_words = sum(1 for w in words if len(w) == 1 and w.isascii())
        if (single_char_words / len(words)) > 0.35 and arabic_ratio < 0.30:
            return True

        # Check 5: Reversed Arabic (visual order instead of logical order)
        # In Arabic grammar, words NEVER begin with Taa Marbuta (ة or presentation variants).
        taa_marbuta_starts = sum(1 for w in words if w.startswith(('ة', '\ufe93', '\ufe94')))
        if taa_marbuta_starts >= 2:
            return True

        # Definite article (الـ) is ALWAYS a prefix in Arabic; in reversed text it becomes a suffix (لا).
        rev_alif_lam = sum(1 for w in words if w.endswith(('لا', 'لآ', 'لأ', 'لإ')))
        if (rev_alif_lam / len(words)) > 0.12 and taa_marbuta_starts >= 1:
            return True

    return False


BIDI_CHARS_RE = re.compile(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]')

OCR_ARABIC_CONFUSIONS = [
    # Tesseract ara+eng glyph confusions inside Arabic context
    (r'(^|[\u0600-\u06FF\s])of(?=[\u0600-\u06FF\s]|$)', r'\g<1>أو'),
    (r'(^|[\u0600-\u06FF\s])ale(?=[\u0600-\u06FF\s]|$)', r'\g<1>علم'),
    (r'(^|[\u0600-\u06FF\s])Jol(?=[\u0600-\u06FF\s]|$)', r'\g<1>أول'),
    (r'(^|[\u0600-\u06FF\s])wi(?=[\u0600-\u06FF\s]|$)', r'\g<1>أو'),
    (r'(^|[\u0600-\u06FF\s])to(?=[\u0600-\u06FF\s]|$)', r'\g<1>إلى'),
    (r'(^|[\u0600-\u06FF\s])in(?=[\u0600-\u06FF\s]|$)', r'\g<1>في'),
    (r'(^|[\u0600-\u06FF\s])and(?=[\u0600-\u06FF\s]|$)', r'\g<1>و'),
    (r'(^|[\u0600-\u06FF\s])fae(?=[\u0600-\u06FF\s]|$)', r'\g<1>فهي'),
    (r'(^|[\u0600-\u06FF\s])bol(?=[\u0600-\u06FF\s]|$)', r'\g<1>بل'),
    (r'(^|[\u0600-\u06FF\s])Bale(?=[\u0600-\u06FF\s]|$)', r'\g<1>حادة'),
    (r'(^|[\u0600-\u06FF\s])Cob(?=[\u0600-\u06FF\s]|$)', r'\g<1>فوق'),
    (r'(^|[\u0600-\u06FF\s])dab Fi(?=[\u0600-\u06FF\s]|$)', r'\g<1>في هذا'),
    (r'(^|[\u0600-\u06FF\s])أنحديد(?=[\u0600-\u06FF\s]|$)', r'\g<1>الحديد'),
    (r'(^|[\u0600-\u06FF\s])انحديد(?=[\u0600-\u06FF\s]|$)', r'\g<1>الحديد'),
]


def is_reversed_arabic_token(w: str) -> bool:
    w = w.strip('.,()!?[]:"\'')
    if not w or len(w) < 2:
        return False
    if w.startswith(('ة', '\ufe93', '\ufe94')):
        return True
    if w.endswith(('لا', 'لآ', 'لأ', 'لإ')) and w not in ('لا', 'إلا', 'كلا', 'لولا', 'علا', 'هلا', 'جلا'):
        return True
    if w.endswith(('لحا', 'لخا', 'لجا')):
        return True
    if w in ('نزولل', 'رصنعلا', 'ديدلحا', 'ينجسكلأا', 'ةدلاصلا', 'ندعلما', 'تاكيليسلا', 'تانوبركلا'):
        return True
    return False


def is_reversed_arabic(text: str) -> bool:
    if not text:
        return False
    words = text.split()
    if not words:
        return False
    return any(is_reversed_arabic_token(w) for w in words)


def fix_reversed_arabic_text(text: str) -> str:
    """
    Detects and fixes visual-order reversed Arabic text commonly found in legacy PDF font streams.
    Reverses words within lines, reverses characters in Arabic tokens, and normalizes standard Arabic ligatures.
    """
    if not text:
        return ""
    if not is_reversed_arabic(text):
        return text

    lines = text.split("\n")
    fixed_lines = []
    for line in lines:
        words = line.split()
        if not words:
            fixed_lines.append("")
            continue

        has_arabic = any(any('\u0600' <= c <= '\u06FF' or '\uFB50' <= c <= '\uFEFF' for c in w) for w in words)
        if not has_arabic:
            fixed_lines.append(line)
            continue

        fixed_words = []
        for w in reversed(words):
            if any('\u0600' <= c <= '\u06FF' or '\uFB50' <= c <= '\uFEFF' for c in w):
                rw = w[::-1]
                # Fix reversed lam-alif ligatures
                rw = rw.replace('لإ', 'إل').replace('لأ', 'أل').replace('لآ', 'آل')
                rw = re.sub(r'^امل', 'الم', rw)
                rw = re.sub(r'^األ', 'الأ', rw)
                rw = re.sub(r'^اإل', 'الإ', rw)
                rw = re.sub(r'^اآل', 'الآ', rw)
                rw = re.sub(r'^احل', 'الح', rw)
                rw = re.sub(r'^اخل', 'الخ', rw)
                rw = re.sub(r'^اجم', 'المج', rw)
                rw = re.sub(r'ني$', 'ين', rw)
                fixed_words.append(rw)
            else:
                fixed_words.append(w)
        fixed_lines.append(" ".join(fixed_words))
    return "\n".join(fixed_lines)


def is_valid_data_table(headers: list[str], rows: list[list[str]]) -> tuple[bool, str]:
    """
    Validates whether an extracted table structure is a genuine data table (multi-row / multi-col tabular data)
    or just a narrative callout box, sidebar, decorative page border, or single paragraph surrounded by lines.
    """
    all_rows = ([headers] if headers else []) + (rows or [])
    cells = [str(c).strip() for r in all_rows for c in r if c and str(c).strip()]
    if len(cells) < 2:
        return False, "Fewer than 2 non-empty cells (layout box or empty border)"

    num_rows = len(all_rows)
    num_cols = max(len(r) for r in all_rows) if all_rows else 0
    if num_rows <= 1 and num_cols <= 1:
        return False, "Single cell box"

    word_counts = [len(c.split()) for c in cells]
    max_words = max(word_counts)
    avg_words = sum(word_counts) / len(word_counts)

    # Real data tables have concise cell entries. If a cell contains paragraphs (> 35 words)
    # or the average cell is > 25 words, it's a narrative callout box, not a data table.
    if max_words > 35 or avg_words > 25:
        return False, f"Narrative text box (max_words={max_words}, avg_words={avg_words:.1f})"

    return True, f"Valid table ({num_rows}x{num_cols})"


def clean_arabic_ocr_text(text: str) -> str:
    """Cleans OCR artifacts, removes rogue Unicode BiDi isolation marks, and context-aware fixes for Tesseract confusions."""
    if not text:
        return ""
    cleaned = BIDI_CHARS_RE.sub('', text)
    # Only apply Arabic substitutions if text has an Arabic context to avoid corrupting English words (e.g. 'of', 'in', 'to')
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', text))
    if has_arabic:
        for pat, rep in OCR_ARABIC_CONFUSIONS:
            cleaned = re.sub(pat, rep, cleaned)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    return cleaned.strip()


def ocr_pdf_page(file_bytes: bytes | None = None, page_number: int = 1, lang: str = "ara+eng", pdfium_doc: Any = None, file_path: str | None = None) -> str:
    """
    Renders a specific PDF page to an image and performs OCR using Tesseract.
    Uses disk caching to prevent re-running OCR on previously processed pages.
    """
    cache_file = None
    try:
        if file_bytes:
            file_hash = hashlib.sha256(file_bytes[:100000] + str(len(file_bytes)).encode()).hexdigest()[:16]
        elif file_path and os.path.exists(file_path):
            file_hash = hashlib.sha256(os.path.basename(file_path).encode() + str(os.path.getsize(file_path)).encode()).hexdigest()[:16]
        else:
            file_hash = "generic_ocr"
        # Check standard app storage location first
        api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        possible_dirs = [
            os.path.join(api_dir, "storage", "knowledge_center", "ocr_cache", file_hash),
            os.path.join("storage", "knowledge_center", "ocr_cache", file_hash),
        ]
        for cdir in possible_dirs:
            cfile = os.path.join(cdir, f"page_{page_number}.txt")
            if os.path.exists(cfile):
                with open(cfile, "r", encoding="utf-8") as cf:
                    cached_text = cf.read()
                    if cached_text:
                        return cached_text
        cache_dir = possible_dirs[0]
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"page_{page_number}.txt")
    except Exception:
        pass

    pdf = None
    try:
        import pypdfium2 as pdfium
        import pytesseract
        from app.core.config import get_tesseract_cmd

        get_tesseract_cmd()  # Ensure Tesseract executable path is configured

        if pdfium_doc is not None:
            pdf = pdfium_doc
        elif file_path:
            pdf = pdfium.PdfDocument(file_path)
        else:
            pdf = pdfium.PdfDocument(file_bytes)
        if page_number < 1 or page_number > len(pdf):
            return ""
        page = pdf[page_number - 1]
        # Render at scale 1.5 (~150 DPI) for optimal balance between OCR accuracy and speed
        pil_image = page.render(scale=1.5).to_pil()
        ocr_text = pytesseract.image_to_string(pil_image, lang=lang)
        cleaned = clean_arabic_ocr_text(ocr_text or "")

        if cache_file and cleaned:
            try:
                with open(cache_file, "w", encoding="utf-8") as cf:
                    cf.write(cleaned)
            except Exception:
                pass

        return cleaned
    except Exception:
        logger.warning(f"OCR fallback failed on page {page_number}")
        return ""
    finally:
        if pdfium_doc is None and pdf is not None and hasattr(pdf, "close"):
            try:
                pdf.close()
            except Exception:
                pass


# =============================================================================
# 1. PDF PARSER (pdfplumber + selective OCR fallback)
# =============================================================================

def parse_pdf_document(file_bytes: bytes | None = None, filename: str = "", progress_callback: Any = None, file_path: str | None = None) -> ParsedDocument:
    """Parses a PDF document using pdfplumber, preserving page numbers, layout, tables, and images with automatic OCR fallback for garbled pages."""
    import pdfplumber
    import pypdfium2 as pdfium

    parsed_doc = ParsedDocument(
        title=os.path.splitext(filename)[0],
        doc_type="pdf",
    )

    pdfium_shared = None
    pdf_source = file_path if (file_path and os.path.exists(file_path)) else (io.BytesIO(file_bytes) if file_bytes else None)
    if pdf_source is None:
        return parsed_doc

    try:
        if file_path and os.path.exists(file_path):
            pdfium_shared = pdfium.PdfDocument(file_path)
        elif file_bytes:
            pdfium_shared = pdfium.PdfDocument(file_bytes)
    except Exception:
        pass

    try:
        with pdfplumber.open(pdf_source) as pdf:
            total_pages = len(pdf.pages)
            parsed_doc.total_pages = total_pages
            
            for p_idx, page in enumerate(pdf.pages, start=1):
                if progress_callback:
                    try:
                        progress_callback(p_idx, total_pages)
                    except Exception:
                        pass

                parsed_page = ParsedPage(page_number=p_idx)
                page_text = page.extract_text() or ""

                # Check for absent/scanned or garbled/mojibake text layer and fallback to OCR selectively
                needs_ocr = is_text_garbled(page_text) or (len(page_text.strip()) < 15 and len(page.images) > 0)
                if needs_ocr:
                    logger.info(f"Page {p_idx} has absent or corrupt text layer; triggering OCR fallback (ara+eng)...")
                    ocr_text = ocr_pdf_page(file_bytes=file_bytes, page_number=p_idx, lang="ara+eng", pdfium_doc=pdfium_shared, file_path=file_path)
                    if ocr_text:
                        page_text = ocr_text
                        parsed_page.extracted_via_ocr = True
                        parsed_doc.extracted_via_ocr = True
                        if p_idx not in parsed_doc.ocr_pages:
                            parsed_doc.ocr_pages.append(p_idx)

                parsed_page.raw_text = page_text

                # 1. Extract tables with strict structural & linguistic validation
                try:
                    tables = page.extract_tables()
                    for t in tables:
                        if not t:
                            continue
                        headers = [str(cell or "").strip() for cell in t[0]]
                        rows = [[str(cell or "").strip() for cell in row] for row in t[1:]]

                        is_valid, reason = is_valid_data_table(headers, rows)
                        if not is_valid:
                            logger.debug(f"Skipping fake table on page {p_idx}: {reason}")
                            continue

                        # Check if table text is garbled / reversed
                        table_text = "\n".join(" | ".join(row) for row in ([headers] + rows))
                        if is_text_garbled(table_text) or parsed_page.extracted_via_ocr:
                            # Attempt to fix visual-order reversed Arabic
                            fixed_headers = [fix_reversed_arabic_text(h) for h in headers]
                            fixed_rows = [[fix_reversed_arabic_text(c) for c in r] for r in rows]
                            fixed_table_text = "\n".join(" | ".join(row) for row in ([fixed_headers] + fixed_rows))
                            if is_text_garbled(fixed_table_text):
                                logger.warning(f"Table on page {p_idx} remains garbled after fix attempt; skipping to preserve quality.")
                                continue
                            headers = fixed_headers
                            rows = fixed_rows
                            table_text = fixed_table_text

                        pt = ParsedTable(
                            page_number=p_idx,
                            headers=headers,
                            rows=rows,
                            raw_text=table_text,
                        )
                        parsed_page.tables.append(pt)
                        parsed_doc.all_tables.append(pt)
                except Exception:
                    logger.debug(f"Table extraction skipped on page {p_idx} due to parsing anomaly")

                # 2. Extract text blocks & headings
                OPT_OR_ANS_RE = re.compile(
                    r"^([\(\[]?\s*([أ-دA-Da-d1-4]|i|z|s|\)\()\s*[\)\]\.\:\-\/]|(?:الإجاب[ةه]|الجواب|الحل|Answer|Key)\b)"
                )
                OPT_SUFFIX_RE = re.compile(
                    r"^(.*?)\s*[\(\[]\s*([أ-دA-Da-d1-4]|i|z|s|\)\()\s*[\)\]][\.\:\-]?$"
                )
                QUESTION_HEADER_RE = re.compile(
                    r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)|س\s*\d+|Question\s*\d+|Q\d+|^\(?\d{1,3}\)?[\.\-\:\)])\b",
                    re.IGNORECASE,
                )
                SECTION_HEADER_RE = re.compile(
                    r"^\s*\[?\s*(?:القسم\s+(?:الأول|الثاني|الثالث|الرابع)|أسئلة\s+الاختيار|الأسئلة\s+المقالية|أولاً|ثانياً|ثالثاً)\b",
                    re.IGNORECASE,
                )

                lines = [l.strip() for l in page_text.split("\n") if l.strip()]
                for b_idx, line in enumerate(lines):
                    # If this line is an option or answer belonging to the previous question block
                    if parsed_page.blocks and parsed_page.blocks[-1].block_type != "heading":
                        if OPT_OR_ANS_RE.match(line) or (OPT_SUFFIX_RE.match(line) and len(line.split()) <= 15):
                            parsed_page.blocks[-1].text += "\n" + line
                            continue

                    # If this line is a chemical equation belonging to the previous explanatory sentence
                    if parsed_page.blocks and is_chemical_equation_line(line):
                        prev_text = parsed_page.blocks[-1].text.strip()
                        intro_phrases = ["وفق المعادلة", "بالمعادلة", "كما يلي", "التفاعل التالي", "المعادلة الكيميائية", "المعادلة التالية", "المعادلة:"]
                        if prev_text.endswith(":") or any(ip in prev_text for ip in intro_phrases):
                            parsed_page.blocks[-1].text += "\n" + line
                            continue

                    # If previous block started with a question header and current line continues the stem
                    if parsed_page.blocks:
                        prev_b = parsed_page.blocks[-1]
                        first_prev_line = prev_b.text.split("\n")[0].strip()
                        if (
                            QUESTION_HEADER_RE.match(first_prev_line)
                            and not QUESTION_HEADER_RE.match(line)
                            and not SECTION_HEADER_RE.match(line)
                            and not (line.startswith("#") or line.isupper())
                        ):
                            prev_b.text += "\n" + line
                            continue

                    is_question_indicator = bool(QUESTION_HEADER_RE.match(line) or OPT_OR_ANS_RE.match(line))
                    is_heading = (
                        not is_question_indicator
                        and len(line) < 60
                        and not line.endswith(".")
                        and (line.startswith("#") or line.isupper() or len(line.split()) <= 6)
                    )

                    b_type = "heading" if is_heading else ("list" if line.startswith(("-", "*", "•", "1.", "2.")) else "paragraph")
                    block = ParsedBlock(
                        block_id=f"pdf_p{p_idx}_b{b_idx+1}",
                        block_type=b_type,
                        text=line,
                        level=1 if is_heading else 0,
                        page_number=p_idx,
                    )
                    parsed_page.blocks.append(block)
                    if is_heading:
                        parsed_doc.hierarchy.append({"title": line, "page": p_idx, "level": 1})

                # 3. Keep original PDF images, their OCR text, and page relationship.
                # PyMuPDF extraction is optional so installations without it keep the
                # existing text/table pipeline working.
                image_limit = int(os.getenv("IMAGE_OCR_MAX_PER_PAGE", "12"))
                img_data_list = extract_pdf_page_images(file_bytes, p_idx)[:image_limit]
                for img_idx, img_item in enumerate(img_data_list, start=1):
                    img_bytes = img_item[0]
                    width = img_item[1]
                    height = img_item[2]
                    bbox = img_item[3] if len(img_item) > 3 else None
                    # Skip OCR on tiny decorative assets (<60px or <2.5KB) to maximize indexing performance
                    if width < 60 or height < 60 or len(img_bytes) < 2500:
                        image_ocr, ocr_engine = "", None
                    else:
                        image_ocr, ocr_engine = ocr_image_bytes(img_bytes)

                    role = "supporting_visual"
                    if width < 36 or height < 36:
                        role = "decorative"
                    elif re.search(r"(?:الصورة|الشكل|الرسم|المنحنى|المخطط|التجربة|figure|diagram)", page_text[:500] if page_text else "", re.IGNORECASE):
                        role = "question_attachment"

                    parsed_img = ParsedImage(
                        id=f"img_p{p_idx}_{img_idx}",
                        page_number=p_idx,
                        asset_kind="figure",
                        caption=f"شكل توضيحي صفحة {p_idx}",
                        surrounding_text=page_text[:500] if page_text else None,
                        image_bytes=img_bytes,
                        width=width,
                        height=height,
                        checksum=hashlib.sha256(img_bytes).hexdigest(),
                        ocr_text=image_ocr or None,
                        ocr_engine=ocr_engine,
                        bbox=bbox,
                        role=role,
                    )
                    parsed_page.images.append(parsed_img)
                    parsed_doc.all_images.append(parsed_img)

                parsed_doc.pages.append(parsed_page)

        if parsed_doc.ocr_pages:
            parsed_doc.metadata["extracted_via_ocr"] = True
            parsed_doc.metadata["ocr_pages"] = parsed_doc.ocr_pages
            parsed_doc.metadata["ocr_engine"] = "tesseract-ara+eng"

    finally:
        if pdfium_shared is not None and hasattr(pdfium_shared, "close"):
            try:
                pdfium_shared.close()
            except Exception:
                pass

    return parsed_doc



# =============================================================================
# 2. DOCX PARSER (python-docx)
# =============================================================================

def parse_docx_document(file_bytes: bytes, filename: str) -> ParsedDocument:
    """Parses a Word DOCX document, preserving headings, paragraphs, lists, tables, and images."""
    import docx

    doc = docx.Document(io.BytesIO(file_bytes))
    parsed_doc = ParsedDocument(
        title=os.path.splitext(filename)[0],
        doc_type="docx",
        total_pages=1,
    )

    page = ParsedPage(page_number=1)
    raw_lines: list[str] = []
    OPT_OR_ANS_RE = re.compile(r"^([\(\[]?\s*[أ-دA-Da-d]\s*[\)\]\.\:\-\/]|(?:الإجاب[ةه]|الجواب|الحل|Answer|Key)\b)")

    # 1. Paragraphs & Headings
    for idx, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if not text:
            continue
        raw_lines.append(text)

        # If this paragraph is an option or answer belonging to the previous question block
        if page.blocks and page.blocks[-1].block_type != "heading" and OPT_OR_ANS_RE.match(text):
            page.blocks[-1].text += "\n" + text
            continue

        # If this paragraph is a chemical equation belonging to the previous explanatory sentence
        if page.blocks and is_chemical_equation_line(text):
            prev_text = page.blocks[-1].text.strip()
            intro_phrases = ["وفق المعادلة", "بالمعادلة", "كما يلي", "التفاعل التالي", "المعادلة الكيميائية", "المعادلة التالية", "المعادلة:"]
            if prev_text.endswith(":") or any(ip in prev_text for ip in intro_phrases):
                page.blocks[-1].text += "\n" + text
                continue

        style_name = (p.style.name or "").lower()
        is_heading = "heading" in style_name or style_name.startswith("title")
        
        b_type = "heading" if is_heading else ("list" if style_name.startswith("list") or text.startswith(("-", "*", "•", "1.")) else "paragraph")

        block = ParsedBlock(
            block_id=f"docx_b{idx+1}",
            block_type=b_type,
            text=text,
            level=int(style_name[-1]) if is_heading and style_name[-1].isdigit() else 1,
            page_number=1,
        )
        page.blocks.append(block)
        if is_heading:
            parsed_doc.hierarchy.append({"title": text, "page": 1, "level": block.level})

    # 2. Tables
    for t_idx, table in enumerate(doc.tables):
        table_rows: list[list[str]] = []
        for row in table.rows:
            cell_texts = [c.text.strip() for c in row.cells]
            table_rows.append(cell_texts)
        if table_rows:
            headers = table_rows[0]
            rows = table_rows[1:]
            t_text = "\n".join(" | ".join(r) for r in table_rows)
            pt = ParsedTable(page_number=1, headers=headers, rows=rows, raw_text=t_text)
            page.tables.append(pt)
            parsed_doc.all_tables.append(pt)

    # 3. Extract Embedded Images from DOCX relationship parts
    img_counter = 1
    for rel in doc.part.rels.values():
        if "image" in rel.target_ref:
            try:
                image_bytes = rel.target_part.blob
                checksum = hashlib.sha256(image_bytes).hexdigest() if image_bytes else str(uuid.uuid4().hex[:16])
                image_ocr, ocr_engine = ocr_image_bytes(image_bytes)
                parsed_img = ParsedImage(
                    id=f"docx_img_{img_counter}",
                    page_number=1,
                    asset_kind="figure",
                    caption=f"شكل توضيحي في مستند {parsed_doc.title}",
                    image_bytes=image_bytes,
                    checksum=checksum,
                    ocr_text=image_ocr or None,
                    ocr_engine=ocr_engine,
                )
                page.images.append(parsed_img)
                parsed_doc.all_images.append(parsed_img)
                img_counter += 1
            except Exception:
                logger.debug("DOCX image extraction skipped due to part anomaly")

    page.raw_text = "\n".join(raw_lines)
    parsed_doc.pages.append(page)
    return parsed_doc


# =============================================================================
# 3. PPTX PARSER (python-pptx)
# =============================================================================

def parse_pptx_document(file_bytes: bytes, filename: str) -> ParsedDocument:
    """Parses a PowerPoint PPTX presentation, preserving slides, titles, notes, and diagrams."""
    import pptx

    prs = pptx.Presentation(io.BytesIO(file_bytes))
    parsed_doc = ParsedDocument(
        title=os.path.splitext(filename)[0],
        doc_type="pptx",
        total_slides=len(prs.slides),
        total_pages=len(prs.slides),
    )

    for s_idx, slide in enumerate(prs.slides, start=1):
        parsed_page = ParsedPage(slide_number=s_idx, page_number=s_idx)
        slide_text_parts: list[str] = []

        # Slide Title
        title_text = ""
        if slide.shapes.title and slide.shapes.title.text:
            title_text = slide.shapes.title.text.strip()
            parsed_page.title = title_text
            parsed_doc.hierarchy.append({"title": title_text, "slide": s_idx, "level": 1})
            slide_text_parts.append(title_text)

        block_seq = 1
        img_counter = 1
        for shape in slide.shapes:
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    t = p.text.strip()
                    if t and t != title_text:
                        slide_text_parts.append(t)
                        block = ParsedBlock(
                            block_id=f"slide{s_idx}_b{block_seq}",
                            block_type="list" if p.level > 0 or t.startswith(("-", "*", "•")) else "paragraph",
                            text=t,
                            level=p.level,
                            slide_number=s_idx,
                        )
                        parsed_page.blocks.append(block)
                        block_seq += 1

            if shape.has_table:
                table_rows: list[list[str]] = []
                for row in shape.table.rows:
                    cell_texts = [c.text.strip() for c in row.cells]
                    table_rows.append(cell_texts)
                if table_rows:
                    headers = table_rows[0]
                    rows = table_rows[1:]
                    pt = ParsedTable(slide_number=s_idx, headers=headers, rows=rows, raw_text="\n".join(" | ".join(r) for r in table_rows))
                    parsed_page.tables.append(pt)
                    parsed_doc.all_tables.append(pt)

            if shape.shape_type == pptx.enum.shapes.MSO_SHAPE_TYPE.PICTURE:
                try:
                    img_bytes = shape.image.blob
                    image_ocr, ocr_engine = ocr_image_bytes(img_bytes)
                    parsed_img = ParsedImage(
                        id=f"pptx_s{s_idx}_img_{img_counter}",
                        slide_number=s_idx,
                        asset_kind="diagram",
                        caption=f"مخطط الشريحة {s_idx}: {title_text or parsed_doc.title}",
                        image_bytes=img_bytes,
                        checksum=hashlib.sha256(img_bytes).hexdigest() if img_bytes else str(uuid.uuid4().hex[:16]),
                        ocr_text=image_ocr or None,
                        ocr_engine=ocr_engine,
                    )
                    parsed_page.images.append(parsed_img)
                    parsed_doc.all_images.append(parsed_img)
                    img_counter += 1
                except Exception:
                    pass

        # Speaker notes
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                slide_text_parts.append(f"[ملاحظات المحاضر]: {notes}")
                parsed_page.blocks.append(ParsedBlock(
                    block_id=f"slide{s_idx}_notes",
                    block_type="note",
                    text=f"ملاحظات الشريحة {s_idx}: {notes}",
                    slide_number=s_idx,
                ))

        parsed_page.raw_text = "\n".join(slide_text_parts)
        parsed_doc.pages.append(parsed_page)

    return parsed_doc


# =============================================================================
# 4. TXT / MARKDOWN PARSER
# =============================================================================

def parse_txt_document(file_bytes: bytes, filename: str) -> ParsedDocument:
    """Parses a plain text or Markdown document preserving section headings, questions, and lists."""
    text = file_bytes.decode("utf-8", errors="ignore").strip()
    parsed_doc = ParsedDocument(
        title=os.path.splitext(filename)[0],
        doc_type="txt",
        total_pages=1,
    )

    page = ParsedPage(page_number=1, raw_text=text)
    OPT_OR_ANS_RE = re.compile(r"^([\(\[]?[أ-دA-Da-d][\)\]\.\:\-]|(?:الإجاب[ةه]|الجواب|الحل|Answer|Key)\b)")

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for b_idx, line in enumerate(lines):
        # If this line is an option or answer belonging to the previous question block
        if page.blocks and page.blocks[-1].block_type != "heading" and OPT_OR_ANS_RE.match(line):
            page.blocks[-1].text += "\n" + line
            continue

        markdown_heading = re.match(r"^(#{1,6})\s+", line)
        is_heading = bool(markdown_heading) or line.startswith(("==", "--")) or (
            len(line) < 60
            and not line.endswith(".")
            and not re.match(r"^[\(\[]?(\d+|[أ-دA-Da-d])[\)\]\.\:\-]", line)
            and len(line.split()) <= 6
        )

        b_type = "heading" if is_heading else ("list" if line.startswith(("-", "*", "•", "1.", "2.")) else "paragraph")
        clean_text = re.sub(r"^#+\s*", "", line) if is_heading else line
        heading_level = len(markdown_heading.group(1)) if markdown_heading else 1

        block = ParsedBlock(
            block_id=f"txt_b{len(page.blocks)+1}",
            block_type=b_type,
            text=clean_text,
            level=heading_level if is_heading else 0,
            page_number=1,
        )
        page.blocks.append(block)
        if is_heading:
            parsed_doc.hierarchy.append({"title": block.text, "page": 1, "level": heading_level})

    parsed_doc.pages.append(page)
    return parsed_doc


# =============================================================================
# 5. IMAGE PARSER
# =============================================================================

def parse_image_asset(file_bytes: bytes, filename: str) -> ParsedDocument:
    """Parses a standalone image file (diagram, figure, map, equation)."""
    img = Image.open(io.BytesIO(file_bytes))
    parsed_doc = ParsedDocument(
        title=os.path.splitext(filename)[0],
        doc_type="image",
        total_pages=1,
    )

    image_ocr, ocr_engine = ocr_image_bytes(file_bytes)
    parsed_img = ParsedImage(
        id=f"img_asset_{uuid.uuid4().hex[:8]}",
        page_number=1,
        asset_kind="figure",
        caption=f"شكل توضيحي: {parsed_doc.title}",
        image_bytes=file_bytes,
        width=img.width,
        height=img.height,
        checksum=hashlib.sha256(file_bytes).hexdigest() if file_bytes else str(uuid.uuid4().hex[:16]),
        ocr_text=image_ocr or None,
        ocr_engine=ocr_engine,
    )

    raw_text = image_ocr or f"صورة توضيحية: {parsed_doc.title}"
    page = ParsedPage(page_number=1, images=[parsed_img], raw_text=raw_text, extracted_via_ocr=bool(image_ocr))
    if image_ocr:
        page.blocks.append(ParsedBlock(
            block_id="image_ocr_1",
            block_type="paragraph",
            text=image_ocr,
            page_number=1,
        ))
        parsed_doc.extracted_via_ocr = True
        parsed_doc.ocr_pages = [1]
        parsed_doc.metadata.update({"ocr_engine": ocr_engine, "ocr_pages": [1]})
    parsed_doc.pages.append(page)
    parsed_doc.all_images.append(parsed_img)
    return parsed_doc


# =============================================================================
# 6. ASSESSMENT BANK PARSER (Quizzes, Exams, Homework)
# =============================================================================

def parse_assessment_bank(file_bytes: bytes, filename: str) -> list[ParsedAssessmentQuestion]:
    """Parses a teacher's previous assessment file (JSON, DOCX, TXT) into ParsedAssessmentQuestion records."""
    questions: list[ParsedAssessmentQuestion] = []
    content_str = file_bytes.decode("utf-8", errors="ignore").strip()

    # Case A: JSON structured question bank
    if content_str.startswith(("[", "{")):
        try:
            data = json.loads(content_str)
            raw_list = data if isinstance(data, list) else data.get("questions", [])
            for item in raw_list:
                if isinstance(item, dict) and "question_text" in item:
                    q = ParsedAssessmentQuestion(
                        question_text=item["question_text"],
                        question_type=item.get("question_type", "multiple_choice"),
                        difficulty=item.get("difficulty", "medium"),
                        learning_objective=item.get("learning_objective", "understanding"),
                        topic_concept=item.get("topic_concept", item.get("topic", "مفهوم الكويز")),
                        correct_answer=item.get("correct_answer"),
                        options=item.get("options", []),
                        explanation=item.get("explanation"),
                        media_ids=item.get("media_ids", []),
                    )
                    questions.append(q)
            if questions:
                return questions
        except Exception:
            pass


    # Case B: Text or Word question bank format (Question stems with options)
    blocks = [b.strip() for b in re.split(r"\n\s*\n|\n(?=\d+[\.\-\)])", content_str) if len(b.strip()) > 10]
    for b in blocks:
        lines = [l.strip() for l in b.split("\n") if l.strip()]
        if not lines:
            continue
        stem = lines[0]
        options: list[dict[str, Any]] = []
        correct_ans = None

        for l in lines[1:]:
            opt_match = re.match(r"^[\(\[\{\s]*([أبجدABCD1234])[\)\.\:\-\s]+(.+)$", l)
            if opt_match:
                key, text = opt_match.group(1), opt_match.group(2).strip()
                is_corr = "[صح]" in text or "(صح)" in text or "[✓]" in text or "*" in l
                clean_text = re.sub(r"\[صح\]|\(صح\)|\[✓\]|\*", "", text).strip()
                options.append({"key": key, "text": clean_text, "is_correct": is_corr})
                if is_corr:
                    correct_ans = clean_text

        q_type = "multiple_choice" if len(options) >= 3 else ("true_false" if len(options) == 2 or "صح" in stem or "خطأ" in stem else "essay")
        
        q = ParsedAssessmentQuestion(
            question_text=stem,
            question_type=q_type,
            difficulty="medium",
            topic_concept="مفهوم الاختبار السابق",
            correct_answer=correct_ans,
            options=options,
            raw_text=b,
        )
        questions.append(q)

    return questions


def ocr_image_bytes(image_bytes: bytes, lang: str = "ara+eng") -> tuple[str, str | None]:
    """Read Arabic/English text from a source image without changing the original."""
    if not image_bytes:
        return "", None

    if os.getenv("PADDLE_OCR_ENABLED", "").lower() in {"1", "true", "yes"}:
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-not-found]

            ocr = PaddleOCR(lang="arabic", use_doc_orientation_classify=False, use_doc_unwarping=False)
            result = ocr.predict(io.BytesIO(image_bytes))
            lines: list[str] = []
            for page in result or []:
                payload = page.json if hasattr(page, "json") else page
                for text in (payload.get("rec_texts", []) if isinstance(payload, dict) else []):
                    if text:
                        lines.append(str(text))
            extracted = clean_arabic_ocr_text("\n".join(lines))
            if extracted:
                return extracted, "paddleocr-arabic"
        except Exception:
            logger.debug("PaddleOCR image extraction unavailable; using Tesseract fallback")

    try:
        import pytesseract
        from app.core.config import get_tesseract_cmd

        get_tesseract_cmd()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image = ImageOps.autocontrast(ImageOps.grayscale(image))
        extracted = pytesseract.image_to_string(image, lang=lang, config="--psm 6")
        return clean_arabic_ocr_text(extracted), "tesseract-ara+eng"
    except Exception:
        logger.debug("Image OCR skipped because no OCR engine is configured")
        return "", None


def extract_pdf_page_images(file_bytes: bytes, page_number: int) -> list[tuple[bytes, int, int, list[float] | None]]:
    """Extract original raster images and their bounding box from a PDF page via PyMuPDF when available."""
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz  # fallback PyMuPDF alias

        document = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            page = document.load_page(page_number - 1)
            images: list[tuple[bytes, int, int, list[float] | None]] = []
            seen: set[int] = set()
            for image_info in page.get_images(full=True):
                xref = image_info[0]
                if xref in seen:
                    continue
                seen.add(xref)
                extracted = document.extract_image(xref)
                data = extracted.get("image")
                width, height = int(extracted.get("width", 0)), int(extracted.get("height", 0))
                if data and width >= 32 and height >= 32:
                    bbox = None
                    try:
                        rects = page.get_image_rects(xref)
                        if rects:
                            r = rects[0]
                            bbox = [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]
                    except Exception:
                        pass
                    images.append((data, width, height, bbox))
            return images
        finally:
            document.close()
    except Exception:
        return []


# =============================================================================
# UNIFIED DISPATCH PARSER
# =============================================================================

def parse_knowledge_file(file_bytes: bytes | None = None, filename: str = "", mime_type: str | None = None, progress_callback: Any = None, file_path: str | None = None) -> ParsedDocument:
    """Dispatches a source file to the correct structure-preserving parser."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")

    if ext == "pdf":
        return parse_pdf_document(file_bytes, filename, progress_callback=progress_callback, file_path=file_path)
    elif ext in ("docx", "doc"):
        if file_bytes is None and file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        return parse_docx_document(file_bytes or b"", filename)
    elif ext in ("pptx", "ppt"):
        if file_bytes is None and file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        return parse_pptx_document(file_bytes or b"", filename)
    elif ext in ("png", "jpg", "jpeg", "webp", "gif"):
        if file_bytes is None and file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        return parse_image_asset(file_bytes or b"", filename)
    else:
        # Default text / markdown parser
        if file_bytes is None and file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        return parse_txt_document(file_bytes or b"", filename)
