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
from app.services.extraction_limits import (ExtractionLimitError, MAX_PAGES, MAX_RENDER_SIDE,
    MAX_RENDER_PIXELS, OCR_TIMEOUT_SECONDS, check_archive, check_image, ocr_slot, render_scale)

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

    Arabic presentation forms (U+FBxx / U+FExx) are a LEGACY-but-valid storage
    choice, not corruption: they normalize losslessly via NFKC.  All ratio
    checks therefore run on an NFKC-measured copy so a healthy presentation-
    forms text layer is never condemned (and never replaced by OCR); the
    caller's original text is left untouched.
    """
    if not text or len(text.strip()) < 10:
        return False

    # Measure corruption on an NFKC copy: presentation forms, compatibility
    # ligatures and symbol variants collapse to their canonical code points
    # before any ratio is computed.  Measurement only - `text` is unchanged.
    measured = unicodedata.normalize("NFKC", text)

    # Check 1: CID font tokens (e.g. (cid:103)(cid:164)...)
    cid_matches = len(re.findall(r'\(cid:\d+\)', text))
    if cid_matches >= 3:
        return True

    non_ws = [c for c in measured if not c.isspace()]
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

    raw_words = measured.split()
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

        # Check 5: Reversed Arabic (visual order instead of logical order)
        # In Arabic grammar, words NEVER begin with Taa Marbuta (ة or presentation variants).
        taa_marbuta_starts = sum(1 for w in words if w.startswith(('ة', '\ufe93', '\ufe94')))
        if taa_marbuta_starts >= 2:
            return True

    # Check 5c (outside the >5-word gate; self-guarded by TWO independent
    # anomalies): presentation-form dumps expose the same impossibility in
    # second position - a word whose second character is Taa Marbuta cannot
    # be logical Arabic (it would need a 1-letter prefix).  Word-FINAL plain
    # 'لل' is the NFKC residue of the lam-lam ligature in visual-order
    # dumps (logical Arabic writes a doubled lam as lam + shadda, one
    # letter; word-INITIAL 'لل' is the legitimate preposition and must not
    # fire).  Legit text has 0 of these anomalies and can never fire.
    taa_second_pos = sum(
        1 for w in words if len(w) >= 2 and w[1] in ('ة', '\u0629')
    )
    final_lam_lam = sum(
        1 for w in words if len(w) >= 4 and w.endswith('لل')
    )
    rev_alif_lam = sum(1 for w in words if w.endswith(('لا', 'لآ', 'لأ', 'لإ')))
    if taa_second_pos + final_lam_lam >= 2:
        return True
    if (rev_alif_lam / max(len(words), 1)) > 0.12 and (taa_marbuta_starts + taa_second_pos + final_lam_lam) >= 1:
        return True

    return False


BIDI_CHARS_RE = re.compile(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]')

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

    # PDF extractors may detach an Arabic combining mark from its base letter.
    # A space before a VOWEL mark (fatha/damma/kasra) belongs to the FOLLOWING
    # word's first letter ('اس ُتهلك' -> 'استُهلك'); a space before a TANWEEN
    # +alef tail belongs to the PRECEDING word's end ('علم ًا' -> 'علمًا').
    normalized = re.sub(
        r"(?<=[\u0600-\u06FF])[ \t]+([\u064F\u0650\u064E])([\u0621-\u064A])",
        r"\2\1",
        normalized,
    )
    normalized = re.sub(
        r"(?<=[\u0600-\u06FF])[ \t]+([\u064B-\u064D\u0670]+\u0627?)(?![\u0621-\u064A])",
        r"\1",
        normalized,
    )
    # Strip orphan combining marks at the start of strings or preceded by whitespace
    normalized = re.sub(r"(?:^|(?<=\s))[\u064B-\u065F\u0670]+", "", normalized)
    # A detached damma after the conjunction waw collapses to bare waw
    # (the damma belongs to the following verb's first consonant);
    # generic orthography — no verb lists.
    normalized = re.sub(r"\bو\s*\u064f(?=[\u0621-\u064A])", "و", normalized)
    normalized = re.sub(r"\bو\u064f(?=[\u0621-\u064A])", "و", normalized)

    # 3. Filter out svg remnants, e.g. svgsvg, <svg ... </svg>, etc.
    normalized = re.sub(r'(?i)<svg\b[^>]*>[\s\S]*?<\/svg>', ' ', normalized)
    normalized = re.sub(r'(?i)<\/?(?:svg|path|g|rect|circle|line|polygon|polyline)\b[^>]*>', ' ', normalized)
    normalized = re.sub(r'\b(?:svgsvg|svgxml|xmlns|viewBox)\b', ' ', normalized, flags=re.IGNORECASE)

    # 4. Filter button leftovers (e.g. "btn-primary", "click here to submit", UI button leftovers)
    normalized = re.sub(r'\b(?:btn|btn-[a-z0-9_\-]+|button-text|submit-btn)\b', ' ', normalized, flags=re.IGNORECASE)

    return normalized


def clean_arabic_ocr_text(text: str) -> str:
    """Normalize layout/Unicode without translating or guessing source words.

    A Latin word near Arabic may be intentional bilingual content. Spelling
    substitutions require visual evidence or an explicit teacher edit, not a
    dictionary keyed only by surrounding language.
    """
    if not text:
        return ""
    cleaned = normalize_arabic_presentation_forms(text)
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
    # Render the symbol; do not turn entropy/temperature or a bare delta into
    # enthalpy. Only the explicitly written H belongs in the result.
    s = re.sub(r"\\Delta\s*H\b|Delta\s*H\b", "ΔH", s)
    s = re.sub(r"\\Delta\b", "Δ", s)
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

    # Step 2: Generic vowel-reattachment — a stray damma fused onto the
    # conjunction waw belongs to the following word's first consonant; the
    # waw keeps its letter.  Restricted to the waw shape only: a general
    # letter+mark+letter rule would destroy legitimate mid-word diacritics
    # ('يُستخدم', 'أُذيب') whose marks were reattached correctly upstream.
    s = re.sub(r"\b\u0648[ \t]*\u064f(?=[\u0621-\u064A])", "\u0648", s)

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

    # Generic degree-unit dedup (no value changes): written-out unit fused
    # with the symbol is collapsed to the symbol, e.g. 'درجة°C' -> '°C' and
    # 'درجة مئوية°C' -> '°C'.  Also matches the LaTeX form before conversion
    # ('25 درجة ^\circ\text{C}').
    s = re.sub(r"درجة\s*(?:مئوية|سيليزية)?\s*(?=°C)", "", s)
    s = re.sub(r"درجة\s*(?:مئوية|سيليزية)?\s*(?=\^?\\?circ)", "", s)

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

    # Generic detached-mark repair (orthography only, no content words).
    # First: a space-separated mark+SINGLE-LETTER fragment after an Arabic
    # word is that word's reordered prefix ('ذيب ُأ' -> 'أُذيب').  A bare
    # alef after the mark is excluded: mark+alef is a tanween ending and
    # belongs to the FOLLOWING word ('بأن ًا علم' -> 'بأن علمًا').
    s = re.sub(
        r"([\u0621-\u064A][\u0621-\u064A\u064B-\u065F]*)[ \t]+([\u064B-\u065F])([\u0623\u0625\u0628-\u064A])(?![\u0621-\u064A])",
        r"\3\2\1",
        s,
    )
    # Then: a space-separated mark+alef tail closes the preceding word
    # ('علم ًا' -> 'علمًا'); a mark+letters fragment INTERLEAVES
    # ('اس ُتهلك' -> 'استُهلك': mark belongs on the first letter of the
    # rest); leftover space-preceded orphan marks drop.
    s = re.sub(
        r"([\u0621-\u064A][\u0621-\u064A]*)[ \t]+([\u064B-\u065F\u0670]+)\u0627(?![\u0621-\u064A])",
        "\\1\\2\u0627",
        s,
    )
    s = re.sub(
        r"([\u0621-\u064A][\u0621-\u064A\u064B-\u065F]*)[ \t]+([\u064B-\u065F])([\u0623\u0625\u0628-\u064A])([\u0621-\u064A\u064B-\u065F]*)",
        r"\1\3\2\4",
        s,
    )
    s = re.sub(r"(?:^|(?<=[ \t]))[\u064B-\u065F\u0670]+", "", s)
    # 'ُأذيب' -> 'أُذيب': a stray damma written before the alef-hamza of a
    # word-initial glottal stop belongs after it (generic orthography).
    s = s.replace("\u064f\u0623", "\u0623\u064f")
    # A space-preceded damma squeezed between two letters is a displaced
    # vowel mark: it fuses onto the FOLLOWING letter ('اس ُتهلك' -> 'استُهلك').
    s = re.sub(r"([\u0621-\u064A])[ \t]+\u064f([\u0621-\u064A])", "\\1\\2\u064f", s)
    # Written digit + fused unit symbol collapse the gap ('25 °C' -> '25°C'),
    # value untouched.
    s = re.sub(r"(\d)[ \t]+°C", r"\1°C", s)
    # Terminal sweep: a number written with the spoken degree word adjacent
    # to the °C symbol collapses to NUMBER+°C in any leftover ordering
    # ('25 درجة°C' / 'درجة 25°C' -> '25°C'), value untouched.
    s = re.sub(r"(\d+(?:\.\d+)?)[ \t]*(?:درجة[ \t]*(?:مئوية|سيليزية)?[ \t]*)°C", r"\1°C", s)
    s = re.sub(r"درجة[ \t]*(?:مئوية|سيليزية)?[ \t]*(\d+(?:\.\d+)?)°C", r"\1°C", s)

    # Clean stray punctuation at the beginning of questions (preserve negative numbers)
    s = re.sub(r"^[،,:\.\/]\s*", "", s.strip())
    s = re.sub(r"^[-–—]\s*(?!\d)", "", s.strip())

    # Clean double spaces
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


_RTL_ASSEMBLY_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_RTL_ASSEMBLY_LTRISH_RE = re.compile(r"[A-Za-z0-9$\\]")
_RTL_ASSEMBLY_OPT_LETTER_RE = re.compile(r"[\u0623\u0628\u062C\u062FA-Da-d1-4]")
_RTL_ASSEMBLY_MATH_MARKERS_RE = re.compile(r"[\\^_{}]")
# Structural signals that a line was stored in VISUAL order (display order ==
# stream order), expressed purely in characters, never in content words:
#  - a direction-neutral separator (comparison operator, equilibrium arrow,
#    standalone dash) sitting next to an Arabic word;
#  - a parenthesis pair wrapped around Arabic text in MIRRORED order ')...(';
#  - a bracket fused to a digit ('3(', ')16') or to a colon (':17').
_RTL_ASSEMBLY_VISUAL_SEP_RE = re.compile(
    r"[\u0600-\u06FF]\s*[><\u21CC\u2192\u2190]\s|[\u0600-\u06FF]\s+[-\u2013]\s+[\u0600-\u06FF]"
)
# Mirrored parenthetical requires TWO adjacent Arabic letters between the
# reversed parens: ')كبريتات الباريوم('.  A lone conjunction like ') و ('
# (which occurs inside logical lines around (X)/(Y) tokens) is NOT a signal.
_RTL_ASSEMBLY_MIRRORED_PAREN_RE = re.compile(
    r"\)\s*[\u0600-\u06FF][\u0600-\u06FF\u064B-\u065F][\u0600-\u06FF\u064B-\u065F\s\d]*\s*\("
)
_RTL_ASSEMBLY_FUSED_BRACKET_NUM_RE = re.compile(r"\d{1,3}\(|\)\d{1,3}|\s:\d{1,3}\b")
_RTL_ASSEMBLY_PUNCT_TAIL = {".", "\u060C", "\u061B", "\u061F", ":", "\u06D4"}
_RTL_ASSEMBLY_LEADING_MARKS_RE = re.compile(r"^([\u064B-\u065F\u0670]+)(.*)$", re.DOTALL)
# Prefix fragments: a damma/kasra/fatha fused with a single letter (يُ / أُ)
# emitted as its own span.  The rebuilt prefix is letter+marks.
_RTL_ASSEMBLY_PREFIX_FRAG_LETTER_LAST_RE = re.compile("^([\u064B-\u065F\u0670]+)([\u064A\u0623])$")
_RTL_ASSEMBLY_PREFIX_FRAG_LETTER_FIRST_RE = re.compile("^([\u064A\u0623])([\u064B-\u065F\u0670]+)$")
_RTL_ASSEMBLY_PUNCT_SPACE_RE = re.compile(r"\s+([\u061F\u060C\u061B])")
_RTL_ASSEMBLY_TRAILING_MARKS_RE = re.compile(r"[\u064B-\u065F\u0670]$")
# Reversed option label emitted in visual order: ')أ(' / ')أ (' / ')3('.  When
# the label wraps a SINGLE letter/digit it is an option marker, so the
# parenthetical is rotated to canonical '(أ)' regardless of line family.
_RTL_ASSEMBLY_REVERSED_LABEL_RE = re.compile(r"\)([\u0623\u0628\u062C\u062F][\u064B-\u065F]?|[1-4A-Da-d])\(")
# Reversed parentheses wrapping ONLY digits and separators: ')0 , 1 (' ->
# '(0,1)'.  These are mirrored coordinate pairs, never real parentheticals.
_RTL_ASSEMBLY_REVERSED_NUMPAIR_RE = re.compile(r"\)\s*([0-9\u0660-\u0669.,\u060C\s]+)\(")
# Latin unit fused with a full stop ('m/s .' / 'V .'): the dot belongs to the
# sentence, not the unit, so it moves AFTER the unit token.
_RTL_ASSEMBLY_UNIT_DOT_RE = re.compile(r"([A-Za-z][A-Za-z0-9/\u00b2\u00b3\u2070-\u209f]*)\s+\.\s*$")
_RTL_ASSEMBLY_TANWEEN_RE = re.compile(r"[\u064B-\u064D]")
_RTL_ASSEMBLY_LABEL_GROUP_RE = re.compile(r"^[()\[\]\s]*[\u0623\u0628\u062C\u062FA-Da-d1-4][()\[\]\s]*$")


def _is_visual_order_stream(joined: str) -> bool:
    """Decide whether a line was stored visually, from structure only.

    No content words are involved: the signals are a direction-neutral
    separator adjacent to Arabic, mirrored Arabic parentheticals, or fused
    bracket/number tokens.  Math-heavy lines (LaTeX markers) are always
    logical.
    """
    if _RTL_ASSEMBLY_MATH_MARKERS_RE.search(joined):
        return False
    if _RTL_ASSEMBLY_VISUAL_SEP_RE.search(joined):
        return True
    if _RTL_ASSEMBLY_MIRRORED_PAREN_RE.search(joined):
        return True
    # A fused bracket/number alone is NOT proof of visual storage: mirrored
    # parentheses of chemical states like '(III)' can fuse in logical lines
    # too.  Structural confirmation requires Arabic plus bracket adjacency.
    if not _RTL_ASSEMBLY_ARABIC_RE.search(joined):
        return False
    return bool(_RTL_ASSEMBLY_FUSED_BRACKET_NUM_RE.search(joined))


def _is_ltrish_token(tok: str) -> bool:
    """True for formula/unit/Latin tokens that must stay atomic inside RTL lines.

    Question-number tokens ('14.') are excluded: they are layout labels,
    not LTR content runs, and must never force the logical family alone.
    """
    if not tok:
        return False
    if re.fullmatch(r"\d{1,3}[.:]", tok):
        return False
    if _RTL_ASSEMBLY_ARABIC_RE.search(tok):
        return False
    return bool(_RTL_ASSEMBLY_LTRISH_RE.search(tok))


def _has_stray_close_paren(tokens: list[str]) -> bool:
    """Token-level mirrored-paren signal: a ')' with no '(' still open.

    Visual-order storage emits the CLOSING paren of an Arabic parenthetical
    before its opening one (')word('), so a bare close with an empty stack
    is a structural visual-order proof that survives around balanced groups
    like '(III)' or '(X)'.
    """
    depth = 0
    for tok in tokens:
        for ch in tok:
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    return True
                depth -= 1
    return False


def _swap_visual_header_token(t: str) -> str:
    """Visual-order essay header token '3( :17' -> '17: (3' (points + number).

    Generic shape: points-number, mirrored open paren, colon, question
    number — no content words involved.
    """
    m = re.fullmatch(r"\s*(\d{1,3})\(\s*:\s*(\d{1,3})", t or "")
    if m:
        return f"{m.group(2)}: ({m.group(1)}"
    return t


def _mirror_brackets(s: str) -> str:
    """Mirror paired brackets (visual-order storage mirrors them)."""
    return s.translate(str.maketrans("()[]{}", ")(][}"))


def _swap_visual_bracket_token(t: str) -> str:
    """Repair fused bracket/digit tokens emitted in visual order.

    Visual-order storage mirrors paired brackets and fuses them with adjacent
    digits, e.g. ':17' -> '17:', '3(' -> '(3', ')20' -> '20)'.
    """
    if re.fullmatch(r":\d{1,3}", t):
        return t[1:] + ":"
    if re.fullmatch(r"\d{1,3}[(]", t):
        return "(" + t[:-1]
    if re.fullmatch(r"\d{1,3}[)]", t):
        return "(" + t[:-1]
    if re.fullmatch(r"[)]\d{1,3}", t):
        return t[1:] + ")"
    if re.fullmatch(r"[(]\d{1,3}", t):
        return t[1:] + ")"
    return t


def _reverse_arabic_comma(s: str) -> str:
    """In coordinate reading the Arabic comma lands mirrored: ',15' -> '15,'"""
    return re.sub(r",(\d+)", r"\1,", s)


def _rotate_reversed_labels(text: str) -> str:
    """Rotate mirrored option labels and mirrored coordinate pairs.

    ')أ(' is an option marker written with mirrored parentheses; a single
    letter/digit between REVERSED parens (no spaces) is never a real
    parenthetical, so it rotates to the canonical '(أ)' form.  Spaced forms
    like ') و (' - conjunctions inside logical text - never match.

    ')0 , 1 (' style number pairs (coordinate points, ordered pairs) get
    the same rotation: reversed parens wrapping only digits/separators are
    mirrored storage of '(0, 1)', and the comma inside a number pair
    separates members, so its spacing is normalized too.
    """
    text = _RTL_ASSEMBLY_REVERSED_LABEL_RE.sub(lambda m: f"({m.group(1)})", text)
    text = _RTL_ASSEMBLY_REVERSED_NUMPAIR_RE.sub(
        lambda m: "(" + m.group(1).replace(" ", "") + ")", text
    )
    return text


def _fuse_latin_unit_dots(words: list[str]) -> list[str]:
    """Attach a lone sentence dot to a preceding Latin/number token.

    '3 A . ما' -> '3 A. ما' and '20 s .' -> '20 s.': a full stop separated
    from a Latin unit/number by spaces is sentence punctuation the writer
    spaced out; it belongs to that token.  Arabic-word dots are untouched
    (an Arabic word never ends in a Latin letter), and multi-dot blank
    tokens ('............') are never single dots.
    """
    out: list[str] = []
    for w in words:
        if (
            w == "."
            and out
            and _RTL_ASSEMBLY_LTRISH_RE.search(out[-1][-1:])
            and not _RTL_ASSEMBLY_ARABIC_RE.search(out[-1][-1:])
        ):
            out[-1] = out[-1] + "."
            continue
        out.append(w)
    return out


def _cluster_rows(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster spans into visual rows with a running y-center and adaptive
    tolerance; rows carry their mean y for the assembler's loop."""
    lines: list[dict[str, Any]] = []
    for sp in sorted(spans, key=lambda s: s["yc"]):
        target = None
        for ln in lines:
            if abs(sp["yc"] - ln["y"]) <= max(6.0, 0.55 * sp["h"]):
                target = ln
                break
        if target is None:
            lines.append({"y": sp["yc"], "items": [sp]})
        else:
            n = len(target["items"])
            target["y"] = (target["y"] * n + sp["yc"]) / (n + 1)
            target["items"].append(sp)
    return lines


def _detect_column_gutter(spans: list[dict[str, Any]], page_width: float) -> float | None:
    """Detect a single vertical two-column gutter from pure geometry.

    Discriminator (line-based, no content words): on a genuine two-column
    page every visual row sits ENTIRELY on one side of the middle band -
    columns never mix inside a row.  On a single-column page, most rows
    span across the middle (long sentences, even when split into several
    spans).  A gutter is accepted only when rows crossing the middle are
    rare (headers) and both sides hold a real share of the rows.
    """
    if len(spans) < 12 or page_width <= 0:
        return None
    mid = page_width / 2.0
    band = 12.0
    # Cluster into visual rows (same tolerance as the assembler).
    rows: list[list[dict[str, Any]]] = []
    for sp in sorted(spans, key=lambda s: s["yc"]):
        if rows and abs(sp["yc"] - rows[-1][-1]["yc"]) <= max(6.0, 0.55 * sp["h"]):
            rows[-1].append(sp)
        else:
            rows.append([sp])
    n_rows = len(rows)
    if n_rows < 6:
        return None
    crossing_rows = 0
    right_rows = 0
    left_rows = 0
    for row in rows:
        has_left = any(sp["x0"] < mid - band for sp in row)
        has_right = any(sp["x1"] > mid + band for sp in row)
        spans_band = any(sp["x0"] < mid - band and sp["x1"] > mid + band for sp in row)
        if spans_band or (has_left and has_right):
            crossing_rows += 1
        elif has_right:
            right_rows += 1
        elif has_left:
            left_rows += 1
    if crossing_rows / n_rows > 0.25:
        return None
    if right_rows < 3 or left_rows < 3:
        return None
    return mid


def _reattach_leading_marks(tokens: list[str]) -> list[str]:
    """Merge combining-mark-led tokens into their reading predecessor.

    PDF writers sometimes emit a diacritic (or a displaced tanween) as its
    own span, or split a word into 'mark + letters' fragments.  Reattachment
    follows generic Arabic orthography only - no dictionary, no content
    knowledge:

    - mark(s) + alef ('ًا') is the word's tanween ending -> append verbatim;
    - other harakat starting a token ('ُتهلك') belong after the consonant
      they mark, so they interleave: prev + first-letter + mark + rest;
    - a mark-led token with no Arabic predecessor rebuilds itself
      ('ًأول' -> 'أولاً'), restoring the tanween's alef.
    """
    out: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        m = _RTL_ASSEMBLY_LEADING_MARKS_RE.match(tok) if tok else None
        if m:
            marks, rest = m.group(1), m.group(2)
            nxt = tokens[i + 1] if i + 1 < n else ""
            prev = out[-1] if out else ""
            if (
                rest
                and len(rest.split()) >= 2
                and _RTL_ASSEMBLY_TANWEEN_RE.search(marks)
                and _RTL_ASSEMBLY_ARABIC_RE.search(rest[:1])
            ):
                # 'ًمساوية تقريب' -> 'مساوية تقريبًا': a tanween mark leading
                # a MULTI-WORD fragment sits word-finally, so it closes the
                # fragment's last word (with its tanween alef).
                ws = rest.split()
                out.append(" ".join(ws[:-1] + [ws[-1] + marks + "\u0627"]))
                i += 1
                continue
            if (
                rest
                and len(rest) == 1
                and rest != "\u0627"
                and _RTL_ASSEMBLY_ARABIC_RE.search(rest[:1])
                and nxt
                and _RTL_ASSEMBLY_ARABIC_RE.search(nxt[:1])
                and not _is_ltrish_token(nxt)
            ):
                # 'ُي' + 'عرف' -> 'يُعرف': a mark+SINGLE-NON-ALEF-LETTER
                # fragment is the reordered PREFIX of the following word.
                # (mark+alef 'ًا' is a tanween ending and must attach to the
                # previous word instead.)
                out.append(rest + marks + nxt)
                i += 2
                continue
            if prev and _RTL_ASSEMBLY_ARABIC_RE.search(prev[-1:]):
                if rest.startswith("\u0627"):
                    out[-1] = prev + marks + rest
                    i += 1
                    continue
                if not rest:
                    out[-1] = prev + marks
                    i += 1
                    continue
                # Interleave would destroy a writer-pushed PREFIX fragment:
                # a mark+SINGLE-LETTER piece against a unit token (or at the
                # line end) is the previous word's reordered prefix ('ذيب' +
                # 'ُأ' + g$ -> 'أُذيب').  Leave those for the prefix pass;
                # multi-letter rests are normal split words and interleave
                # ('اس' + 'ُتهلك' -> 'استُهلك').
                if len(rest) == 1 and ((i + 1 >= n) or _is_ltrish_token(tokens[i + 1])):
                    out.append(tok)
                    i += 1
                    continue
                # Shadda marks gemination of the PREVIOUS consonant, so a
                # shadda-led fragment never interleaves ('نق' + 'ّي' ->
                # 'نقّي', not 'نقيّ').
                if "\u0651" in marks:
                    out[-1] = prev + marks + rest
                    i += 1
                    continue
                out[-1] = prev + rest[0] + marks + rest[1:]
                i += 1
                continue
            if not (prev and _RTL_ASSEMBLY_ARABIC_RE.search(prev[-1:])):
                # No Arabic neighbour: rebuild the word itself ('ًأول' -> 'أولاً').
                alef = "\u0627" if (_RTL_ASSEMBLY_TANWEEN_RE.search(marks) and not rest.endswith("\u0627")) else ""
                rebuilt = rest + marks + alef
                if rebuilt.strip():
                    out.append(rebuilt)
                    i += 1
                    continue
        out.append(tok)
        i += 1
    return out


def _resolve_tanween_fragments(items: list[dict[str, Any]]) -> None:
    """Attach a lone tanween fragment ('ًا') to the reading-successor span.

    Geometry: the fragment sits flush against the span that follows it in
    reading order (next span by ascending x).  The mark closes that span's
    LAST word ('الناتجة عنها، ومبين' + 'ًا' -> '...ومبينًا') - generic
    Arabic orthography, no content knowledge.
    """
    for i, sp in enumerate(items):
        t = sp["text"]
        m = re.fullmatch(r"([\u064B-\u065F]+)\u0627?", t or "")
        if not m:
            continue
        # Reading-order successor: the next span starting flush at (or just
        # after) this fragment's right edge — flush-touching counts
        # (successor x0 == fragment x1 is common in these layouts).
        best = None
        for j, other in enumerate(items):
            if j == i or other["x0"] < sp["x1"] - 0.5:
                continue
            if best is None or other["x0"] < items[best]["x0"]:
                best = j
        if best is None:
            continue
        succ = items[best]
        if not _RTL_ASSEMBLY_ARABIC_RE.search(succ["text"][-1:]):
            continue
        words = succ["text"].split()
        if not words:
            continue
        alef = "\u0627" if t.endswith("\u0627") else ""
        words[-1] = words[-1] + m.group(1) + alef
        succ["text"] = " ".join(words)
        sp["text"] = ""


def _resolve_prefix_fragments(items: list[dict[str, Any]]) -> None:
    """Merge 'mark+letter' prefix fragments (يُ / أُ) into the span to their left.

    Geometry: such a fragment sits flush against its left neighbour's right
    edge (x1).  The rebuilt prefix (letter + marks) prepends to that span's
    first word ('ُي' + 'ستخدم' -> 'يُستخدم') - generic Arabic morphology,
    no content knowledge.
    """
    for i, sp in enumerate(items):
        t = sp["text"]
        m1 = _RTL_ASSEMBLY_PREFIX_FRAG_LETTER_LAST_RE.match(t)
        m2 = _RTL_ASSEMBLY_PREFIX_FRAG_LETTER_FIRST_RE.match(t)
        if m1:
            letter, marks = m1.group(2), m1.group(1)
        elif m2:
            letter, marks = m2.group(1), m2.group(2)
        else:
            continue
        rebuilt = letter + marks
        for j in range(len(items) - 1, -1, -1):
            if j == i:
                continue
            prev = items[j]
            # Flush adjacency OR full x-coverage: fragments placed before the
            # unit token are covered by that unit span's bbox ('ستخدم'
            # spans [75.6..524.1] over the 'ُي' fragment at [174.69..177.14]).
            # Search the WHOLE line: writers emit these fragments with
            # degenerate zero-width boxes out of stream position.
            adjacent = abs(prev["x1"] - sp["x0"]) <= 5.0
            covered = prev["x0"] <= sp["x0"] and sp["x1"] <= prev["x1"]
            if (adjacent or covered) and _RTL_ASSEMBLY_ARABIC_RE.search(prev["text"][-1:]):
                words = prev["text"].split()
                words[0] = rebuilt + words[0]
                prev["text"] = " ".join(words)
                sp["text"] = ""
                break


def _fuse_arabic_word_fragments(tokens: list[str]) -> list[str]:
    """Fuse writer-split word fragments by generic Arabic orthography.

    - a token ending in a combining mark joins the following letters
      (the mark sits on its last consonant);
    - a lone Arabic prefix letter (و/ف/ب/ل/ك) at a token end attaches to the
      next Arabic token ('و' + 'يدرس' -> 'ويدرس'), including a waw that ends
      a longer fragment ('...الذرية، و' + 'يُستخدم' -> '...الذرية، ويُستخدم').
    """
    fused: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < n else None
        if (
            nxt
            and tok
            and _RTL_ASSEMBLY_ARABIC_RE.search(tok[-1:])
            and _RTL_ASSEMBLY_TRAILING_MARKS_RE.search(tok)
            and _RTL_ASSEMBLY_ARABIC_RE.search(nxt[:1])
            and not _is_ltrish_token(nxt)
        ):
            fused.append(tok + nxt)
            i += 2
            continue
        if (
            nxt
            and _RTL_ASSEMBLY_ARABIC_RE.search(nxt[:1])
            and not _is_ltrish_token(nxt)
            and (tok in ("\u0648", "\u0641", "\u0628", "\u0644", "\u0643") or re.search(r"(?:^|\s)[\u0648\u0641\u0628\u0644\u0643]$", tok or ""))
        ):
            m = re.search(r"(?:^|\s)([\u0648\u0641\u0628\u0644\u0643])$", tok or "")
            if tok in ("\u0648", "\u0641", "\u0628", "\u0644", "\u0643"):
                fused.append(tok + nxt)
            elif m:
                fused.append(tok[: m.start(1)] + m.group(1) + nxt)
            i += 2
            continue
        fused.append(tok)
        i += 1
    return fused


def _assemble_rtl_lines_from_fitz(fitz_page: Any) -> list[str]:
    """
    Coordinate-based line reassembly for Arabic (RTL) PDF pages.

    The unit of assembly is the typeset SPAN (``get_text("dict")``), not the
    word: words-mode silently drops detached combining marks, spans keep
    them.

    Mixed-storage documents: within one page some lines are stored logically
    (stream order == reading order) and others visually (stream order ==
    left-to-right display order).  Each line is routed by STRUCTURAL signals
    only (never content words):

    - math/LaTeX or pure-LTR lines -> verbatim left-to-right span order;
    - a direction-neutral separator next to Arabic ('>') -> visual line,
      read right-to-left (x-descending) with label/number/tail rotations;
    - lines containing LTR tokens (formulas/units) -> logical stream order;
    - a mirrored Arabic parenthetical ')word(' -> visual;
    - paren-initial lines (options) -> logical ascending-x order;
    - punctuation-final lines without stray marks -> logical stream order;
    - remaining Arabic stems/headers -> visual (geometry decides).

    Stray combining-mark spans are repaired generically BEFORE ordering:
    a 'mark+letter' prefix fragment (يُ / أُ) merges into the flush-left
    neighbour span's first word, and mark-led word fragments reattach by
    orthography afterwards.  No content words, no chemistry knowledge.
    """
    try:
        page_dict = fitz_page.get_text("dict")
    except Exception:
        return []

    # Page width for the two-column gutter detector.
    try:
        page_width = float(fitz_page.rect.width)
    except Exception:
        page_width = 595.0

    # Collect non-empty spans and cluster them into visual lines with a
    # running y-center and adaptive tolerance.
    spans: list[dict[str, Any]] = []
    for blk_i, blk in enumerate(page_dict.get("blocks", [])):
        for ln_i, ln in enumerate(blk.get("lines", [])):
            for sp_i, sp in enumerate(ln.get("spans", [])):
                txt = str(sp.get("text", ""))
                if not txt.strip():
                    continue
                x0, y0, x1, y1 = sp["bbox"]
                spans.append(
                    {
                        "x0": x0,
                        "x1": x1,
                        "yc": (y0 + y1) / 2,
                        "h": max(y1 - y0, 1.0),
                        "text": txt.strip(),
                        # True writer stream position (block, line, span):
                        # the authoritative order for logically-stored lines.
                        "seq": (blk_i, ln_i, sp_i),
                    }
                )
    if not spans:
        return []

    # ---- Two-column page split (RTL reading: right column first) --------
    # Detection is line-based geometry: on a genuine two-column page every
    # visual row sits entirely on one side of the middle band.  The page is
    # then split into two half-width sub-pages and each is assembled
    # independently; single-column pages are assembled whole.
    gutter = _detect_column_gutter(spans, page_width)
    row_clusters: list[list[dict[str, Any]]]
    if gutter is not None:
        right_spans = [sp for sp in spans if sp["x0"] >= gutter]
        left_spans = [sp for sp in spans if sp["x0"] < gutter]
        row_clusters = [
            _cluster_rows(group) for group in (right_spans, left_spans)
        ]
    else:
        row_clusters = [_cluster_rows(spans)]

    out: list[str] = []
    for rows in row_clusters:
        for ln in rows:
            items = [sp for sp in ln["items"] if sp["text"].strip()]
            if not items:
                continue
            # Restore the writer's stream order inside each visual row.
            items.sort(key=lambda s: s["seq"])
            if not items:
                continue

            # Geometry-driven prefix-fragment repair BEFORE any ordering.
            _resolve_prefix_fragments(items)
            _resolve_tanween_fragments(items)
            items = [sp for sp in items if sp["text"].strip()]
            if not items:
                continue

            # ---- Two-column layout guard -------------------------------------
            # Handled at PAGE level (see _detect_column_gutter): two-column
            # pages never mix columns inside one visual row, while single-
            # column pages have rows spanning the page middle.

            stream = [sp["text"] for sp in items]
            joined = " ".join(stream)
            xasc = sorted(items, key=lambda s: s["x0"])
            xdesc = sorted(items, key=lambda s: (-s["x0"], -s["x1"]))

            if not _RTL_ASSEMBLY_ARABIC_RE.search(joined) or _RTL_ASSEMBLY_MATH_MARKERS_RE.search(joined):
                # Pure LTR / math line: verbatim writer stream order (this is the
                # only order that keeps mixed Arabic+LaTeX premise lines readable).
                text = re.sub(r"\s{2,}", " ", " ".join(sp["text"] for sp in items)).strip()
                if text:
                    out.append(text)
                continue

            has_frag = any(_RTL_ASSEMBLY_LEADING_MARKS_RE.match(t) for t in stream)
            has_ltr = any(_is_ltrish_token(t) for t in stream)
            ends_punct = bool(stream and stream[-1].rstrip().endswith((":", ".")))
            label_option = bool(
                xasc
                and (xasc[0]["text"] or "") == "("
                and len(xasc) >= 2
                and re.fullmatch(r"[\u0623\u0628\u062C\u062FA-Da-d1-4]", xasc[1]["text"] or "")
            )

            if label_option:
                # Option rows ('(أ) ...') are canonical: label flush-left, text
                # ascending-x — even when they contain '>' comparison chains.
                family = "logical_xasc"
            elif _RTL_ASSEMBLY_VISUAL_SEP_RE.search(joined):
                family = "visual"
            elif _has_stray_close_paren(stream):
                family = "visual"
            elif _RTL_ASSEMBLY_ARABIC_RE.search(joined) and _RTL_ASSEMBLY_FUSED_BRACKET_NUM_RE.search(joined):
                family = "visual"
            elif _RTL_ASSEMBLY_MATH_MARKERS_RE.search(joined):
                family = "logical"
            elif has_ltr:
                family = "logical"
            elif ends_punct and not has_frag:
                family = "logical"
            else:
                # Stems/headers without structural signals: geometry wins.
                family = "visual"

            if family in ("logical", "logical_xasc"):
                ordered = items if family == "logical" else xasc
                words: list[str] = []
                for sp in ordered:
                    t = sp["text"]
                    if _is_ltrish_token(t):
                        words.append(t)
                    else:
                        words.extend(t.split())
                words = _reattach_leading_marks(words)
                words = _fuse_arabic_word_fragments(words)
                words = _reattach_leading_marks(words)
                # Tighten the split label triplet '( أ )' -> '(أ)'.
                tight: list[str] = []
                k2 = 0
                while k2 < len(words):
                    if (
                        k2 + 2 < len(words)
                        and words[k2] == "("
                        and words[k2 + 2] == ")"
                        and re.fullmatch(r"[\u0623\u0628\u062C\u062FA-Da-d1-4]", words[k2 + 1] or "")
                    ):
                        tight.append(f"({words[k2 + 1]})")
                        k2 += 3
                        continue
                    tight.append(words[k2])
                    k2 += 1
                words = tight
                # 'ذيب' + 'ُأ' -> 'أُذيب': a mark+SINGLE-LETTER fragment sitting
                # AFTER an Arabic word (next token LTR/absent) is that word's
                # reordered prefix, pushed by the writer before the unit token.
                for wi in range(len(words) - 1, 0, -1):
                    mm = _RTL_ASSEMBLY_LEADING_MARKS_RE.match(words[wi] or "")
                    if (
                        mm
                        and len(mm.group(2)) == 1
                        and mm.group(2) != "\u0627"
                        and _RTL_ASSEMBLY_ARABIC_RE.search(words[wi - 1][-1:])
                        and (wi + 1 >= len(words) or _is_ltrish_token(words[wi + 1]))
                    ):
                        words[wi - 1] = mm.group(2) + mm.group(1) + words[wi - 1]
                        del words[wi]
                # Word-level spacing: 'اس ُتهلك' -> 'استُهلك' (mark preceded by a
                # space fuses onto the following letter).
                words = [
                    (re.sub(r"([\u0621-\u064A])[ \t]+([\u064B-\u065F])", r"\1\2", w) if not _is_ltrish_token(w) else w)
                    for w in words
                ]
                # A question number displaced into the stream rotates to the head
                # so downstream 'N.' question-start detection still fires.
                if words and not re.match(r"^\(?\d{1,3}\)?\s*[.\-:]", words[0]):
                    for k in range(1, len(words)):
                        if re.fullmatch(r"\(?\d{1,3}\)?[.:]", words[k] or ""):
                            words.insert(0, words.pop(k))
                            break
                text = _rotate_reversed_labels(re.sub(r"\s{2,}", " ", " ".join(words)))
                text = _fuse_latin_unit_dots(text.split())
                text = " ".join(text)
                text = re.sub(r"\(\s+([^()]+?)\s+\)", r"(\1)", text)
                text = _RTL_ASSEMBLY_PUNCT_SPACE_RE.sub(r"\1", text)
                if text:
                    out.append(text)
                continue

            # ---- Visual-order path: read x-descending -------------------------
            seq = [_swap_visual_header_token(_swap_visual_bracket_token(sp["text"])) for sp in xdesc]
            seq = [_reverse_arabic_comma(t) for t in seq]
            # Enclosing frame rotation: '] ... [' -> '[ ... ]'.
            if len(seq) >= 2 and seq[0] in ")]}”" and seq[-1] in "([{\u201c":
                seq = [seq[-1]] + seq[1:-1] + [seq[0]]

            # Option label at the visual left end: ') أ (' or '(' + 'أ' -> '(أ)'
            label = None
            if len(seq) >= 2 and seq[-1] in "()" and re.fullmatch(
                r"[\u0623\u0628\u062C\u062FA-Da-d1-4]", seq[-2] or ""
            ):
                label = f"({seq[-2]})"
                seq = seq[:-2]

            # Question number at the visual left end: '14.' / '20:' -> head
            num = None
            if seq and re.fullmatch(r"\d{1,3}[.:]", seq[-1]):
                num = seq[-1]
                seq = seq[:-1]

            # Sentence-final punctuation at the visual right end -> logical end
            tail_punct = ""
            if seq and seq[0] in _RTL_ASSEMBLY_PUNCT_TAIL:
                tail_punct = seq[0]
                seq = seq[1:]

            seq = _reattach_leading_marks(seq)
            # Word-level orthographic repair inside spans ('نق ّي' -> 'نقّي').
            flat: list[str] = []
            for t in seq:
                if _is_ltrish_token(t):
                    flat.append(t)
                else:
                    flat.extend(t.split())
            flat = _reattach_leading_marks(flat)
            flat = _fuse_arabic_word_fragments(flat)
            seq = flat

            # Merge parenthesised groups spanning several tokens.
            merged: list[str] = []
            i = 0
            while i < len(seq):
                t = seq[i]
                if t.startswith("(") and not t.endswith(")"):
                    grp = [t]
                    j = i + 1
                    closed = False
                    while j < len(seq):
                        grp.append(seq[j])
                        if seq[j].endswith(")") or seq[j] == ")":
                            closed = True
                            break
                        j += 1
                    if closed:
                        merged.append(" ".join(grp))
                        i = j + 1
                        continue
                merged.append(t)
                i += 1
            seq = merged

            seq = _fuse_arabic_word_fragments(seq)
            parts = ([label] if label else []) + seq
            text = " ".join(p for p in parts if p)
            if tail_punct:
                text = f"{text} {tail_punct}".strip()
            if num:
                text = f"{num} {text}".strip()
            text = _rotate_reversed_labels(text)
            text = _fuse_latin_unit_dots(text.split())
            text = " ".join(text)
            text = re.sub(r"\(\s+([^()]+?)\s+\)", r"(\1)", text)
            text = re.sub(r"\)\s*\)$", ")", text)
            text = _RTL_ASSEMBLY_PUNCT_SPACE_RE.sub(r"\1", text)
            text = re.sub(r"\s{2,}", " ", text).strip()
            if text:
                out.append(text)
    return out


PARSER_OCR_VERSION = "v8-source-words-no-translation"
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

    with _OCR_SEMAPHORE, ocr_slot():
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
            # Upscaling beyond native scan detail can damage Arabic OCR.
            # Target 108 DPI, reduced BEFORE allocation to the pixel budget.
            width, height = page.get_size()
            scale = render_scale(width, height, desired=1.5)
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            gray_image = pil_image.convert("L")
            try:
                from app.services.ocr_quality import recognize
                ocr_text = recognize(gray_image, lang=lang)
            finally:
                try:
                    gray_image.close()
                    pil_image.close()
                    bitmap.close()
                    page.close()
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
        except ExtractionLimitError:
            raise
        except RuntimeError as exc:
            raise ExtractionLimitError("OCR timed out or failed; extraction is incomplete") from exc
        except Exception:
            logger.warning(f"OCR fallback failed on page {page_number}")
            raise ExtractionLimitError("OCR failed; extraction is incomplete")
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
        if pdfium_shared is not None:
            if len(pdfium_shared) > MAX_PAGES:
                raise ExtractionLimitError(f"PDF exceeds the {MAX_PAGES}-page extraction limit")
            for index in range(len(pdfium_shared)):
                safe_page = pdfium_shared[index]
                try:
                    render_scale(*safe_page.get_size())
                finally:
                    safe_page.close()
    except ExtractionLimitError:
        if pdfium_shared is not None:
            pdfium_shared.close()
        raise
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
            if total_pages > MAX_PAGES:
                raise ExtractionLimitError(f"PDF exceeds the {MAX_PAGES}-page extraction limit")
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
                page_text_final = False
                if fitz_doc and p_idx - 1 < len(fitz_doc):
                    try:
                        # Coordinate-based line reassembly: span geometry fixes
                        # both storage orders (logical/visual) generically.
                        # Normalize BEFORE the corruption probe: presentation-
                        # forms layers must be judged post-NFKC, otherwise a
                        # healthy legacy text layer gets discarded in favour of
                        # lossy OCR (the root cause of garbled extractions on
                        # exam PDFs written with U+FBxx/FExx glyphs).
                        fitz_text = "\n".join(_assemble_rtl_lines_from_fitz(fitz_doc[p_idx - 1]))
                        fitz_text = normalize_arabic_presentation_forms(fitz_text)
                        if fitz_text and not is_text_garbled(fitz_text):
                            page_text = fitz_text
                            page_text_final = True
                    except Exception as fe:
                        logger.debug(f"fitz text extraction failed on page {p_idx}: {fe}")
                        page_text = ""
                        page_text_final = False

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
                # Pages rebuilt from span geometry are already in reading
                # order: the whole-page fixers are skipped for them (they
                # still run for pdfplumber/OCR fallback text).
                if not page_text_final:
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
                    r"^(.*[\u0600-\u06FF].*)\s*[\(\[]\s*([أبجدA-Da-d1-4]|i|z|s|\)\()\s*[\)\]][\.\:\-]?$"
                )
                QUESTION_HEADER_RE = re.compile(
                    r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)|س\s*\d+|Question\s*\d+|Q\d+|^\(?\d{1,3}\)?\s*[\.\-\:]\s*(?!\d))",
                    re.IGNORECASE,
                )
                SECTION_HEADER_RE = re.compile(
                    r"^\s*\[?\s*(?:القسم\s+(?:الأول|الثاني|الثالث|الرابع)|أسئلة\s+الاختيار|الأسئلة\s+المقالية|أولاً|ثانياً|ثالثاً|انتهت\s+الورق[ةه])\b",
                    re.IGNORECASE,
                )

                lines = [l.strip() for l in page_text.split("\n") if l.strip()]
                for b_idx, line in enumerate(lines):
                    # If this line is an option or answer belonging to the previous question block
                    # (never after a trailer/heading block: RTL column layouts
                    # re-emit 'انتهت الورقة' banners mid-page; an option row
                    # after such a banner belongs to a question in the OTHER
                    # region, not to the banner)
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
                    # (only within the SAME numbered question: a new 'N.' line
                    # always opens its own block so column-layout regions keep
                    # questions separated)
                    if parsed_page.blocks:
                        prev_b = parsed_page.blocks[-1]
                        first_prev_line = prev_b.text.split("\n")[0].strip()
                        prev_num = re.match(r"^(\d{1,3})\s*[.\-:]", first_prev_line)
                        cur_num = re.match(r"^(\d{1,3})\s*[.\-:]", line)
                        same_question = not (prev_num and cur_num and prev_num.group(1) != cur_num.group(1))
                        if (
                            QUESTION_HEADER_RE.match(first_prev_line)
                            and not QUESTION_HEADER_RE.match(line)
                            and not SECTION_HEADER_RE.match(line)
                            and not (line.startswith("#") or line.isupper())
                            and same_question
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
                    # A numbered question line NEVER merges into a previous
                    # non-question block (RTL column layouts split a numbered
                    # stem across a region boundary): '5. مجموع...' after a
                    # trailer/heading line must open a fresh paragraph block,
                    # never append into that trailer.
                    if QUESTION_HEADER_RE.match(line):
                        is_heading = False

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
    check_archive(file_source)

    doc = docx.Document(io.BytesIO(file_source) if isinstance(file_source, bytes) else file_source)
    parsed_doc = ParsedDocument(
        title=os.path.splitext(filename)[0],
        doc_type="docx",
        total_pages=1,
    )

    page = ParsedPage(page_number=1)
    raw_lines: list[str] = []
    OPT_OR_ANS_RE = re.compile(r"^([\(\[]?\s*[أبجدA-Da-d]\s*[\)\]\.\:\-\/]|(?:الإجاب[ةه]|الجواب|الحل|Answer|Key)\b)")

    image_by_rel_id: dict[str, ParsedImage] = {}
    for rel_id, rel in doc.part.rels.items():
        if "image" not in rel.target_ref:
            continue
        try:
            image_bytes = rel.target_part.blob
            image_ocr, ocr_engine = ocr_image_bytes(image_bytes)
            parsed_image = ParsedImage(
                id=f"docx_img_{len(image_by_rel_id)+1}",
                page_number=1,
                asset_kind="figure",
                caption=f"شكل توضيحي في مستند {parsed_doc.title}",
                image_bytes=image_bytes,
                checksum=hashlib.sha256(image_bytes).hexdigest(),
                ocr_text=image_ocr or None,
                ocr_engine=ocr_engine,
            )
            image_by_rel_id[rel_id] = parsed_image
            page.images.append(parsed_image)
            parsed_doc.all_images.append(parsed_image)
        except Exception:
            logger.debug("DOCX image extraction skipped due to part anomaly")

    def append_embedded_ocr(element: Any, block_index: int) -> None:
        from docx.oxml.ns import qn

        for image_index, blip in enumerate(element.xpath(".//a:blip"), start=1):
            image = image_by_rel_id.get(blip.get(qn("r:embed")))
            if image is None or not image.ocr_text:
                continue
            raw_lines.append(image.ocr_text)
            page.blocks.append(ParsedBlock(
                block_id=f"docx_imgocr_{block_index}_{image_index}",
                block_type="paragraph",
                text=image.ocr_text,
                page_number=1,
                media_ids=[image.id],
            ))
            page.extracted_via_ocr = True
            parsed_doc.extracted_via_ocr = True
            parsed_doc.ocr_pages = [1]
            parsed_doc.metadata["ocr_pages"] = [1]

    # Walk the body in source order.  doc.paragraphs/doc.tables are separate
    # collections and lose every question placed inside a layout table.
    for idx, item in enumerate(doc.iter_inner_content()):
        if isinstance(item, docx.table.Table):
            table_rows = [[cell.text.strip() for cell in row.cells] for row in item.rows]
            table_rows = [row for row in table_rows if any(row)]
            if not table_rows:
                continue
            table_text = "\n".join(" | ".join(row) for row in table_rows)
            parsed_table = ParsedTable(
                page_number=1,
                headers=table_rows[0],
                rows=table_rows[1:],
                raw_text=table_text,
            )
            page.tables.append(parsed_table)
            parsed_doc.all_tables.append(parsed_table)
            raw_lines.extend(" | ".join(row) for row in table_rows)
            # Single-column tables are often Word layout wrappers for a
            # normal question/option sequence, not tabular question banks.
            if max(len(row) for row in table_rows) == 1:
                page.blocks.append(ParsedBlock(
                    block_id=f"docx_table_{idx+1}",
                    block_type="paragraph",
                    text="\n".join(row[0] for row in table_rows),
                    page_number=1,
                ))
            append_embedded_ocr(item._element, idx + 1)
            continue

        p = item
        text = p.text.strip()
        if not text:
            append_embedded_ocr(p._element, idx + 1)
            continue
        raw_lines.append(text)

        # If this paragraph is an option or answer belonging to the previous question block
        if page.blocks and page.blocks[-1].block_type != "heading" and OPT_OR_ANS_RE.match(text):
            page.blocks[-1].text += "\n" + text
            append_embedded_ocr(p._element, idx + 1)
            continue

        # If this paragraph is a chemical equation belonging to the previous explanatory sentence
        if page.blocks and is_chemical_equation_line(text):
            prev_text = page.blocks[-1].text.strip()
            intro_phrases = ["وفق المعادلة", "بالمعادلة", "كما يلي", "التفاعل التالي", "المعادلة الكيميائية", "المعادلة التالية", "المعادلة:"]
            if prev_text.endswith(":") or any(ip in prev_text for ip in intro_phrases):
                page.blocks[-1].text += "\n" + text
                append_embedded_ocr(p._element, idx + 1)
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
        append_embedded_ocr(p._element, idx + 1)

    page.raw_text = "\n".join(raw_lines)
    parsed_doc.pages.append(page)
    return parsed_doc


# =============================================================================
# 3. PPTX PARSER (python-pptx)
# =============================================================================

def parse_pptx_document(file_source: bytes | str, filename: str) -> ParsedDocument:
    """Parses a PowerPoint PPTX presentation, preserving slides, titles, notes, and diagrams."""
    import pptx

    check_archive(file_source)
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
    try:
        check_image(img)
        width, height = img.size
    finally:
        img.close()
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
        width=width,
        height=height,
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
    """Bounded local OCR; resource failures never masquerade as empty success."""
    if not image_bytes:
        return "", None
    if os.getenv("ALLOW_IN_PROCESS_OCR", "true").strip().lower() in ("false", "0", "no"):
        raise ExtractionLimitError("OCR is disabled by configuration")
    import pytesseract
    from app.core.config import get_tesseract_cmd

    get_tesseract_cmd()
    with _OCR_SEMAPHORE, ocr_slot():
        try:
            with Image.open(io.BytesIO(image_bytes)) as source:
                check_image(source)
                source.thumbnail((MAX_RENDER_SIDE, MAX_RENDER_SIDE))
                # Bound area as well as the longest side before converting.
                scale = min(1.0, (MAX_RENDER_PIXELS / (source.width * source.height)) ** 0.5)
                if scale < 1:
                    source.thumbnail((max(1, int(source.width * scale)), max(1, int(source.height * scale))))
                gray = ImageOps.grayscale(source)
                try:
                    image = ImageOps.autocontrast(gray)
                    try:
                        from app.services.ocr_quality import recognize
                        text = recognize(image, lang=lang)
                    finally:
                        image.close()
                finally:
                    gray.close()
            return clean_arabic_ocr_text(text), "tesseract-ara+eng"
        except ExtractionLimitError:
            raise
        except Exception as exc:
            raise ExtractionLimitError("Image OCR failed or timed out; extraction is incomplete") from exc


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
