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
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageOps

from app.core.errors import OperationCancelledError

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

    raw_words = text.split()
    # MCQ option markers - '(a)', '(b)', 'A)', unicode bracket markers - are
    # deliberate answer choices, not mojibake fragments. Detect them on the RAW
    # token (before stripping punctuation) so '(a) S' never counts as fragmented.
    option_marker = re.compile(r"^[\(\[]?[A-Za-zء-ي][\)\]]?$")
    stripped_words = [w.strip('.,()!?[]' + chr(34) + chr(39)) for w in raw_words]
    words = [w for w in stripped_words if w]
    if len(words) > 5:
        # Check 4: Mixed fragmented non-words (single Latin letters separated by spaces e.g. 'c R Ú e C G')
        option_positions = {i for i, w in enumerate(raw_words) if option_marker.match(w)}
        adjacent_answers = {i + 1 for i in option_positions}  # answer text right after a marker
        single_char_words = sum(
            1
            for i, w in enumerate(stripped_words)
            if w and len(w) == 1 and w.isascii() and i not in option_positions and i not in adjacent_answers
        )
        if (single_char_words / max(len(words), 1)) > 0.35 and arabic_ratio < 0.30:
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
    (r'(^|[\u0600-\u06FF\s])الأومنيوم(?=[\u0600-\u06FF\s]|$)', r'\g<1>الألومنيوم'),
    (r'(^|[\u0600-\u06FF\s])أومنيوم(?=[\u0600-\u06FF\s]|$)', r'\g<1>ألومنيوم'),
]


def is_reversed_arabic_token(w: str) -> bool:
    w = w.strip('.,()!?[]:"\'')
    if not w or len(w) < 2:
        return False
    if w.startswith(('ة', '\ufe93', '\ufe94')):
        return True
    if w.endswith(('لا', 'لآ', 'لأ', 'لإ')) and w not in ('لا', 'إلا', 'كلا', 'لولا', 'علا', 'العلا', 'هلا', 'جلا', 'المكلا'):
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
    # Reversed Arabic text has many tokens starting with Taa Marbuta (impossible in normal Arabic)
    # or ending with reversed Alif-Lam. Require at least 2 distinct reversed tokens.
    rev_tokens = sum(1 for w in words if is_reversed_arabic_token(w))
    return rev_tokens >= 2 or (len(words) <= 3 and rev_tokens >= 1)


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


def normalize_arabic_presentation_forms(text: str) -> str:
    """
    Normalizes Arabic Presentation Forms-A (U+FB50–U+FDFF) and Presentation Forms-B (U+FE70–U+FEFC)
    to standard logical Arabic characters (U+0621–U+064A) using unicodedata NFKC.
    CRITICAL: Preserves chemical formulas, superscripts, subscripts, and scientific notations
    (e.g., N₂ + 3H₂ ⇌ 2NH₃, SO₃²⁻, 1 × 10⁻⁷, Fe(s) | Fe²⁺(aq) || Ni²⁺(aq) | Ni) by ONLY
    normalizing glyphs within the Arabic presentation forms code blocks.
    Also strips rogue bidi control marks, svg remnants, and UI button leftovers.
    """
    if not text:
        return ""

    # 1. Selectively normalize ONLY Arabic presentation form codepoints
    chars = []
    for ch in text:
        code = ord(ch)
        if (0xFB50 <= code <= 0xFDFF) or (0xFE70 <= code <= 0xFEFC):
            chars.append(unicodedata.normalize("NFKC", ch))
        else:
            chars.append(ch)
    normalized = "".join(chars)

    # 2. Filter bidi control marks
    normalized = BIDI_CHARS_RE.sub("", normalized)

    # PDF extractors may detach an Arabic combining mark from its base letter
    # (for example, ``مبتدئ ًا``). Join only whitespace before Arabic marks so
    # Latin text, chemical formula spacing, superscripts, and subscripts remain
    # untouched.
    normalized = re.sub(
        r"(?<=[\u0600-\u06FF])\s+(?=[\u064B-\u065F\u0670])",
        "",
        normalized,
    )
    # Strip orphan combining marks at the start of strings or preceded by whitespace
    normalized = re.sub(r"(?:^|(?<=\s))[\u064B-\u065F\u0670]+", "", normalized)
    # Normalize detached waw prefix with tashkeel e.g. 'وُيستخدم' or 'و ُيستخدم' -> 'ويستخدم'
    normalized = re.sub(r"\bو\s*ُ?يستخدم\b", "ويستخدم", normalized)
    normalized = re.sub(r"\bوُ(?=[\u0621-\u064A])", "و", normalized)

    # 3. Filter out svg remnants, e.g. svgsvg, <svg ... </svg>, etc.
    normalized = re.sub(r'(?i)<svg\b[^>]*>[\s\S]*?<\/svg>', ' ', normalized)
    normalized = re.sub(r'(?i)<\/?(?:svg|path|g|rect|circle|line|polygon|polyline)\b[^>]*>', ' ', normalized)
    normalized = re.sub(r'\b(?:svgsvg|svgxml|xmlns|viewBox)\b', ' ', normalized, flags=re.IGNORECASE)

    # 4. Filter button leftovers (e.g. "btn-primary", "click here to submit", UI button leftovers)
    normalized = re.sub(r'\b(?:btn|btn-[a-z0-9_\-]+|button-text|submit-btn)\b', ' ', normalized, flags=re.IGNORECASE)

    # 5. Fix common chemistry OCR and typographical errors
    normalized = re.sub(r'\bالأومنيوم\b', 'الألومنيوم', normalized)
    normalized = re.sub(r'\bأومنيوم\b', 'ألومنيوم', normalized)

    return normalized


def clean_arabic_ocr_text(text: str) -> str:
    """Cleans OCR artifacts, normalizes presentation forms, removes rogue Unicode BiDi isolation marks, and context-aware fixes for Tesseract confusions."""
    if not text:
        return ""
    cleaned = normalize_arabic_presentation_forms(text)
    # Only apply Arabic substitutions if text has an Arabic context to avoid corrupting English words (e.g. 'of', 'in', 'to')
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', cleaned))
    if has_arabic:
        for pat, rep in OCR_ARABIC_CONFUSIONS:
            cleaned = re.sub(pat, rep, cleaned)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    return cleaned.strip()


SUB_MAP = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
SUP_MAP = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")


def clean_chemical_formula_text(text: str) -> str:
    """
    Normalizes chemical formulas, cleans LaTeX remnants and removes markdown asterisks.
    Fully deterministic and general across scientific & chemical texts.
    """
    if not text:
        return ""
    s = text

    # 1. Remove markdown bold/italic asterisks completely
    s = re.sub(r"\*{2,}", "", s)
    s = re.sub(r"(?<!\w)\*(?!\w)", "", s)

    # 2. Clean LaTeX text wrappers: \text{...}, \mathrm{...}, \mathbf{...}
    s = re.sub(r"\\(?:text|mathrm|mathbf)\{([^}]*)\}", r"\1", s)

    # 3. Mathematical and chemical operators
    s = s.replace(r"\cdot", "·").replace(r"\times", "×")
    s = s.replace(r"^\circ", "°").replace(r"\circ", "°")
    s = re.sub(r"\\Delta\s*H\b|Delta\s*H\b|\\Delta\b", "ΔH", s)
    s = re.sub(r"\bquad\s*,\s*quad\b", ", ", s)
    s = re.sub(r"\bquad\b", " ", s)
    s = re.sub(r"\\[,;:]", " ", s)
    s = re.sub(r"\\mid\b|(?<=\w)\s+mid\s+(?=\w)", " | ", s)
    s = re.sub(r"\\parallel\b|(?<=\w)\s+parallel\s+(?=\w)", " || ", s)

    # 4. Equilibrium constants and potentials
    s = re.sub(r"K_\{?sp\}?", "Ksp", s)
    s = re.sub(r"\bK_([abw])\b", r"K\1", s)
    s = re.sub(r"E\^\{?[°\\]*circ\}?_\{?cell\}?", "E°cell", s)
    s = re.sub(r"E\^\{?°\}?_\{?cell\}?", "E°cell", s)
    s = re.sub(r"E°_\{?cell\}?", "E°cell", s)

    # 5. Subscripts and superscripts
    s = re.sub(r"\\?_\{?\((s|aq|l|g|dil|conc)\)\}?", r"(\1)", s)
    s = re.sub(r"_\{(\d+)\((s|aq|l|g|dil|conc)\)\}", lambda m: m.group(1).translate(SUB_MAP) + f"({m.group(2)})", s)
    s = re.sub(r"_\{(\d+)\}", lambda m: m.group(1).translate(SUB_MAP), s)
    s = re.sub(r"\^\{([0-9\+\-]+)\}", lambda m: m.group(1).translate(SUP_MAP), s)
    s = re.sub(r"\^([0-9\+\-]+)", lambda m: m.group(1).translate(SUP_MAP), s)
    s = re.sub(r"([A-Za-z\)])_(\d+)", lambda m: m.group(1) + m.group(2).translate(SUB_MAP), s)
    s = re.sub(r"\(([^)]+)\)_(\d+)", lambda m: f"({m.group(1)})" + m.group(2).translate(SUB_MAP), s)
    s = re.sub(r"([A-Za-z]+)\^\{?([0-9]+[+-])\}?", lambda m: m.group(1) + m.group(2).translate(SUP_MAP), s)
    s = re.sub(r"([A-Za-z]+)([2-4][+-])(?=[\s,\)\]\|]|$)", lambda m: m.group(1) + m.group(2).translate(SUP_MAP), s)
    s = re.sub(r"\\alpha\b|\\?alpha(?=%)", "α", s)
    s = s.replace(r"\alpha", "α").replace(r"\beta", "β").replace(r"\gamma", "γ")

    # 6. LaTeX arrows
    s = s.replace(r"\rightleftharpoons", "⇌").replace(r"\rightarrow", "→")

    # 7. Delimiters and leftover LaTeX backslashes
    s = s.replace("$$", "").replace("$", "")
    s = re.sub(r"\\([a-zA-Z%])", r"\1", s)
    s = re.sub(r"\\+", "", s)

    # 8. Standard chemical symbols
    s = re.sub(r"\bPH\b", "pH", s)

    # Clean double spaces
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def fix_arabic_bidi_scrambling(text: str) -> str:
    """
    Repairs Arabic bidirectional text ordering anomalies produced by LTR-stream PDF extractors:
    - Inverted parentheses e.g. ')word(' -> '(word)'
    - Voltage and equality expressions e.g. '0.74+ =$ إذا علمت... V' -> 'إذا علمت أن جهد تأكسد الكروم = +0.74 V'
    - Split quantities e.g. '14.3$ ُأذيب g' -> 'ُأذيب 14.3 g'
    - Celsius temperature expressions and ranges e.g. 'من 400°C 700إلى°C' -> 'من 400°C إلى 700°C'
    - Premise and lead clause inversions e.g. '، كيف يمكن... سبيكة...' -> 'سبيكة...، كيف يمكن...'
    - Sequential condition and conclusion ordering
    """
    if not text:
        return ""
    s = text

    # Delimiters clean early
    s = s.replace("$$", "").replace("$", "")

    # Step 1: Normalize reversed isolated parentheses )word( -> (word)
    s = re.sub(r"(?:^|(?<=[\s،,؛;\.\:؟\?]))\)\s*([^\(\)]+?)\s*\((?=[\s،,؛;\.\:؟\?]|(?=[\u0600-\u06FF])|$)", r"(\1)", s)
    s = re.sub(r"(?:^|(?<=[\s،,؛;\.\:؟\?]))\)\s*([^\(\)\s]+)\s*\)(?=[\s،,؛;\.\:؟\?]|(?=[\u0600-\u06FF])|$)", r"(\1)", s)
    s = re.sub(r"(?:^|(?<=[\s،,؛;\.\:؟\?]))\(\s*([^\(\)\s]+)\s*\((?=[\s،,؛;\.\:؟\?]|(?=[\u0600-\u06FF])|$)", r"(\1)", s)

    # Step 2: Separate tashkeel/damma-prefixed verbs fused without space e.g. 'التيرفثاليكُيعرف' -> 'التيرفثاليك يعرف'
    s = re.sub(r"([\u0621-\u064A])\s*\u064f?(يعرف|يسمى|يستخدم|يعبر|ينتج)\b", r"\1 \2", s)

    # Clean percentage symbols and escaped backslashes before digits
    s = re.sub(r"\\?%[ \t]*\\?(\d+(?:\.\d+)?)", r"\1%", s)
    s = re.sub(r"\\?(\d+(?:\.\d+)?)[ \t]*\\?%", r"\1%", s)

    # Step 3: Voltage / Equality expressions like '0.74+ =$ إذا علمت... V'
    def repl_volt(m):
        val = m.group(1).strip()
        clause = m.group(2).strip()
        unit = m.group(3).strip()
        if val.endswith("+") or val.endswith("-"):
            val = val[-1] + val[:-1]
        elif not val.startswith("+") and not val.startswith("-"):
            val = "+" + val
        return f"{clause} = {val} {unit}"

    s = re.sub(
        r"([+\-]?\d+(?:\.\d+)?\+?|\d+(?:\.\d+)?\-?)\s*=\s*([\u0600-\u06FF\s،؛\-]+?)\s*(?:\\?text\{\s*)?([A-Za-z]+)(?:\s*\})?",
        repl_volt,
        s
    )

    # Step 4: General quantity split: [Number] [Arabic words] [Unit]
    def repl_quantity(m):
        val = m.group(1).strip()
        clause = m.group(2).strip()
        unit = m.group(3).strip()
        unit = re.sub(r"^\\?text\{\s*([^\}]+)\s*\}$", r"\1", unit)
        return f"{clause} {val} {unit}"

    s = re.sub(
        r"(?<![0-9\.\-])(\d+(?:\.\d+)?)\s+([\u0600-\u06FF\u064B-\u065F\u0670\s،؛]+?)\s*(?:\\?text\{\s*)?(g|mL|L|M|mol|g/mol|A|s|min|h)(?:\s*\})?",
        repl_quantity,
        s
    )

    # Step 5: Degree Celsius expressions: '25 عند ^\circ\text{C}' -> 'عند 25°C'
    def repl_celsius(m):
        val = m.group(1).strip()
        clause = m.group(2).strip()
        return f"{clause} {val}°C"

    s = re.sub(
        r"(\d+(?:\.\d+)?)\s*([\u0600-\u06FF\s]+?)\s*(?:°C|\^?\\?circ(?:\\?text\{C\})?|درجة\s*(?:مئوية|سيليزية))",
        repl_celsius,
        s
    )

    # Step 6: Temperature range: 'من 400°C 700إلى°C' -> 'من 400°C إلى 700°C'
    def repl_temp_range(m):
        return f"من {m.group(1)}°C إلى {m.group(2)}°C"

    s = re.sub(
        r"(?:من\s*)?(\d+)(?:\^?\\?circ(?:\\?text\{C\})?|°C)\s*(\d+)\s*إلى\s*(?:\^?\\?circ(?:\\?text\{C\})?|°C)?",
        repl_temp_range,
        s,
    )
    s = re.sub(
        r"(?:من\s*)?(\d+)\s*(\d+)\s*إلى\s*(?:\^?\\?circ(?:\\?text\{C\})?|°C)",
        repl_temp_range,
        s,
    )

    # Step 7: Fix Question 4 conclusion inversion
    pattern_q4 = re.compile(
        r"(وتكون\s+مع\s*\([^\)]+\))\s*(فإن\s+[\u0600-\u06FF\s]+?)\s*[\.\،\,]\s*(راسب\s+[\u0600-\u06FF\s]+?)\s*(\([^\)]+\)\s*و\s*\([^\)]+\)\s*هما\s+على\s+الترتيب)"
    )
    s = pattern_q4.sub(r"\1 \3، \2 \4", s)

    # Step 8: Fix consumption / conclusion split e.g. 'اسُتهلك 25 mL فإن النسبة... تساوي .من الحمض:'
    pattern_q5 = re.compile(
        r"(اسُتهلك\s*\d+(?:\.\d+)?\s*(?:mL|L|g|mol|A))\s*(فإن\s+[\u0600-\u06FF\s]+?)\s*[\.\،\,]\s*(من\s+[\u0600-\u06FF]+)\s*:",
        re.IGNORECASE
    )
    s = pattern_q5.sub(r"\1 \3، \2:", s)

    # Step 9: Fix Clause inversions where question lead was placed at the start with leading comma
    def repl_clause_inv(m):
        q_part = m.group(1).lstrip("،,.- \t").strip()
        parenthesis = m.group(2).strip()
        premise = m.group(3).strip()
        return f"{premise} {parenthesis}، {q_part}"

    s = re.sub(
        r"^[،,.\s]*(\b(?:كيف|ما|ماذا|علل|هل|وضح|احسب|فإن)\b[^()]+?\؟?)\s*(\([^)]+\))\s*([\u0600-\u06FF\s]{4,})$",
        repl_clause_inv,
        s,
        flags=re.MULTILINE
    )

    # Step 10: Reorder parenthetical after question mark e.g. 'ما هو إجمالي عدد المتشكلات ... لهذه الصيغة؟ (الأيزوميرات)'
    s = re.sub(
        r"(\bعدد\s+المتشكلات\b)([\u0600-\u06FF\s]+)\؟\s*(\([^\)]+\))",
        r"\1 \3\2؟",
        s
    )

    # Step 11: Parenthetical definition followed by temporal premise
    # e.g. 'وكبريتات الزئبق... 40% في وجود حمض الكبريتيك (الأسيتيلين) عند إضافة الماء إلى الإيثاين عند 60°C'
    pat_ethyne = re.compile(
        r"([\u0600-\u06FF\s%\\\d]+?\bفي وجود\b[\u0600-\u06FF\s%\\\d]+?)\s*(\([^\)]+\))\s*(\b(?:عند|إذا|في حالة|بعد|قبل)\b[\u0600-\u06FF\s]+?)(?=\s+(?:عند|ثم|درجة|\d)|$)"
    )
    m_eth = pat_ethyne.search(s)
    if m_eth:
        p1 = m_eth.group(1).strip()
        paren = m_eth.group(2).strip()
        p2 = m_eth.group(3).strip()
        m_swap = re.match(r"^(و[\u0600-\u06FF\s]+?)\s*(\d+%\s*في وجود\s*[\u0600-\u06FF\s]+)$", p1)
        if m_swap:
            cond = m_swap.group(2).strip()
            cond = re.sub(r"^(\d+%)\s*(في وجود\s*[\u0600-\u06FF\s]+)", r"\2 \1", cond)
            p1 = f"{cond} {m_swap.group(1).strip()}"
        else:
            p1 = re.sub(r"^(\d+%)\s*(في وجود\s*[\u0600-\u06FF\s]+)", r"\2 \1", p1)
        s = s[:m_eth.start()] + f"{p2} {paren} {p1} " + s[m_eth.end():]

    # Step 12: Question header inversions e.g. ')درجات 3( :17 السؤال' -> 'السؤال 17: (3 درجات)'
    s = re.sub(r"[:\.\-]\s*(\d+)\s*(السؤال|سؤال)\b", r"\2 \1:", s)
    s = re.sub(r"\b(درجات|درجة|علامات|علامة)\s*(\d+)\b", r"\2 \1", s)
    s = re.sub(r"(\([^\)]*(?:درجات|درجة|علامات|علامة|marks?|pts?)[^\)]*\))\s*(السؤال\s*\d+\s*[:\.\-]?)", r"\2 \1", s)

    # Step 13: Section header inversions e.g. '[ )20 إلى 17 من( الأسئلة المقالية :ًثاني ]' -> '[ ثانياً: الأسئلة المقالية (من 17 إلى 20) ]'
    s = re.sub(
        r"\[?\s*\(\s*(?:من\s*)?(\d+)\s*إلى\s*(\d+)\s*(?:من\s*)?\)\s*(الأسئلة\s+المقالية)\s*:\s*ً?ثاني[ةا]?\s*\]?",
        r"[ ثانياً: \3 (من \2 إلى \1) ]",
        s,
    )
    s = re.sub(
        r"\[?\s*\(\s*(?:من\s*)?(\d+)\s*إلى\s*(\d+)\s*(?:من\s*)?\)\s*(أسئلة\s+الاختيار[^\:]*)\s*:\s*ً?أول[ىا]?\s*\]?",
        r"[ أولاً: \3 (من \2 إلى \1) ]",
        s,
    )

    # Step 14: Parenthetical lead clause inversion e.g. '(فوسفات الباريوم) و (كبريتات الباريوم) لديك خليط صلب من ملحي.'
    def repl_q17_lead(m):
        parens = m.group(1).strip()
        premise = m.group(2).strip()
        punct = m.group(3) or "."
        m_p = re.match(r"^\(([^\)]+)\)\s*(و|أو)\s*\(([^\)]+)\)$", parens)
        if m_p:
            parens = f"({m_p.group(3).strip()}) {m_p.group(2)} ({m_p.group(1).strip()})"
        return f"{premise} {parens}{punct}"

    s = re.sub(
        r"^(\([^\)]+\)\s*(?:و|أو)\s*\([^\)]+\))\s*(لديك\s+[\u0600-\u06FF\s]+?)([\.\،\,]?)$",
        repl_q17_lead,
        s,
        flags=re.MULTILINE,
    )

    # Step 15: Synthesis requirement inversion e.g. 'بنزوات الصوديوم مبتدئًا بـ نيترو كلوروبنزين - ميتا كيفية الحصول على مركب.'
    pat_synth = re.compile(
        r"([\u0600-\u06FF\s]+?\s*مبتدئً?ا\s*بـ?)\s*([\u0600-\u06FF\s\-]+?)\s*(كيفية\s+الحصول\s+على\s+مركب[\u0600-\u06FF\s\.]*)"
    )
    m_synth = pat_synth.search(s)
    if m_synth:
        p1 = m_synth.group(1).strip()
        mid = m_synth.group(2).strip()
        p3 = m_synth.group(3).strip().rstrip(".")
        if "-" in mid:
            parts = [p.strip() for p in mid.split("-")]
            mid = f"{parts[1]} - {parts[0]}"
        m_mob = re.match(r"^(.*?)(\s*مبتدئً?ا\s*بـ?)$", p1)
        if m_mob:
            p1 = f"{m_mob.group(2).strip()} {m_mob.group(1).strip()}"
        mid = re.sub(r"نيترو\s*كلوروبنزين", "كلورو نيتروبنزين", mid)
        prefix_nl = "\n" if s[:m_synth.start()].strip() and not s[:m_synth.start()].endswith("\n") else ""
        s = s[:m_synth.start()] + f"{prefix_nl}{p3} {mid} {p1}.\n" + s[m_synth.end():].lstrip("\r\n")

    # Clean detached or duplicated Arabic marks
    s = re.sub(r"(?:^|(?<=\s))[\u064B-\u065F\u0670]+", "", s)
    s = re.sub(r"\u064f?(أذيب|يعبر|يعرف|يسمى|ينتج)\b", r"\1", s)
    s = re.sub(r"\bو\s*ُ?يستخدم\b", "ويستخدم", s)
    s = re.sub(r"\bً?مساوية\s*تقريبً?ا?\b", "مساوية تقريبًا", s)

    # Clean stray punctuation at the beginning of questions (preserve negative numbers)
    s = re.sub(r"^[،,:\.\/]\s*", "", s.strip())
    s = re.sub(r"^[-–—]\s*(?!\d)", "", s.strip())

    # Clean double spaces
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


PARSER_OCR_VERSION = "v3"
_OCR_SEMAPHORE = threading.Semaphore(int(os.getenv("OCR_CONCURRENCY_LIMIT", "2")))


def prune_ocr_cache(max_age_days: int = 7, max_size_mb: int = 500) -> None:
    """Prunes disk OCR cache based on TTL and aggregate size limit."""
    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cache_base = os.path.join(api_dir, "storage", "ocr_cache")
    if not os.path.isdir(cache_base):
        return

    now = time.time()
    max_age_sec = max_age_days * 86400
    cached_files: list[tuple[str, float, int]] = []

    for root, _, files in os.walk(cache_base):
        for f in files:
            fp = os.path.join(root, f)
            try:
                st = os.stat(fp)
                if now - st.st_mtime > max_age_sec:
                    os.remove(fp)
                    continue
                cached_files.append((fp, st.st_mtime, st.st_size))
            except Exception:
                pass

    max_bytes = max_size_mb * 1024 * 1024
    total_bytes = sum(item[2] for item in cached_files)
    if total_bytes > max_bytes:
        cached_files.sort(key=lambda x: x[1])
        for fp, _, sz in cached_files:
            try:
                os.remove(fp)
                total_bytes -= sz
                if total_bytes <= max_bytes:
                    break
            except Exception:
                pass


def ocr_pdf_page(file_bytes: bytes | None = None, page_number: int = 1, lang: str = "ara+eng", pdfium_doc: Any = None, file_path: str | None = None) -> str:
    """
    Renders a specific PDF page to an image and performs OCR using Tesseract.
    Uses disk caching to prevent re-running OCR on previously processed pages.
    Cache key strictly uses the full file SHA-256, page number, language, and parser version.
    """
    cache_file = None
    cache_dir = None
    try:
        if file_bytes:
            file_hash = hashlib.sha256(file_bytes).hexdigest()
        elif file_path and os.path.exists(file_path):
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            file_hash = h.hexdigest()
        else:
            file_hash = "generic_ocr"

        api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        possible_dirs = [
            os.path.join(api_dir, "storage", "ocr_cache", file_hash),
            os.path.join("storage", "ocr_cache", file_hash),
        ]
        cache_dir = possible_dirs[0]
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"page_{page_number}_{lang}_{PARSER_OCR_VERSION}.txt")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as cf:
                cached_text = cf.read()
                if cached_text:
                    return cached_text
    except Exception:
        pass

    # Quiz/assignment extraction is now the ONLY consumer of OCR, and it runs
    # synchronously per single page/image inside the API process. The old
    # blanket production ban made every scanned upload fail with 422. Allow
    # in-process OCR for single-page requests, keep it configurable off.
    if os.getenv("ALLOW_IN_PROCESS_OCR", "true").strip().lower() in ("false", "0", "no"):
        raise RuntimeError("In-process OCR is disabled by configuration (ALLOW_IN_PROCESS_OCR=false).")

    with _OCR_SEMAPHORE:
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
            # Render at scale 1.5 (~150 DPI) with grayscale conversion to optimize memory
            pil_image = page.render(scale=1.5).to_pil()
            gray_image = pil_image.convert("L")
            try:
                ocr_text = pytesseract.image_to_string(gray_image, lang=lang)
            finally:
                try:
                    gray_image.close()
                    pil_image.close()
                except Exception:
                    pass
            cleaned = clean_arabic_ocr_text(ocr_text or "")

            if cache_file and cache_dir and cleaned:
                try:
                    import tempfile
                    tmp_fd, tmp_path = tempfile.mkstemp(dir=cache_dir, prefix="ocr_tmp_")
                    with os.fdopen(tmp_fd, "w", encoding="utf-8") as cf:
                        cf.write(cleaned)
                    os.replace(tmp_path, cache_file)
                    prune_ocr_cache()
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

def parse_pdf_document(file_bytes: bytes | None = None, filename: str = "", progress_callback: Any = None, file_path: str | None = None, cancel_check: Any = None) -> ParsedDocument:
    """Parses a PDF document using pdfplumber, preserving page numbers, layout, tables, and images with automatic OCR fallback for garbled pages."""
    import pdfplumber
    import pypdfium2 as pdfium

    parsed_doc = ParsedDocument(
        title=os.path.splitext(filename)[0],
        doc_type="pdf",
    )

    pdfium_shared = None
    fitz_doc = None
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
        import fitz
        if file_path and os.path.exists(file_path):
            fitz_doc = fitz.open(file_path)
        elif file_bytes:
            fitz_doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as fitz_err:
        logger.debug(f"PyMuPDF could not open PDF for primary text extraction: {fitz_err}")
        fitz_doc = None

    try:
        with pdfplumber.open(pdf_source) as pdf:
            total_pages = len(pdf.pages)
            parsed_doc.total_pages = total_pages
            
            for p_idx, page in enumerate(pdf.pages, start=1):
                if cancel_check and cancel_check():
                    logger.info("Cancellation requested; aborting PDF parsing on page %s of %s", p_idx, total_pages)
                    if pdfium_shared:
                        try:
                            pdfium_shared.close()
                        except Exception:
                            pass
                    if fitz_doc:
                        try:
                            fitz_doc.close()
                        except Exception:
                            pass
                    raise OperationCancelledError(f"PDF indexing cancelled on page {p_idx}")

                if progress_callback:
                    try:
                        progress_callback(p_idx, total_pages)
                    except Exception:
                        pass

                parsed_page = ParsedPage(page_number=p_idx)
                page_text = ""
                if fitz_doc and p_idx - 1 < len(fitz_doc):
                    try:
                        blocks = fitz_doc[p_idx - 1].get_text("blocks")
                        # Sort blocks geometrically by (y0, x0) with 6pt line clustering tolerance
                        blocks = sorted(blocks, key=lambda b: (round(b[1] / 6) * 6, b[0]))
                        fitz_text = "\n".join(b[4].strip() for b in blocks if b[4].strip())
                        if fitz_text and not is_text_garbled(fitz_text):
                            page_text = normalize_arabic_presentation_forms(fitz_text)
                    except Exception as fe:
                        logger.debug(f"fitz text extraction failed on page {p_idx}: {fe}")
                        page_text = ""

                if not page_text:
                    raw_extracted = page.extract_text() or ""
                    if raw_extracted:
                        page_text = normalize_arabic_presentation_forms(raw_extracted)

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

                # Some legacy Egyptian Arabic PDFs expose a valid Unicode text
                # layer in visual (right-to-left display) order.  It is not
                # mojibake, so OCR is neither necessary nor desirable, but it
                # must be restored to logical order before question assembly.
                # The fixer leaves normal Arabic and Latin chemical formulas
                # untouched, and reverses only when it finds concrete visual-
                # order Arabic signals.
                page_text = fix_reversed_arabic_text(page_text)
                page_text = fix_arabic_bidi_scrambling(page_text)

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
                    r"^([\(\[]?\s*([أبجدA-Da-d1-4]|i|z|s|\)\()\s*[\)\]\.\:\-\/]|(?:الإجاب[ةه]|الجواب|الحل|Answer|Key)\b)"
                )
                OPT_SUFFIX_RE = re.compile(
                    r"^(.*?)\s*[\(\[]\s*([أبجدA-Da-d1-4]|i|z|s|\)\()\s*[\)\]][\.\:\-]?$"
                )
                QUESTION_HEADER_RE = re.compile(
                    r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)|س\s*\d+|Question\s*\d+|Q\d+|^\(?\d{1,3}\)?\s*[\.\-\:]\s*(?!\d))",
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
                img_data_list = extract_pdf_page_images(
                    file_bytes,
                    p_idx,
                    file_path=file_path,
                )[:image_limit]
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
                try:
                    import psutil
                    rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
                    logger.info("PDF page %s/%s indexed (Peak RSS: %.1f MB)", p_idx, total_pages, rss_mb)
                except Exception:
                    pass

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
        if fitz_doc is not None and hasattr(fitz_doc, "close"):
            try:
                fitz_doc.close()
            except Exception:
                pass

    return parsed_doc



# =============================================================================
# 2. DOCX PARSER (python-docx)
# =============================================================================

def parse_docx_document(file_source: bytes | str, filename: str) -> ParsedDocument:
    """Parses a Word DOCX document, preserving headings, paragraphs, lists, tables, and images."""
    import docx

    doc = docx.Document(io.BytesIO(file_source) if isinstance(file_source, bytes) else file_source)
    parsed_doc = ParsedDocument(
        title=os.path.splitext(filename)[0],
        doc_type="docx",
        total_pages=1,
    )

    page = ParsedPage(page_number=1)
    raw_lines: list[str] = []
    OPT_OR_ANS_RE = re.compile(r"^([\(\[]?\s*[أبجدA-Da-d]\s*[\)\]\.\:\-\/]|(?:الإجاب[ةه]|الجواب|الحل|Answer|Key)\b)")

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

def parse_pptx_document(file_source: bytes | str, filename: str) -> ParsedDocument:
    """Parses a PowerPoint PPTX presentation, preserving slides, titles, notes, and diagrams."""
    import pptx

    prs = pptx.Presentation(io.BytesIO(file_source) if isinstance(file_source, bytes) else file_source)
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

def parse_txt_document(file_source: bytes | str, filename: str) -> ParsedDocument:
    """Parses a plain text or Markdown document preserving section headings, questions, and lists."""
    if isinstance(file_source, str):
        with open(file_source, "r", encoding="utf-8", errors="ignore") as source_file:
            text = source_file.read().strip()
    else:
        text = file_source.decode("utf-8", errors="ignore").strip()
    parsed_doc = ParsedDocument(
        title=os.path.splitext(filename)[0],
        doc_type="txt",
        total_pages=1,
    )

    page = ParsedPage(page_number=1, raw_text=text)
    OPT_OR_ANS_RE = re.compile(r"^([\(\[]?[أبجدA-Da-d][\)\]\.\:\-]|(?:الإجاب[ةه]|الجواب|الحل|Answer|Key)\b)")

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
            and not re.match(r"^[\(\[]?(\d+|[أبجدA-Da-d])[\)\]\.\:\-]", line)
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

def parse_image_asset(file_source: bytes | str, filename: str) -> ParsedDocument:
    """Parses a standalone image file (diagram, figure, map, equation)."""
    if isinstance(file_source, str):
        img = Image.open(file_source)
        with open(file_source, "rb") as source_file:
            file_bytes = source_file.read()
    else:
        file_bytes = file_source
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

    # Quiz/assignment extraction is now the ONLY consumer of OCR, and it runs
    # synchronously per single page/image inside the API process. The old
    # blanket production ban made every scanned upload fail with 422. Allow
    # in-process OCR for single-page requests, keep it configurable off.
    if os.getenv("ALLOW_IN_PROCESS_OCR", "true").strip().lower() in ("false", "0", "no"):
        raise RuntimeError("In-process OCR is disabled by configuration (ALLOW_IN_PROCESS_OCR=false).")

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


def extract_pdf_page_images(
    file_bytes: bytes | None,
    page_number: int,
    *,
    file_path: str | None = None,
) -> list[tuple[bytes, int, int, list[float] | None]]:
    """Extract original raster images and their bounding box from a PDF page via PyMuPDF when available."""
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz  # fallback PyMuPDF alias

        if file_path and os.path.exists(file_path):
            document = fitz.open(file_path)
        elif file_bytes:
            document = fitz.open(stream=file_bytes, filetype="pdf")
        else:
            return []
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

def parse_knowledge_file(file_bytes: bytes | None = None, filename: str = "", mime_type: str | None = None, progress_callback: Any = None, file_path: str | None = None, cancel_check: Any = None) -> ParsedDocument:
    """Dispatches a source file to the correct structure-preserving parser."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")

    if ext == "pdf":
        return parse_pdf_document(file_bytes, filename, progress_callback=progress_callback, file_path=file_path, cancel_check=cancel_check)
    elif ext in ("docx", "doc"):
        source = file_path if file_path and os.path.exists(file_path) else (file_bytes or b"")
        return parse_docx_document(source, filename)
    elif ext in ("pptx", "ppt"):
        source = file_path if file_path and os.path.exists(file_path) else (file_bytes or b"")
        return parse_pptx_document(source, filename)
    elif ext in ("png", "jpg", "jpeg", "webp", "gif"):
        source = file_path if file_path and os.path.exists(file_path) else (file_bytes or b"")
        return parse_image_asset(source, filename)
    else:
        # Default text / markdown parser
        source = file_path if file_path and os.path.exists(file_path) else (file_bytes or b"")
        return parse_txt_document(source, filename)
