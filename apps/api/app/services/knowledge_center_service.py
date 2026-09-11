"""
=============================================================================
AI TEACHING KNOWLEDGE CENTER — INGESTION & KNOWLEDGE SERVICE
=============================================================================
Handles source file uploads, structure-preserving document parsing, Knowledge Unit
extraction, media asset indexing, assessment bank ingestion, idempotent reindexing,
and safe source deletion.
=============================================================================
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.course import Course, Lesson
from app.models.knowledge_center import (
    AssessmentQuestion,
    AssessmentSource,
    KnowledgeAsset,
    KnowledgeConceptLink,
    KnowledgeConceptRelation,
    KnowledgeDocument,
    KnowledgeLessonRelation,
    KnowledgeOutlineNode,
    KnowledgeQuestionImageLink,
    KnowledgeQuestionRecord,
    KnowledgeSource,
    KnowledgeUnitRecord,
    SourceRole,
    SourceStatus,
)
from app.models.user import User
from app.services.document_parsers import (
    ParsedAssessmentQuestion,
    ParsedDocument,
    ParsedTable,
    parse_assessment_bank,
    parse_knowledge_file,
    clean_arabic_ocr_text,
    is_text_garbled,
)
from app.services.educational_normalizer import (
    KnowledgeUnit,
    clean_spoken_noise,
    reconstruct_educational_statement,
)
from app.services.semantic_rewriter import invoke_llm_semantic_rewriting, verify_semantic_faithfulness
from app.services.embedding_provider import get_embedding_provider
from app.services.exam_processing import materialize_assessment_questions
from app.services.book_outline import materialize_book_outline, materialize_lesson_relations, outline_node_for_page
from app.services.vision_language import analyze_educational_image
from app.services.knowledge_graph import build_source_knowledge_graph
from app.services.content_safety import sanitize_retrieval_text
from app.services.vector_store import upsert_knowledge_vectors
from app.services.formula_validation import extract_and_validate_formulas
from app.services.question_image_linker import ImageMatch, select_question_images

STORAGE_DIR = os.getenv("STORAGE_DIR", "storage/knowledge_center")
SEMANTIC_CONFIDENCE_THRESHOLD = float(os.getenv("SEMANTIC_CONFIDENCE_THRESHOLD", "0.65"))
logger = logging.getLogger(__name__)


def _compute_checksum(data: bytes) -> str:
    """Compute SHA256 checksum for source file duplicate detection."""
    return hashlib.sha256(data).hexdigest()


KEY_SECTION_PATTERNS = [
    r"نموذج\s+(?:ال)?(?:[اإأ]جاب[ةه]|[اإأ]جابات|حل)",
    r"مفتاح\s+(?:ال)?(?:[اإأ]جاب[ةه]|[اإأ]جابات|حل)",
    r"(?:ال)?(?:[اإأ]جابات)\s+(?:النموذجي[ةه]|النهائي[ةه]|الصحيح[ةه])",
    r"[اإأ]جابات\s+(?:الأسئل[ةه]|الاختبار|الامتحان)",
    r"حلول\s+(?:الأسئل[ةه]|الاختبار|الامتحان)",
    r"answer\s*key",
    r"answers\s*:",
    r"solutions\s*:",
]

ADMINISTRATIVE_METADATA_PATTERNS = [
    # 1. Ministry, Government & Department Entities
    r"وزار[ةه]\s+التربي[ةه]\s+(?:و\s*)?التعليم",
    r"وزار[ةه]\s+التعليم\s+العالي",
    r"جمهوري[ةه]\s+مصر\s+العربي[ةه]",
    r"قطاع\s+الكتب",
    r"[اإأآ]دار[ةه]\s+مركزي[ةه]",
    r"[اإأآ]ل?ادارة\s+المركزية",
    r"(?:مكتب|مستشار)\s+مستشار",
    r"مركز\s+تطوير\s+المناهج",
    r"مدير\s+عام\s+تنمي[ةه]\s+ماد[ةه]",
    
    # 2. Editorial Committee, Supervisory & Authorship roles
    r"[اإأآ]شراف\s+(?:عام|علمي|علمى|تربوي|تربوى|فني)?",
    r"توجيه\s+فني",
    r"لجن[ةه]\s+(?:[اإأآ]عداد|تأليف|مراجع[ةه]|تعديل|تطوير)",
    r"فريق\s+العمل",
    r"(?:المراجع[ةه]|التعديل)\s+(?:العلمي[ةه]|التربوي[ةه]|والتعديل)",
    r"مستشار\s+ماد[ةه]",
    r"خبير\s+المناهج",
    r"تصميم\s+الغلاف",
    
    # 3. Academic titles followed by names (committee member credits)
    r"(?:^|\s)(?:أ\.د|دكتور|الأستاذ\s+الدكتور)\s+[\u0621-\u064A]{2,}",
    r"(?:^|\s)(?:أستاذ|أستاذة)\s+[\u0621-\u064A]{2,}\s+[\u0621-\u064A]{2,}",

    # 4. Copyright, Printing, ISBN, & Publishing Houses
    r"حقوق\s+(?:الطبع|النشر|الملكي[ةه])\s+محفوظ[ةه]",
    r"جميع\s+الحقوق\s+محفوظ[ةه]",
    r"رقم\s+الإيداع|الترقيم\s+الدولي|ISBN\b",
    r"دار\s+(?:المطابع|الطباع[ةه]|النشر)|مطابع\s+|طبعت\s+بـ|مطابع\s+الأهرام|مطابع\s+الشرط[ةه]",
    r"العام\s+الدراسي\s*\d{4}|طبع[ةه]\s*\d{4}|غير\s+مصرح\s+بتداول",

    # 5. Book Introductions, Table of Contents, and Pedagogical Objectives
    r"بسم\s+الله\s+الرحمن\s+الرحيم",
    r"مقدم[ةه]\s+(?:الكتاب|المنهج|المقرر|الطبع[ةه])|^\s*مقدمة\s*$",
    r"(?:^|\s)تصدير\b",
    r"(?:^|\s)(?:فهرس|محتويات\s+الكتاب|قائم[ةه]\s+المحتويات|دليل\s+المعلم)",
    r"الأهداف\s*:\s*بعد\s+الانتهاء|بعد\s+الانتهاء\s+من\s+دراسة\s+هذا\s+(?:الباب|الفصل|الدرس)",
    r"يصبح\s+الطالب\s+قادراً\s+على\s+أن|يتوقع\s+من\s+الطالب\s+أن",

    # 6. Existing exam headers & download watermarks
    r"^(?:امتحان|اختبار|ورق[ةه]\s+عمل|تدريب|بنك\s+أسئل[ةه]|كويز|quiz|exam|test)\b",
    r"الفصل\s+الدراسي\s+(?:الأول|الثاني|الصيفي)",
    r"الصف\s+(?:الأول|الثاني|الثالث)\s+الثانوي",
    r"مقرر\s+.*\s+امتحان\s+شامل",
    r"^\s*===.*===\s*$",
    r"(?:تم\s+تحميل|موقع\s+وتطبيق|مذكرات\s+جاهزة|حمل\s+المزيد|جروب\s+تليجرام|قناة\s+تليجرام)",
]
EXCLUDED_METADATA_PATTERNS = ADMINISTRATIVE_METADATA_PATTERNS

NARRATIVE_PREFIXES = [
    r"^(?:إذا|لو|حيث|بينما|كما|وقد|لذلك|وبالتالي|فإن|نلاحظ|ومن\s+هنا|وجدير\s+بالذكر)\b",
    r"^(?:وقبل\s+أن|وعندما|وحين|ومع\s+ذلك|وهذا\s+السؤال|هذا\s+السؤال)\b",
]

BLOOM_OBJECTIVE_PATTERNS = [
    r"الأ[هص]داف\s*:",
    r"يصبح\s+الطالب\s+قادراً",
    r"يتوقع\s+من\s+الطالب",
    r"\b(?:يكتب|يذكر|يقارن|يتعرف|يرسم|يحدد|يستنتج|يوضح|يميز|يعدد|يحلل)\s+(?:تعريف|أفرع|علاقة|بين|على|تخطيط|مكونات|أهمية|أنواع|خصائص|ميدانياً|عدم\s+التوافق)",
    r"المصطلحات\s+المستخدمة\s+فى\s+وصفهما",
]



def extract_distant_answer_keys(parsed_doc: Any) -> dict[str, str]:
    """
    Scans document for distant answer-key sections (e.g. at the end of an exam).
    Returns mapping from question number (e.g. '1', '2', 'س1', 'q1') to answer text/letter.
    """
    keys_map: dict[str, str] = {}
    is_in_answer_key_section = False

    blocks_text: list[str] = []
    if isinstance(parsed_doc, str):
        blocks_text = [parsed_doc]
    elif hasattr(parsed_doc, "pages"):
        for page in parsed_doc.pages:
            for block in getattr(page, "blocks", []):
                blocks_text.append(getattr(block, "text", ""))
    elif isinstance(parsed_doc, list):
        blocks_text = [str(x) for x in parsed_doc]

    for text in blocks_text:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            if any(re.search(pat, line, re.IGNORECASE) for pat in KEY_SECTION_PATTERNS):
                is_in_answer_key_section = True
                continue

            if is_in_answer_key_section:
                line_norm = line.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
                matches = re.findall(
                    r"(?:س|q|question)?\s*\(?(\d+)\)?\s*[\:\.\-\)]\s*\(?([أ-دA-Da-d]|[^\n\r\,\;]{1,100})\)?",
                    line_norm,
                    re.IGNORECASE,
                )
                for q_num, ans in matches:
                    clean_ans = ans.strip(" ()[].,:-")
                    if clean_ans:
                        keys_map[q_num] = clean_ans
                        keys_map[f"س{q_num}"] = clean_ans
                        keys_map[f"q{q_num}"] = clean_ans

    return keys_map


def resolve_correct_answer_text(
    options: list[dict[str, Any]] | None,
    answer_raw: str | None,
) -> tuple[str | None, bool]:
    """
    Converts letter answer keys (e.g. 'ج' or 'A') to the actual full text of the corresponding option.
    Marks is_correct=True on the matching option in options list.
    Returns (resolved_text, needs_review).
    """
    if not answer_raw:
        return (None, True)

    clean_ans = answer_raw.strip().strip("().,:- ")
    if not clean_ans:
        return (None, True)

    if not options:
        return (clean_ans, False)

    AR_TO_LATIN = {"أ": "A", "ب": "B", "ج": "C", "د": "D", "ا": "A"}
    LATIN_TO_AR = {"A": "أ", "B": "ب", "C": "ج", "D": "د"}

    norm_key = clean_ans.upper()
    alt_key = AR_TO_LATIN.get(clean_ans, LATIN_TO_AR.get(norm_key, clean_ans))

    # Match by key or alternative key
    for opt in options:
        opt_k = opt.get("key", "").strip()
        if opt_k.lower() in (clean_ans.lower(), norm_key.lower(), alt_key.lower()):
            opt["is_correct"] = True
            return (opt.get("text", clean_ans), False)

    # Match by text substring/equality
    for opt in options:
        opt_text = opt.get("text", "").strip().lower()
        if opt_text == clean_ans.lower() or (len(clean_ans) > 2 and clean_ans.lower() in opt_text):
            opt["is_correct"] = True
            return (opt.get("text", clean_ans), False)

    # If answer provided could not be matched with confidence, flag for teacher review
    return (clean_ans, True)


def is_question_table(headers: list[Any], rows: list[list[Any]]) -> bool:
    """
    Strict positive check: returns True only if table positively exhibits question/exam structure.
    Never treats descriptive tables (reference values, instruments, comparisons) as questions.
    """
    if not rows or len(rows) == 0:
        return False

    header_str = " ".join(str(h) for h in headers).lower()
    has_q_header = any(k in header_str for k in ["سؤال", "السؤال", "question"])
    has_opt_header = any(k in header_str for k in ["خيارات", "options", "بدائل"])
    has_ans_header = any(w in header_str for w in ["إجاب", "اجاب", "حل", "answer", "key"])
    has_letter_headers = sum(1 for h in headers if str(h).strip().upper() in ["أ", "ب", "ج", "د", "A", "B", "C", "D"]) >= 2

    # Positive signal 1: Header has question keyword AND (options/answer keyword OR letter columns)
    if has_q_header and (has_opt_header or has_ans_header or has_letter_headers):
        return True

    # Positive signal 2: Columns are explicitly labeled as multiple-choice letters
    if has_letter_headers and len(headers) >= 3:
        return True

    # Positive signal 3: Row questions explicitly contain Arabic question mark '؟' or '?' with 4+ words in first cell
    q_cell_count = sum(1 for r in rows if len(r) >= 2 and any(qm in str(r[0] if not str(r[0]).isdigit() else r[1]) for qm in ["؟", "?"]) and len(str(r[0]).split()) >= 4)
    if q_cell_count >= 2 and (has_opt_header or has_ans_header or len(headers) >= 4):
        return True

    return False


def parse_table_questions(
    tables_or_doc: Any,
    distant_keys: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Extracts questions structured as tables (e.g. columns for Question, Options, and Answer).
    Reuses parsed_doc.all_tables.
    """
    distant_keys = distant_keys or {}
    extracted_questions: list[dict[str, Any]] = []

    if hasattr(tables_or_doc, "all_tables"):
        tables_list = tables_or_doc.all_tables
    elif isinstance(tables_or_doc, list):
        tables_list = tables_or_doc
    else:
        tables_list = []

    for table in tables_list:
        rows = table.get("rows", []) if isinstance(table, dict) else getattr(table, "rows", [])
        headers = table.get("headers", []) if isinstance(table, dict) else getattr(table, "headers", [])
        page_num = table.get("page_number") if isinstance(table, dict) else getattr(table, "page_number", None)
        slide_num = table.get("slide_number") if isinstance(table, dict) else getattr(table, "slide_number", None)

        if not rows:
            continue

        if not is_question_table(headers, rows):
            continue

        # Find dedicated answer column if any
        ans_col_idx: int | None = None
        for c_idx, h in enumerate(headers):
            if any(w in str(h).lower() for w in ["إجاب", "اجاب", "حل", "answer", "key"]):
                ans_col_idx = c_idx
                break

        for r_idx, row in enumerate(rows):
            if not row or len(row) < 2:
                continue

            first_cells_text = " ".join(str(c) for c in row[:2])
            if len(first_cells_text.split()) < 3 and not any(k in first_cells_text for k in ["؟", "?", "س", "q"]):
                continue

            q_text = str(row[1]) if len(row) > 2 and str(row[0]).strip().isdigit() else str(row[0])
            if len(q_text.strip().split()) < 3:
                continue

            options: list[dict[str, Any]] = []
            opt_keys = ["أ", "ب", "ج", "د"]
            start_opt_idx = 2 if len(row) > 2 and str(row[0]).strip().isdigit() else 1

            raw_answer: str | None = None
            if ans_col_idx is not None and ans_col_idx < len(row):
                raw_answer = str(row[ans_col_idx]).strip()

            for col_i in range(start_opt_idx, len(row)):
                if col_i == ans_col_idx:
                    continue
                cell_clean = str(row[col_i]).strip()
                if not cell_clean:
                    continue
                if not raw_answer and any(cell_clean.startswith(p) for p in ["الإجابة", "الحل", "Answer", "Key"]):
                    raw_answer = cell_clean.split(":", 1)[-1].strip()
                    continue
                k = opt_keys[len(options)] if len(options) < len(opt_keys) else str(len(options) + 1)
                options.append({"key": k, "text": cell_clean, "is_correct": False})

            q_num_match = re.search(r"\(?(\d+)\)?", str(row[0]))
            q_num = q_num_match.group(1) if q_num_match else str(r_idx + 1)

            if not raw_answer and q_num in distant_keys:
                raw_answer = distant_keys[q_num]

            corr_text, needs_rev = resolve_correct_answer_text(options, raw_answer)

            extracted_questions.append({
                "question_text": q_text.strip(),
                "question_type": "multiple_choice" if len(options) >= 2 else "essay",
                "options": options if options else None,
                "correct_answer": corr_text,
                "page_number": page_num,
                "slide_number": slide_num,
                "classification_confidence": "high" if (q_text.endswith("؟") or q_text.endswith("?") or len(options) >= 2) else "uncertain",
                "needs_answer_review": needs_rev,
                "raw_text": " | ".join(str(c) for c in row),
            })

    return extracted_questions


def classify_and_parse_question(
    text: str,
    distant_keys: dict[str, str] = {},
) -> tuple[str, dict[str, Any] | None]:
    """
    Classifies a text block into: 'question', 'uncertain', or 'content'.
    If 'question' or 'uncertain', extracts question_text, options, correct_answer.
    Robust against OCR artifacts, spacing variations, and narrative paragraph filtering.
    """
    # Strip Unicode directional marks (RLM, LRM, etc.) that OCR often prepends
    clean_t = re.sub(r"[\u200e\u200f\u202a-\u202e\ufeff]", "", text).strip()
    if not clean_t:
        return ("content", None)

    # 1. Reject PDF binary/internal corruption tokens (Requirement 1 & 8)
    PDF_CORRUPTION_TOKENS = [
        "obj", "endobj", "stream", "endstream", "FlateDecode",
        "/Type", "/Pages", "/Resources", "/Font", "/Contents",
        "/ProcSet", "/ImageB", "/ImageC", "/ImageI"
    ]
    if any(tok in clean_t for tok in ["FlateDecode", "endobj", "endstream", "/Type /Page", "/Resources", "/Contents"]) or any(
        re.search(r"(?:^|[\s/])" + re.escape(tok.lstrip("/")) + r"(?:[\s/]|$)", clean_t) for tok in PDF_CORRUPTION_TOKENS
    ):
        return ("content", None)

    # 2. Reject Frontend UI tokens (Requirement 8 & 10)
    FRONTEND_UI_TOKENS = [
        "اختيار من متعدد (MCQ)", "صح أو خطأ (True/False)",
        "سؤال مقالي (Essay)", "أكمل الفراغات (Fill in the blank)",
        "حفظ التعديل", "الدرجة:", "svg"
    ]
    if any(tok in clean_t for tok in FRONTEND_UI_TOKENS):
        cleaned_no_ui = clean_t
        for tok in FRONTEND_UI_TOKENS:
            cleaned_no_ui = cleaned_no_ui.replace(tok, "")
        if len(cleaned_no_ui.strip().split()) < 3:
            return ("content", None)

    # Exclude dedicated answer key header blocks
    if any(re.search(pat, clean_t, re.IGNORECASE) for pat in KEY_SECTION_PATTERNS):
        return ("content", None)

    # Exclude administrative metadata, publishers, committee credits, and pedagogical objectives
    if any(re.search(pat, clean_t, re.IGNORECASE) for pat in ADMINISTRATIVE_METADATA_PATTERNS):
        return ("content", None)

    # Exclude narrative paragraph transitions (e.g. "إذا تأملنا في حياتنا...", "وقبل أن نجيب...")
    if any(re.search(pat, clean_t) for pat in NARRATIVE_PREFIXES):
        return ("content", None)

    # Exclude Bloom's taxonomy objectives
    if any(re.search(pat, clean_t, re.IGNORECASE) for pat in BLOOM_OBJECTIVE_PATTERNS):
        return ("content", None)

    norm_t = clean_t.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

    STRONG_QUESTION_START = [
        r"^(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)",
        r"^س\s*\d+\s*[\:\.\-\)]",
        r"^(?:Question|Q)\s*\d+\s*[\:\.\-\)]",
        r"^\(?\d+\)?\s*[\.\-\)]\s+.*\b(?:ما|ماذا|علل|بم\s+تفسر|وضح|اختر|قارن|اذكر|عرف|كيف|متى|أين|هل|أي\s+مما\s+يلي|يعتبر|يعد|تعتبر)\b",
    ]

    is_strong_q = any(re.search(pat, norm_t, re.IGNORECASE) for pat in STRONG_QUESTION_START)
    has_q_mark = ("؟" in clean_t or "?" in clean_t)
    ends_with_q_mark = clean_t.endswith("؟") or clean_t.endswith("?")

    lines = [l.strip() for l in clean_t.split("\n") if l.strip()]
    if lines and all(bool(re.match(r"^\(?\d+\)?\s*[\:\.\-\)]\s*[أ-دA-Da-d]\b", l)) for l in lines):
        return ("content", None)

    option_lines: list[tuple[str, str]] = []
    question_lines: list[str] = []
    answer_raw: str | None = None

    # Key normalization dictionary
    KEY_NORM = {
        'i': 'أ', '1': 'أ', 'a': 'أ', 'A': 'أ', 'أ': 'أ', 'ا': 'أ', 'ع': 'أ',
        '2': 'ب', 'b': 'ب', 'B': 'ب', 'ب': 'ب',
        'z': 'ج', '3': 'ج', 'c': 'ج', 'C': 'ج', 'ج': 'ج',
        '4': 'د', 'd': 'د', 'D': 'د', 'د': 'د', 's': 'د', ')(': 'د'
    }

    # OCR-tolerant patterns allowing prefix and suffix delimiters
    OPT_PATTERN = re.compile(r"^[\(\[]?\s*([أ-دA-Da-d1-4]|i|z|s|\)\()\s*[\)\]\.\:\-\/]\s*(.*)$")
    OPT_SUFFIX_PATTERN = re.compile(r"^(.*?)\s*[\(\[]\s*([أ-دA-Da-d1-4]|i|z|s|\)\()\s*[\)\]][\.\:\-]?$")
    ANS_PATTERN = re.compile(
        r"^(?:الإجاب[ةه](?:\s+الصحيح[ةه])?|الجواب(?:\s+الصحيح)?|الحل(?:\s+الصحيح)?|فكرة\s+الحل|Answer|Key)\s*[\:\.\-\/]?\s*(.*)$",
        re.IGNORECASE,
    )
    INLINE_OPT_PATTERN = re.compile(
        r"(?:^|\s+)[\(\[]?\s*([أ-دA-D1-4]|i|z)\s*[\)\]\.\:\-\/]\s*(.*?)(?=(?:\s+[\(\[]?\s*[أ-دA-D1-4]|i|z\s*[\)\]\.\:\-\/]|$))"
    )

    for idx, line in enumerate(lines):
        ans_match = ANS_PATTERN.match(line)
        if ans_match:
            raw_val = ans_match.group(1).strip()
            raw_val = re.sub(r"^(?:الصحيح[ةه]|الصواب)\s*[\:\.\-]?\s*", "", raw_val, flags=re.IGNORECASE).strip()
            answer_raw = raw_val.lstrip(":.-/ ").strip()
            continue

        # Check inline options first (e.g. "(أ) ... (ب) ...")
        inline_opts = INLINE_OPT_PATTERN.findall(line)
        if len(inline_opts) >= 2:
            for k, txt in inline_opts:
                norm_k = KEY_NORM.get(k, k)
                option_lines.append((norm_k, txt.strip()))
            continue

        opt_match = OPT_PATTERN.match(line)
        opt_suffix_match = OPT_SUFFIX_PATTERN.match(line)

        # Check single-line prefix option
        if idx > 0 and opt_match and len(line.split()) < 25:
            norm_k = KEY_NORM.get(opt_match.group(1), opt_match.group(1))
            option_lines.append((norm_k, opt_match.group(2).strip()))
        # Check single-line suffix option (common in RTL/OCR)
        elif idx > 0 and opt_suffix_match and len(line.split()) <= 15:
            norm_k = KEY_NORM.get(opt_suffix_match.group(2), opt_suffix_match.group(2))
            option_lines.append((norm_k, opt_suffix_match.group(1).strip()))
        else:
            question_lines.append(line)

    has_options = len(option_lines) >= 2
    q_stem = "\n".join(question_lines).strip()

    # Reject blocks that are ONLY a header without question stem or options (Requirement 1 & 8)
    HEADER_ONLY_PATTERN = re.compile(
        r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)|س\s*\d+|Question\s*\d+|Q\d+)\s*[\:\.\-\)]?\s*(?:\(?\s*\d+\s*(?:درجات|درجة|marks?|pts?)\s*\)?)?$",
        re.IGNORECASE,
    )
    if not has_options and (HEADER_ONLY_PATTERN.match(clean_t.strip()) or HEADER_ONLY_PATTERN.match(q_stem.strip())):
        return ("content", None)

    # Reject blocks that have no question stem and no question mark (e.g. answer key pairs)
    if len(q_stem.split()) < 2 and not (has_q_mark and len(clean_t.split()) >= 3):
        return ("content", None)

    has_digit_q_start = bool(re.match(r"^\(?\d+\)?\s*[\.\-\)]\s+.*\b(?:ما|ماذا|علل|بم\s+تفسر|وضح|اختر|قارن|اذكر|عرف|كيف|متى|أين|هل|أي\s+مما\s+يلي|احسب|ما\s+النتائج)\b", norm_t, re.IGNORECASE))
    if has_digit_q_start or (has_options and (answer_raw or len(option_lines) >= 3)):
        is_strong_q = True

    q_num_match = re.search(r"^(?:السؤال|سؤال|س|q|question)?\s*\(?(\d+)\)?", norm_t, re.IGNORECASE)
    if not q_num_match or not q_num_match.group(1):
        q_num_match = re.search(r"(?:السؤال|سؤال|س|q|question)\s*\(?(\d+)\)?", norm_t, re.IGNORECASE)
    q_num = q_num_match.group(1) if q_num_match else None

    if not answer_raw and q_num and q_num in distant_keys:
        answer_raw = distant_keys[q_num]

    formatted_options = [
        {"key": k, "text": txt, "is_correct": False}
        for k, txt in option_lines
    ]

    corr_answer_text, needs_rev = resolve_correct_answer_text(formatted_options, answer_raw)

    # Extract marks if present
    marks_m = re.search(r"[\(\[]\s*(\d+)\s*(?:درجات|درجة|علامات|علامة|marks?|pts?)\s*[\)\]]", clean_t, re.IGNORECASE)
    extracted_points = int(marks_m.group(1)) if marks_m else 5

    # Determine Canonical Question Type (Requirement 4)
    if has_options:
        primary_q_type = "multiple_choice"
        canonical_q_type = "MCQ"
    elif any(w in clean_t for w in ["صح أم خطأ", "ضع علامة", "True/False", "صواب أم خطأ", "صح أو خطأ", "true", "false"]):
        primary_q_type = "true_false"
        canonical_q_type = "TRUE_FALSE"
    elif any(w in clean_t for w in ["أكمل الفراغ", "أكمل ما يأتي", "أكمل العبارات", "Fill in the blank"]):
        primary_q_type = "fill_in_blank"
        canonical_q_type = "FILL_BLANK"
    else:
        primary_q_type = "essay"
        canonical_q_type = "ESSAY"

    if is_strong_q or (has_q_mark and has_options):
        return ("question", {
            "question_text": q_stem or clean_t,
            "question_type": primary_q_type,
            "canonical_type": canonical_q_type,
            "options": formatted_options if formatted_options else None,
            "correct_answer": corr_answer_text,
            "points": extracted_points,
            "classification_confidence": "high",
            "needs_answer_review": needs_rev,
            "raw_text": clean_t,
        })
    elif (ends_with_q_mark and len(clean_t.split()) <= 150 and not any(re.search(p, clean_t) for p in NARRATIVE_PREFIXES)) or (has_options and len(q_stem.split()) >= 3):
        return ("uncertain", {
            "question_text": q_stem or clean_t,
            "question_type": primary_q_type,
            "canonical_type": canonical_q_type,
            "options": formatted_options if formatted_options else None,
            "correct_answer": corr_answer_text,
            "points": extracted_points,
            "classification_confidence": "uncertain",
            "needs_answer_review": True,
            "raw_text": clean_t,
        })
    else:
        return ("content", None)


def assemble_document_questions(
    parsed_doc: ParsedDocument,
    distant_keys: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Robust multi-line document question assembler.
    Accumulates multi-line question headers, stems, continuations, options across
    lines and page breaks, extracts marks/points, and associates visual assets.
    """
    distant_keys = distant_keys or {}
    questions: list[dict[str, Any]] = []

    CORRUPTION_TOKENS = [
        "obj", "endobj", "stream", "endstream", "FlateDecode",
        "/Type", "/Pages", "/Resources", "/Font", "/Contents",
        "/ProcSet", "/ImageB", "/ImageC", "/ImageI"
    ]
    UI_TOKENS = [
        "تعديل", "حفظ التعديل", "الدرجة:",
        "اختيار من متعدد (MCQ)", "صح أو خطأ (True/False)",
        "سؤال مقالي (Essay)", "أكمل الفراغات (Fill in the blank)",
        "svg"
    ]

    HEADER_RE = re.compile(
        r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)|س\s*\d+|Question\s*\d+|Q\d+)\b",
        re.IGNORECASE,
    )
    MARKS_RE = re.compile(r"[\(\[]\s*(\d+)\s*(?:درجات|درجة|علامات|علامة|marks?|pts?)\s*[\)\]]", re.IGNORECASE)
    SECTION_RE = re.compile(r"^\s*\[?\s*(?:القسم\s+(?:الأول|الثاني|الثالث|الرابع)|أسئلة\s+الاختيار|الأسئلة\s+المقالية|أولاً|ثانياً|ثالثاً)\b", re.IGNORECASE)
    ANS_RE = re.compile(r"^(?:فكرة\s+الحل|الحل(?:\s+الصحيح)?|الإجاب[ةه](?:\s+الصحيح[ةه])?|الجواب|Answer|Key)\s*[\:\.\-]?\s*(.*)$", re.IGNORECASE)
    EXAM_END_RE = re.compile(r"(?:مع\s+أطيب\s+التمنيات|انتهت\s+الأسئلة|مع\s+تمنياتنا|بالتوفيق|ﺔﻠﺌﺳألا\s+ﺖﻬﺘﻧا|\.{5,}|={5,})", re.IGNORECASE)

    KEY_NORM = {
        'i': 'أ', '1': 'أ', 'a': 'أ', 'A': 'أ', 'أ': 'أ', 'ا': 'أ', 'ع': 'أ',
        '2': 'ب', 'b': 'ب', 'B': 'ب', 'ب': 'ب',
        'z': 'ج', '3': 'ج', 'c': 'ج', 'C': 'ج', 'ج': 'ج',
        '4': 'د', 'd': 'د', 'D': 'د', 'د': 'د', 's': 'د', ')(': 'د'
    }

    OPT_PREFIX_RE = re.compile(r"^[\(\[]+\s*([أ-دA-Da-d1-4]|i|z|s|\)\()\s*[\)\]\.\:\-\/]+\s*(.*)$")
    OPT_SUFFIX_RE = re.compile(r"^(.*?)\s*[\(\[]+\s*([أ-دA-Da-d1-4]|i|z|s|\)\()\s*[\)\]]+[\.\:\-]?$")
    OPT_ANY_RE = re.compile(r"(?:^|\s)[\(\[]+\s*([أ-دA-Da-d1-4]|i|z|s|\)\()\s*[\)\]]+(?:\s|$)")

    DIGIT_START_RE = re.compile(r"^\(?(\d{1,2})\)?[\.\-\:\)]\s+(.*)$")
    DIGIT_END_RE = re.compile(r"^(.*?)\s+[\.\-\:]?\s*(\d{1,2})[\.\-\:]?$")

    def _parse_opt(line: str) -> tuple[str, str] | None:
        l_c = line.strip()
        if not l_c or len(l_c.split()) > 25:
            return None
        # mirrored bracket suffix like )1( or )أ( or (د) or (د))
        m = re.match(r"^(.*?)\s*[\(\)\[\]]+\s*([أ-دA-Da-d1-4]|i|z|s)\s*[\(\)\[\]]+[\.\:\-]?$", l_c)
        if m and len(m.group(1).split()) <= 25:
            k = KEY_NORM.get(m.group(2), m.group(2))
            return (k, m.group(1).strip())
        # number letter bracket like 3ب)
        m = re.match(r"^(.+?)\s*([أ-د])[\)\]]+$", l_c)
        if m:
            return (m.group(2), m.group(1).strip())
        # suffix with )(
        if l_c.endswith(")("):
            return ("د", l_c[:-2].strip())
        # prefix like (i) or (1) or (أ)
        m = re.match(r"^[\(\)\[\]]+\s*([أ-دA-Da-d1-4]|i|z|s)\s*[\(\)\[\]\.\:\-\/]+\s*(.*)$", l_c)
        if m:
            return (KEY_NORM.get(m.group(1), m.group(1)), m.group(2).strip())
        m = OPT_ANY_RE.search(l_c)
        if m and not l_c.startswith("السؤال"):
            raw_k = m.group(1)
            k = KEY_NORM.get(raw_k, raw_k)
            txt = l_c[:m.start()] + " " + l_c[m.end():]
            txt = re.sub(r"\s+", " ", txt).strip()
            return (k, txt)
        return None

    cur_header = ""
    cur_stem_lines: list[str] = []
    cur_options: list[dict[str, Any]] = []
    cur_answer = ""
    cur_explanation = ""
    cur_points = 5
    cur_page = 1
    cur_images: list[str] = []
    is_essay_mode = False

    def flush():
        nonlocal cur_header, cur_stem_lines, cur_options, cur_answer, cur_explanation, cur_points, cur_page, cur_images
        stem = "\n".join(cur_stem_lines).strip()
        full_text = cur_header + ("\n" + stem if stem else "") if cur_header else stem
        full_text = full_text.strip()
        if not full_text:
            _reset()
            return

        # 1. Reject if question text is ONLY a header (Requirement 1 & 8)
        if not cur_stem_lines and HEADER_RE.match(full_text) and len(full_text.split()) <= 6:
            return
        # 2. Reject admin metadata
        if any(re.search(p, full_text, re.IGNORECASE) for p in ADMINISTRATIVE_METADATA_PATTERNS) or re.search(r"^(?:جمهورية|وزارة|امتحان\s+شهادة|الزمن\s*:|الدرجة\s+العظمى)", full_text):
            _reset()
            return
        # 3. Reject PDF corruption tokens
        if any(tok in full_text for tok in CORRUPTION_TOKENS):
            _reset()
            return
        # 4. Reject frontend UI tokens
        if any(tok in full_text for tok in UI_TOKENS):
            _reset()
            return
        # 5. Reject trivial noise
        if len(full_text.split()) < 3 and not cur_options:
            _reset()
            return

        # Canonical Question Type mapping (Requirement 4)
        if len(cur_options) >= 2:
            q_type = "MCQ"
        elif any(w in full_text for w in ["صح أم خطأ", "ضع علامة", "True/False", "صواب أم خطأ", "صح أو خطأ"]):
            q_type = "TRUE_FALSE"
        elif any(w in full_text for w in ["أكمل الفراغ", "أكمل ما يأتي", "Fill in the blank"]):
            q_type = "FILL_BLANK"
        else:
            q_type = "ESSAY"

        # Validate MCQ without options
        if q_type == "MCQ" and len(cur_options) < 2:
            _reset()
            return

        # Reject fragments falsely categorized as essay:
        if q_type == "ESSAY":
            has_explicit_header = bool(cur_header and HEADER_RE.match(cur_header))
            has_marks = (cur_points != 5)
            has_instruction_word = bool(re.search(
                r"^(?:السؤال|وضح|علل|فسر|اشرح|بين|قارن|احسب|أثبت|ماذا|كيف|اذكر|ما\s|استنتج|اكتب)\b",
                full_text
            ))
            if not (has_explicit_header or has_marks or has_instruction_word) and len(full_text.split()) < 12:
                _reset()
                return

        formatted_options = [
            {"key": opt["key"], "text": opt["text"], "is_correct": False}
            for opt in cur_options
        ]
        corr_ans, needs_rev = resolve_correct_answer_text(formatted_options, cur_answer)

        questions.append({
            "order": len(questions) + 1,
            "header": cur_header,
            "question_text": full_text,
            "question_type": q_type,
            "options": formatted_options if formatted_options else None,
            "correct_answer": corr_ans,
            "explanation": cur_explanation or None,
            "points": cur_points,
            "page_number": cur_page,
            "image_asset_ids": list(cur_images),
            "classification_confidence": "high",
            "needs_answer_review": needs_rev,
        })
        _reset()

    def _reset():
        nonlocal cur_header, cur_stem_lines, cur_options, cur_answer, cur_explanation, cur_points, cur_images
        cur_header = ""
        cur_stem_lines = []
        cur_options = []
        cur_answer = ""
        cur_explanation = ""
        cur_points = 5
        cur_images = []

    for page in parsed_doc.pages:
        lines: list[str] = []
        for b in page.blocks:
            for l in b.text.split("\n"):
                l_str = l.strip()
                if l_str:
                    lines.append(l_str)

        page_img_ids = [img.id for img in page.images]

        for line in lines:
            if any(re.search(p, line, re.IGNORECASE) for p in ADMINISTRATIVE_METADATA_PATTERNS) or re.search(r"^(?:جمهورية|وزارة|امتحان\s+شهادة|الزمن\s*:|الدرجة\s+العظمى)", line):
                continue
            if EXAM_END_RE.search(line):
                flush()
                continue

            if SECTION_RE.search(line):
                flush()
                is_essay_mode = ("مقالي" in line)
                continue

            if HEADER_RE.search(line):
                flush()
                cur_header = line
                cur_page = page.page_number
                cur_images.extend(page_img_ids)
                marks_m = MARKS_RE.search(line)
                if marks_m:
                    cur_points = int(marks_m.group(1))
                continue

            ans_m = ANS_RE.match(line)
            if ans_m:
                raw_ans = ans_m.group(1).strip()
                if "فكرة" in line:
                    cur_explanation = raw_ans
                else:
                    cur_answer = raw_ans
                continue

            if is_essay_mode:
                cur_stem_lines.append(line)
                continue

            opt = _parse_opt(line)
            if opt and (cur_stem_lines or cur_header or cur_options):
                opt_key, opt_text = opt
                existing_keys = {o["key"] for o in cur_options}
                if opt_key in existing_keys:
                    for next_k in ["أ", "ب", "ج", "د"]:
                        if next_k not in existing_keys:
                            opt_key = next_k
                            break
                cur_options.append({"key": opt_key, "text": opt_text})
                continue

            if re.match(r"^\d{1,2}\.?$", line):
                continue

            # If options have already been collected for the active question,
            # ANY subsequent non-option line MUST start the next question!
            if cur_options and len(cur_options) >= 2:
                flush()
                cur_page = page.page_number
                cur_images.extend(page_img_ids)
                m_start = DIGIT_START_RE.match(line)
                m_end = DIGIT_END_RE.match(line)
                if m_start:
                    cur_stem_lines.append(m_start.group(2).strip())
                elif m_end and len(m_end.group(1).split()) >= 4:
                    cur_stem_lines.append(m_end.group(1).strip())
                else:
                    cur_stem_lines.append(line)
                continue

            # If no options yet, check if line explicitly starts a numbered question
            m_start = DIGIT_START_RE.match(line)
            m_end = DIGIT_END_RE.match(line)
            if m_start:
                if cur_options:
                    flush()
                cur_page = page.page_number
                cur_images.extend(page_img_ids)
                cur_stem_lines.append(m_start.group(2).strip())
                continue
            elif m_end and len(m_end.group(1).split()) >= 4:
                if cur_options:
                    flush()
                cur_page = page.page_number
                cur_images.extend(page_img_ids)
                cur_stem_lines.append(m_end.group(1).strip())
                continue

            # Standard line continuation
            cur_stem_lines.append(line)

    flush()
    return questions


def sanitize_source_filename(name: str) -> str:
    base = os.path.basename(name).strip()
    base = base.replace("\x00", "").replace("/", "_").replace("\\", "_")
    base = re.sub(r'[\r\n\t]', '', base)
    while ".." in base:
        base = base.replace("..", "_")
    if not base or base.startswith("."):
        base = f"file_{base.lstrip('.')}" if base.lstrip('.') else "uploaded_file"
    return base[:200]


def create_knowledge_source(
    db: Session,
    user: User,
    course_id: uuid.UUID,
    filename: str,
    file_bytes: bytes | None = None,
    lesson_id: uuid.UUID | None = None,
    source_role: str = SourceRole.KNOWLEDGE,
    mime_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    staged_file_path: str | None = None,
    checksum: str | None = None,
    size_bytes: int | None = None,
) -> KnowledgeSource:
    """Uploads and creates a new KnowledgeSource record in QUEUED state."""
    filename = sanitize_source_filename(filename)

    if checksum is None:
        if file_bytes is not None:
            checksum = _compute_checksum(file_bytes)
        elif staged_file_path and os.path.exists(staged_file_path):
            hasher = hashlib.sha256()
            with open(staged_file_path, "rb") as sf:
                while chk := sf.read(1024 * 1024):
                    hasher.update(chk)
            checksum = hasher.hexdigest()
        else:
            raise ValueError("Either file_bytes or staged_file_path must be provided.")

    if size_bytes is None:
        if file_bytes is not None:
            size_bytes = len(file_bytes)
        elif staged_file_path and os.path.exists(staged_file_path):
            size_bytes = os.path.getsize(staged_file_path)
        else:
            size_bytes = 0

    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if isinstance(source_role, SourceRole):
        source_role = source_role.value
    else:
        role_str = str(source_role).split(".")[-1].strip().upper()
        source_role = SourceRole(role_str).value

    BANNED_MEDIA_EXTENSIONS = {"mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "3gp", "m4v", "mp3", "wav", "aac"}
    if ext in BANNED_MEDIA_EXTENSIONS or (mime_type and any(mime_type.lower().startswith(p) for p in ["video/", "audio/"])):
        raise ValueError("Video and audio files cannot be ingested into the AI Knowledge Center. Please upload document files only.")
    allowed_extensions = {
        "pdf", "docx", "doc", "txt", "md", "markdown", "json", "quiz", "pptx", "ppt",
        "py", "js", "ts", "tsx", "jsx", "java", "cs", "cpp", "c", "html", "css", "sql",
        "png", "jpg", "jpeg", "webp", "gif",
    }
    if ext not in allowed_extensions:
        raise ValueError(f"صيغة الملف غير مدعومة: .{ext}. الصيغ المدعومة هي: PDF, Word (docx, doc), PowerPoint (pptx, ppt), ملفات نصية، وصور.")

    # Ensure course exists and belongs to teacher's institution
    course = db.scalar(
        select(Course).where(
            Course.id == course_id,
            Course.institution_id == user.institution_id,
        )
    )
    if not course:
        # Fallback to the institution's primary course or auto-create official chemistry course
        fallback_course = db.scalar(
            select(Course).where(Course.institution_id == user.institution_id)
        )
        if not fallback_course:
            fallback_course = db.scalar(select(Course))
        if not fallback_course:
            from app.models.course import CourseStatus
            fallback_course = Course(
                institution_id=user.institution_id,
                teacher_id=user.id,
                code="CHEM-3SEC",
                title="الكيمياء - الصف الثالث الثانوي",
                description="منهج الكيمياء للثانوية العامة — مستر حسن شعبان",
                status=CourseStatus.PUBLISHED,
            )
            db.add(fallback_course)
            db.commit()
            db.refresh(fallback_course)
        course = fallback_course
        course_id = fallback_course.id

    # Check for existing checksum upload to avoid duplicate storage
    existing = db.scalar(
        select(KnowledgeSource).where(
            KnowledgeSource.course_id == course_id,
            KnowledgeSource.checksum == checksum,
            KnowledgeSource.lesson_id == lesson_id,
            KnowledgeSource.source_role == source_role,
        )
    )
    if existing:
        if staged_file_path and os.path.exists(staged_file_path) and staged_file_path != existing.storage_path:
            try:
                os.remove(staged_file_path)
            except OSError:
                pass
        return existing

    # A source with the same logical document key is a new edition. Retrieval
    # uses only the current edition; prior files stay available for audit.
    source_metadata = dict(metadata or {})
    document_key = str(source_metadata.get("document_key") or filename).strip().lower()
    source_metadata["document_key"] = document_key
    prior_sources = db.scalars(
        select(KnowledgeSource).where(
            KnowledgeSource.course_id == course_id,
            KnowledgeSource.lesson_id == lesson_id,
            KnowledgeSource.source_role == source_role,
            KnowledgeSource.is_current == True,
        )
    ).all()
    matching_prior = [
        item for item in prior_sources
        if str((item.metadata_json or {}).get("document_key") or item.filename).strip().lower() == document_key
    ]
    next_version = max((item.version for item in matching_prior), default=0) + 1
    for item in matching_prior:
        item.is_current = False

    # Save file to storage using completely server-generated filename
    rel_dir = f"courses/{course_id}"
    full_dir = os.path.join(STORAGE_DIR, rel_dir)
    os.makedirs(full_dir, exist_ok=True)
    
    server_storage_name = f"{uuid.uuid4().hex}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(full_dir, server_storage_name)
    if staged_file_path and os.path.exists(staged_file_path):
        shutil.move(staged_file_path, file_path)
    elif file_bytes is not None:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    else:
        raise ValueError("Either file_bytes or staged_file_path must be provided.")

    source = KnowledgeSource(
        institution_id=user.institution_id,
        course_id=course_id,
        lesson_id=lesson_id,
        teacher_id=user.id,
        filename=filename,
        file_format=ext,
        mime_type=mime_type or f"application/{ext}",
        storage_path=file_path,
        size_bytes=size_bytes,
        source_role=source_role,
        version=next_version,
        is_current=True,
        checksum=checksum,
        status=SourceStatus.QUEUED,
        metadata_json=source_metadata,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def process_knowledge_source(db: Session, source_id: uuid.UUID) -> KnowledgeSource:
    """Parses source file, extracts structured Knowledge Units, Questions & Assets, and indexes knowledge."""
    source = db.scalar(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    if not source or not os.path.exists(source.storage_path):
        raise ValueError("Knowledge source or file not found")

    source.status = SourceStatus.PROCESSING
    source.progress_percent = 10
    db.commit()

    # Ensure idempotency: purge any prior child records for this source before processing
    db.execute(delete(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source_id))
    db.execute(delete(KnowledgeQuestionImageLink).where(
        KnowledgeQuestionImageLink.question_record_id.in_(
            select(KnowledgeQuestionRecord.id).where(KnowledgeQuestionRecord.source_id == source_id)
        )
    ))
    db.execute(delete(KnowledgeQuestionRecord).where(KnowledgeQuestionRecord.source_id == source_id))
    db.execute(delete(KnowledgeAsset).where(KnowledgeAsset.source_id == source_id))
    db.execute(delete(KnowledgeConceptLink).where(KnowledgeConceptLink.source_id == source_id))
    db.execute(delete(KnowledgeConceptRelation).where(KnowledgeConceptRelation.source_id == source_id))
    db.execute(delete(KnowledgeLessonRelation).where(KnowledgeLessonRelation.source_id == source_id))
    db.execute(delete(KnowledgeOutlineNode).where(KnowledgeOutlineNode.source_id == source_id))
    db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.source_id == source_id))
    db.execute(delete(AssessmentSource).where(AssessmentSource.source_id == source_id))
    try:
        # Structured assessment banks are parsed directly; document assessments use
        # the normal structure-preserving document parser below, then materialize.
        if source.file_format in ("json", "quiz"):
            with open(source.storage_path, "rb") as f:
                file_bytes = f.read()
            parsed_questions = parse_assessment_bank(file_bytes, source.filename)
            
            assess_source = AssessmentSource(
                source_id=source.id,
                assessment_type=(source.metadata_json or {}).get("assessment_type", "quiz"),
                title=os.path.splitext(source.filename)[0],
                total_questions=len(parsed_questions),
                answer_key_source_id=(source.metadata_json or {}).get("answer_key_source_id"),
                processing_status="resolved",
                review_status="needs_review",
            )
            db.add(assess_source)
            db.commit()
            db.refresh(assess_source)

            q_count = 0
            for pq in parsed_questions:
                norm_text = re.sub(r"\s+", "", pq.question_text.lower())
                norm_hash = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()
                fingerprint = hashlib.md5(f"{norm_text}_{pq.correct_answer or ''}".encode("utf-8")).hexdigest()

                q_rec = AssessmentQuestion(
                    assessment_source_id=assess_source.id,
                    course_id=source.course_id,
                    lesson_id=source.lesson_id,
                    question_text=pq.question_text,
                    question_type=pq.question_type,
                    difficulty=pq.difficulty,
                    learning_objective=pq.learning_objective,
                    topic_concept=pq.topic_concept,
                    correct_answer=pq.correct_answer,
                    answer_source="structured_bank" if pq.correct_answer else None,
                    answer_status="resolved" if pq.correct_answer else "needs_review",
                    answer_provenance_json={"source": "structured_upload"} if pq.correct_answer else {},
                    options_json=pq.options,
                    explanation=pq.explanation,
                    media_ids_json=pq.media_ids,
                    review_status="approved" if pq.correct_answer else "needs_review",
                    normalized_hash=norm_hash,
                    semantic_fingerprint=fingerprint,
                )
                db.add(q_rec)
                q_count += 1

            source.question_count = q_count
            source.status = SourceStatus.INDEXED
            source.progress_percent = 100
            db.commit()
            return source

        # Document & Media parsing (PDF, DOCX, PPTX, TXT, Images)
        def on_page_progress(current_page: int, total_pages: int) -> None:
            if total_pages > 0 and (current_page % 5 == 0 or current_page == total_pages):
                pct = min(75, int(10 + (current_page / total_pages) * 65))
                source.progress_percent = pct
                try:
                    db.commit()
                except Exception:
                    pass

        parsed_doc = parse_knowledge_file(
            file_bytes=None,
            filename=source.filename,
            mime_type=source.mime_type,
            progress_callback=on_page_progress,
            file_path=source.storage_path,
        )

        doc_rec = KnowledgeDocument(
            source_id=source.id,
            title=parsed_doc.title,
            author=parsed_doc.author,
            doc_type=parsed_doc.doc_type,
            total_pages=parsed_doc.total_pages,
            total_slides=parsed_doc.total_slides,
            hierarchy_json=parsed_doc.hierarchy,
        )
        db.add(doc_rec)
        db.commit()
        db.refresh(doc_rec)

        outline_nodes = materialize_book_outline(
            db,
            source_id=source.id,
            course_id=source.course_id,
            document_title=parsed_doc.title,
            total_pages=parsed_doc.total_pages,
            hierarchy=parsed_doc.hierarchy,
        )
        materialize_lesson_relations(
            db, source_id=source.id, course_id=source.course_id, nodes=outline_nodes,
        )
        outline_by_id = {node.id: node for node in outline_nodes}

        def outline_context(page_or_slide: int | None) -> tuple[KnowledgeOutlineNode | None, dict[str, str]]:
            node = outline_node_for_page(outline_nodes, page_or_slide)
            context: dict[str, str] = {}
            current = node
            while current:
                context.setdefault(current.node_kind, current.title)
                current = outline_by_id.get(current.parent_id) if current.parent_id else None
            return node, context
        db.commit()

        # 1. Process Assets with single BATCH COMMIT
        asset_count = 0
        img_id_map: dict[str, uuid.UUID] = {}
        assets_dir = os.path.join(STORAGE_DIR, f"courses/{source.course_id}/assets")
        os.makedirs(assets_dir, exist_ok=True)

        for p_img in parsed_doc.all_images:
            asset_path = p_img.storage_path or source.storage_path
            vision_analysis: dict[str, Any] = {}
            if p_img.image_bytes:
                img_filename = f"{p_img.id}_{source.id.hex[:8]}.png"
                asset_path = os.path.join(assets_dir, img_filename)
                try:
                    with open(asset_path, "wb") as img_f:
                        img_f.write(p_img.image_bytes)
                except Exception:
                    asset_path = source.storage_path
                vision_analysis = analyze_educational_image(
                    p_img.image_bytes,
                    mime_type="image/png",
                    caption=p_img.caption,
                    surrounding_text=p_img.surrounding_text,
                    existing_ocr_text=p_img.ocr_text,
                ).model_dump()
                vision_analysis["validated_formulas"] = [
                    {"raw": formula.raw, "kind": formula.kind, "valid": formula.valid, "normalized": formula.normalized}
                    for formula in extract_and_validate_formulas(
                        "\n".join(filter(None, [p_img.ocr_text, vision_analysis.get("table_markdown"), " ".join(vision_analysis.get("formulas", []))]))
                    )
                ]

            asset = KnowledgeAsset(
                source_id=source.id,
                document_id=doc_rec.id,
                outline_node_id=(
                    outline_node_for_page(outline_nodes, p_img.page_number or p_img.slide_number).id
                    if outline_node_for_page(outline_nodes, p_img.page_number or p_img.slide_number)
                    else None
                ),
                page_number=p_img.page_number,
                slide_number=p_img.slide_number,
                asset_kind=p_img.asset_kind,
                caption=p_img.caption,
                surrounding_text=p_img.surrounding_text,
                storage_path=asset_path,
                checksum=p_img.checksum,
                width=p_img.width,
                height=p_img.height,
                metadata_json={
                    "ocr_text": p_img.ocr_text,
                    "ocr_engine": p_img.ocr_engine,
                    "page_number": p_img.page_number,
                    "slide_number": p_img.slide_number,
                    "vision_analysis": vision_analysis,
                },
            )
            db.add(asset)
            img_id_map[p_img.id] = asset.id
            asset_count += 1

        if asset_count > 0:
            db.commit()

        assets_by_page: dict[int, list[KnowledgeAsset]] = {}
        for asset in db.scalars(select(KnowledgeAsset).where(KnowledgeAsset.source_id == source.id)).all():
            assets_by_page.setdefault(asset.page_number or asset.slide_number or 1, []).append(asset)
        pending_question_image_links: list[tuple[KnowledgeQuestionRecord, list[ImageMatch]]] = []

        def question_image_matches(question_text: str, page_or_slide: int | None, explicit_ids: list[str] | None = None) -> list[ImageMatch]:
            return select_question_images(
                question_text,
                assets_by_page.get(page_or_slide or 1, []),
                explicit_asset_ids=explicit_ids or [],
            )
            from app.services.chemistry_vision import index_asset_as_knowledge_unit
            created_assets = db.scalars(select(KnowledgeAsset).where(KnowledgeAsset.source_id == source.id)).all()
            for ca in created_assets:
                try:
                    index_asset_as_knowledge_unit(
                        db=db,
                        asset=ca,
                        course_id=source.course_id,
                        lesson_id=source.lesson_id,
                        source_id=source.id,
                        version=source.version,
                    )
                except Exception as exc:
                    logger.debug(f"Failed indexing asset {ca.id} as knowledge unit: {exc}")
            db.commit()

        # 2. Extract distant answer keys across document
        distant_keys = extract_distant_answer_keys(parsed_doc)

        # 3. Extract table-structured questions (reusing parsed_doc.all_tables)
        question_count = 0
        table_questions = parse_table_questions(parsed_doc, distant_keys)
        for tq in table_questions:
            q_page = tq.get("page_number") or tq.get("slide_number")
            matches = question_image_matches(tq["question_text"], q_page)
            outline_node, context = outline_context(q_page)
            kq_rec = KnowledgeQuestionRecord(
                source_id=source.id,
                course_id=source.course_id,
                lesson_id=source.lesson_id,
                document_id=doc_rec.id,
                outline_node_id=outline_node.id if outline_node else None,
                question_text=tq["question_text"],
                question_order=question_count + 1,
                question_type=tq["question_type"],
                options_json=tq["options"],
                correct_answer=tq["correct_answer"],
                page_number=tq["page_number"],
                slide_number=tq["slide_number"],
                image_asset_ids_json=[match.asset_id for match in matches],
                raw_text=tq.get("raw_text"),
                metadata_json={"hierarchy": context, "image_link_verification": [match.evidence for match in matches]},
                classification_confidence=tq.get("classification_confidence", "high"),
                needs_answer_review=tq.get("needs_answer_review", False),
            )
            db.add(kq_rec)
            pending_question_image_links.append((kq_rec, matches))
            question_count += 1

        # 3c. Extract document-level structured questions (multi-line continuations, MCQs, Essay)
        doc_assembled_questions = assemble_document_questions(parsed_doc, distant_keys)
        assembled_q_stems: set[str] = set()
        for aq in doc_assembled_questions:
            q_page = aq.get("page_number") or 1
            explicit_img_ids = [str(img_id_map[m_id]) for m_id in aq.get("image_asset_ids", []) if m_id in img_id_map]
            matches = question_image_matches(aq["question_text"], q_page, explicit_img_ids)
            outline_node, context = outline_context(q_page)
            points = aq.get("points", 5)
            context["points"] = points

            kq_rec = KnowledgeQuestionRecord(
                source_id=source.id,
                course_id=source.course_id,
                lesson_id=source.lesson_id,
                document_id=doc_rec.id,
                outline_node_id=outline_node.id if outline_node else None,
                question_text=aq["question_text"],
                question_order=question_count + 1,
                question_type=aq["question_type"],
                options_json=aq["options"],
                correct_answer=aq["correct_answer"],
                explanation=aq["explanation"],
                page_number=q_page,
                slide_number=None,
                image_asset_ids_json=[match.asset_id for match in matches],
                raw_text=aq["question_text"],
                metadata_json={"hierarchy": context, "image_link_verification": [match.evidence for match in matches], "points": points},
                classification_confidence=aq.get("classification_confidence", "high"),
                needs_answer_review=aq.get("needs_answer_review", False),
            )
            db.add(kq_rec)
            pending_question_image_links.append((kq_rec, matches))
            question_count += 1
            assembled_q_stems.add(re.sub(r"\s+", "", aq["question_text"][:40]))

        # 3b. Convert genuine non-question descriptive tables into rich KnowledgeUnitRecords
        unit_count = 0
        PEDAGOGICAL_FILTER_MARKERS = [
            "أهداف", "يتعرف الطالب", "يوضح الطالب", "ينبغي أن يكون", "يكون الطالب قادراً",
            "اختر الإجابة", "ضع علامة", "علل لما يأتي", "فسر ما يلي", "ما النتائج المترتبة",
            "قارن بين", "أسئلة وتدريبات", "مراجعة عامة", "مراجعة الدرس", "امتحانات"
        ]

        for t_idx, table in enumerate(parsed_doc.all_tables):
            headers = getattr(table, "headers", []) if hasattr(table, "headers") else table.get("headers", [])
            rows = getattr(table, "rows", []) if hasattr(table, "rows") else table.get("rows", [])
            page_num = getattr(table, "page_number", 1) if hasattr(table, "page_number") else table.get("page_number", 1)
            slide_num = getattr(table, "slide_number", None) if hasattr(table, "slide_number") else table.get("slide_number", None)

            if is_question_table(headers, rows):
                continue
            if not headers or not rows:
                continue

            # Skip tables containing pedagogical objectives or assessment headers
            headers_str = " ".join(str(h) for h in headers)
            if any(m in headers_str for m in PEDAGOGICAL_FILTER_MARKERS):
                continue

            h0 = str(headers[0]).strip() if headers else ""
            if not h0 or h0 in ["جدول البيانات", "جدول", "بيانات", "مقارنة", "جدول مقارنة", "None"]:
                table_prefix = f"وفقاً للبيانات الإحصائية (صفحة {page_num}): "
            else:
                table_prefix = f"وفقاً لجدول {h0}: "

            for r_idx, row in enumerate(rows):
                if not row or len(row) < 2:
                    continue

                # Skip rows containing objectives or exam questions
                row_str = " ".join(str(c) for c in row)
                if any(m in row_str for m in PEDAGOGICAL_FILTER_MARKERS):
                    continue

                # Reject rows with oversized narrative text (> 35 words in any cell)
                if any(len(str(c).split()) > 35 for c in row):
                    continue

                row_concept = str(row[0]).strip()
                if row_concept.isdigit() and len(row) > 1:
                    row_concept = str(row[1]).strip()

                row_parts = []
                for c_idx, cell in enumerate(row):
                    h_name = str(headers[c_idx]).strip() if c_idx < len(headers) else f"البند {c_idx+1}"
                    c_val = str(cell).strip()
                    if c_val:
                        row_parts.append(f"{h_name} هو «{c_val}»")

                if not row_parts:
                    continue

                statement = table_prefix + "، و".join(row_parts) + "."

                # Ensure statement is not garbled
                if is_text_garbled(statement):
                    continue

                if any(w in statement for w in ["استخدام", "وظيفة", "عملية", "قياس", "معايرة", "تحضير"]):
                    k_type = "application"
                elif any(w in statement for w in ["تعريف", "وصف", "خاصية", "تركيب"]):
                    k_type = "definition"
                else:
                    k_type = "fact"

                ku_rec = KnowledgeUnitRecord(
                    course_id=source.course_id,
                    lesson_id=source.lesson_id,
                    source_id=source.id,
                    source_type="document",
                    concept=row_concept[:100],
                    knowledge_type=k_type,
                    statement=statement,
                    details=statement,
                    importance=0.7,
                    semantic_confidence=1.0,
                    needs_review=False,
                    source_document_id=doc_rec.id,
                    outline_node_id=(outline_node_for_page(outline_nodes, page_num or slide_num).id if outline_node_for_page(outline_nodes, page_num or slide_num) else None),
                    page_number=page_num,
                    slide_number=slide_num,
                    block_id=f"tbl_{t_idx}_r_{r_idx+1}",
                    source_media_ids_json=[],
                    version=source.version,
                )
                db.add(ku_rec)
                unit_count += 1

        # 4. Extract Knowledge Units and Block Questions from document pages
        inside_objectives_section = False
        table_count = len(parsed_doc.all_tables)
        stripped_instruction_lines = 0

        for page in parsed_doc.pages:
            # Check if user requested to stop indexing
            if (page.page_number or 0) % 2 == 0:
                current_status = db.scalar(select(KnowledgeSource.status).where(KnowledgeSource.id == source.id))
                if current_status == SourceStatus.FAILED:
                    logger.info(f"Stopping indexing early for source {source.id} per user request.")
                    return source

            # Front-matter page heuristic for multi-page books/documents:
            # Skip entire cover/credits/preface/TOC pages if page_number in (1, 2, 3) and contains markers
            if parsed_doc.total_pages >= 4 and page.page_number in (1, 2, 3):
                p_text = page.raw_text or ""
                is_fm = False
                if page.page_number in (1, 2) and any(re.search(pat, p_text, re.IGNORECASE) for pat in [
                    r"وزار[ةه]\s+التربي[ةه]",
                    r"مقدم[ةه]",
                    r"فهرس|محتويات\s+الكتاب",
                    r"حقوق\s+الطبع",
                    r"لجن[ةه]\s+(?:التطوير|التأليف|الإعداد)",
                    r"[اإأآ]دار[ةه]\s+مركزي[ةه]",
                    r"مستشار\s+ماد[ةه]",
                ]):
                    is_fm = True
                elif page.page_number <= 3:
                    # Check for Table of Contents pattern: multiple chapters/parts listed
                    toc_matches = len(re.findall(r"(?:الباب|الجزء)\s+(?:الأول|الثان[يي]|الثالث|الرابع|الخامس)|فهرس|محتويات", p_text, re.IGNORECASE))
                    if toc_matches >= 2:
                        is_fm = True

                if is_fm:
                    continue

            page_img_ids = [str(img_id_map[i.id]) for i in page.images if i.id in img_id_map]

            for block in page.blocks:
                safe_text, stripped = sanitize_retrieval_text(block.text)
                stripped_instruction_lines += stripped
                if not safe_text:
                    continue
                block.text = safe_text
                b_text = safe_text.strip()

                # Objectives section header detection
                if re.search(r"الأهداف\s+التعليمية|أهداف\s+(?:الباب|الفصل|الدرس|الوحدة|المقرر)|يتوقع\s+من\s+الطالب\s+أن", b_text, re.IGNORECASE):
                    inside_objectives_section = True
                    continue

                if inside_objectives_section:
                    if re.search(r"^(?:الباب|الفصل|الدرس|الموضوع|الوحدة|أولاً|ثانياً|ثالثاً|تعريف|مفهوم|تكامل)\b", b_text):
                        inside_objectives_section = False
                    elif block.block_type == "heading" and not any(k in b_text for k in ["الأهداف", "أهداف", "يتوقع"]):
                        inside_objectives_section = False
                    elif re.search(r"^(?:[0-9]+[\-\.\)]\s*|[\-\*•]\s*)(?:يوضح|يتعرف|يذكر|يقارن|يفسر|يشرح|يحدد|يصف|يستنتج|يميز|يعدد|يطبق|يبين|يحلل|يركب|يحسب)\b", b_text) or re.search(r"^(?:يوضح|يتعرف|يذكر|يقارن|يفسر|يشرح|يحدد|يصف|يستنتج|يميز|يعدد|يطبق|يبين|يحلل)\b", b_text):
                        continue

                norm_block_stem = re.sub(r"\s+", "", block.text[:40])
                if norm_block_stem in assembled_q_stems:
                    continue

                status, q_data = classify_and_parse_question(block.text, distant_keys)

                if status in ("question", "uncertain") and q_data:
                    block.block_type = status
                    matches = question_image_matches(
                        q_data["question_text"], page.page_number or page.slide_number,
                        [str(img_id_map[media_id]) for media_id in block.media_ids if media_id in img_id_map],
                    )
                    outline_node, context = outline_context(page.page_number or page.slide_number)
                    kq_rec = KnowledgeQuestionRecord(
                        source_id=source.id,
                        course_id=source.course_id,
                        lesson_id=source.lesson_id,
                        document_id=doc_rec.id,
                        outline_node_id=outline_node.id if outline_node else None,
                        question_text=q_data["question_text"],
                        question_order=question_count + 1,
                        question_type=q_data["question_type"],
                        options_json=q_data["options"],
                        correct_answer=q_data["correct_answer"],
                        page_number=page.page_number,
                        slide_number=page.slide_number,
                        image_asset_ids_json=[match.asset_id for match in matches],
                        raw_text=q_data.get("raw_text"),
                        metadata_json={"hierarchy": context, "image_link_verification": [match.evidence for match in matches]},
                        classification_confidence=q_data.get("classification_confidence", "high"),
                        needs_answer_review=q_data.get("needs_answer_review", False),
                    )
                    db.add(kq_rec)
                    pending_question_image_links.append((kq_rec, matches))
                    question_count += 1
                    continue

                # Everything not a question is processed as Content
                if source.source_role in (SourceRole.ASSESSMENT, SourceRole.ANSWER_KEY):
                    continue
                # Filter out document/exam titles and answer-key sections from becoming KnowledgeUnits
                lines = [l.strip() for l in block.text.split("\n") if l.strip()]
                if any(re.search(pat, block.text, re.IGNORECASE) for pat in KEY_SECTION_PATTERNS):
                    continue
                if any(re.search(pat, block.text, re.IGNORECASE) for pat in ADMINISTRATIVE_METADATA_PATTERNS):
                    continue
                if any(re.search(pat, block.text, re.IGNORECASE) for pat in BLOOM_OBJECTIVE_PATTERNS):
                    continue
                if lines and all(bool(re.match(r"^\(?\d+\)?\s*[\:\.\-\)]\s*[أ-دA-Da-d]\b", l)) for l in lines):
                    continue

                cleaned = clean_spoken_noise(block.text)
                if len(cleaned.split()) < 4:
                    continue

                # Optional structured LLM extraction turns source content into a
                # concept/claim/category triple.  The independent verifier below
                # rejects any expansion, and the deterministic parser remains the
                # zero-config fallback.
                llm_unit = invoke_llm_semantic_rewriting(cleaned, block.text, timeout=2.0)
                if llm_unit:
                    concept = str(llm_unit.get("concept") or "")
                    statement = str(llm_unit.get("statement") or "")
                    category = str(llm_unit.get("category") or "fact")
                else:
                    concept, statement, category = reconstruct_educational_statement(cleaned)
                if not concept or not statement:
                    lines = [l.strip() for l in block.text.split("\n") if l.strip()]
                    concept = lines[0][:60] if lines else f"محتوى الصفحة {page.page_number or 1}"
                    statement = block.text.strip()
                    category = "fact"

                concept = clean_arabic_ocr_text(concept)
                statement = clean_arabic_ocr_text(statement)

                verif = verify_semantic_faithfulness(block.text, statement)
                if not verif.is_faithful and llm_unit:
                    concept, statement, category = reconstruct_educational_statement(cleaned)
                    verif = verify_semantic_faithfulness(block.text, statement)
                needs_review = bool(verif.semantic_confidence < SEMANTIC_CONFIDENCE_THRESHOLD)

                ku_rec = KnowledgeUnitRecord(
                    course_id=source.course_id,
                    lesson_id=source.lesson_id,
                    source_id=source.id,
                    source_type="document",
                    concept=concept,
                    knowledge_type=category,
                    statement=statement,
                    details=block.text,
                    importance=0.8 if block.block_type == "heading" else 0.5,
                    semantic_confidence=verif.semantic_confidence,
                    needs_review=needs_review,
                    source_document_id=doc_rec.id,
                    outline_node_id=(outline_node_for_page(outline_nodes, page.page_number or page.slide_number).id if outline_node_for_page(outline_nodes, page.page_number or page.slide_number) else None),
                    page_number=page.page_number,
                    slide_number=page.slide_number,
                    block_id=block.block_id,
                    source_media_ids_json=page_img_ids,
                    version=source.version,
                )
                db.add(ku_rec)
                unit_count += 1

        if getattr(parsed_doc, "extracted_via_ocr", False):
            source_meta = dict(source.metadata_json or {})
            source_meta["extracted_via_ocr"] = True
            source_meta["ocr_pages"] = getattr(parsed_doc, "ocr_pages", [])
            source_meta["ocr_engine"] = "tesseract-ara+eng"
            source.metadata_json = source_meta

        if stripped_instruction_lines:
            source_meta = dict(source.metadata_json or {})
            source_meta["stripped_instruction_like_lines"] = stripped_instruction_lines
            source.metadata_json = source_meta

        # Normalize source order after table and paragraph extraction have both
        # completed, so a table on a later page cannot jump ahead of an earlier
        # paragraph question merely because tables are processed first.
        db.flush()
        source_questions = db.scalars(
            select(KnowledgeQuestionRecord)
            .where(KnowledgeQuestionRecord.source_id == source.id)
            .order_by(
                KnowledgeQuestionRecord.page_number.asc().nullslast(),
                KnowledgeQuestionRecord.slide_number.asc().nullslast(),
                KnowledgeQuestionRecord.created_at.asc(),
            )
        ).all()
        for ordinal, source_question in enumerate(source_questions, start=1):
            source_question.question_order = ordinal

        # Persist the verified edge separately from the denormalized media list.
        # This lets the quiz renderer retain why each image belongs to a question.
        db.flush()
        for question_record, matches in pending_question_image_links:
            for position, match in enumerate(matches, start=1):
                db.add(KnowledgeQuestionImageLink(
                    question_record_id=question_record.id,
                    asset_id=uuid.UUID(match.asset_id),
                    relation_type=match.relation_type,
                    confidence=match.confidence,
                    position=position,
                    evidence_json=match.evidence,
                ))
        db.flush()

        if source.source_role == SourceRole.ASSESSMENT:
            db.flush()
            answer_key_raw = (source.metadata_json or {}).get("answer_key_source_id")
            answer_key_source_id = uuid.UUID(str(answer_key_raw)) if answer_key_raw else None
            materialize_assessment_questions(
                db,
                source,
                assessment_type=(source.metadata_json or {}).get("assessment_type", "exam"),
                answer_key_source_id=answer_key_source_id,
            )

        source.progress_percent = 85
        db.commit()

        units_to_embed = db.scalars(
            select(KnowledgeUnitRecord).where(
                KnowledgeUnitRecord.source_id == source.id,
                KnowledgeUnitRecord.embedding_json.is_(None),
            )
        ).all()
        if units_to_embed:
            provider = get_embedding_provider()
            texts = [
                f"{unit.concept}\n{unit.statement}\n{unit.details or ''}"[:6000]
                for unit in units_to_embed
            ]
            for unit, vector in zip(units_to_embed, provider.embed_texts(texts), strict=False):
                unit.embedding_json = vector

        source.progress_percent = 90
        db.commit()

        indexed_units = db.scalars(
            select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source.id)
        ).all()
        upsert_knowledge_vectors(
            (
                str(unit.id), unit.embedding_json or [],
                {"course_id": str(unit.course_id), "source_id": str(source.id), "version": source.version},
            )
            for unit in indexed_units
        )

        source.progress_percent = 95
        db.commit()

        build_source_knowledge_graph(db, source.id)

        source.unit_count = unit_count
        source.image_count = asset_count
        source.table_count = table_count
        source.question_count = question_count
        source.status = SourceStatus.INDEXED
        source.progress_percent = 100
        db.commit()
        db.refresh(source)

        return source

    except Exception as exc:
        source.status = SourceStatus.FAILED
        source.error_message = str(exc)
        db.commit()
        raise exc


def reindex_knowledge_source(db: Session, source_id: uuid.UUID) -> KnowledgeSource:
    """Idempotently reindexes a KnowledgeSource without creating duplicate records."""
    source = db.scalar(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    if not source:
        raise ValueError("Source not found")

    # Increment version
    source.version += 1

    # Delete previous version units, questions & documents safely
    db.execute(delete(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source_id))
    db.execute(delete(KnowledgeQuestionImageLink).where(
        KnowledgeQuestionImageLink.question_record_id.in_(
            select(KnowledgeQuestionRecord.id).where(KnowledgeQuestionRecord.source_id == source_id)
        )
    ))
    db.execute(delete(KnowledgeQuestionRecord).where(KnowledgeQuestionRecord.source_id == source_id))
    db.execute(delete(KnowledgeAsset).where(KnowledgeAsset.source_id == source_id))
    db.execute(delete(KnowledgeConceptLink).where(KnowledgeConceptLink.source_id == source_id))
    db.execute(delete(KnowledgeConceptRelation).where(KnowledgeConceptRelation.source_id == source_id))
    db.execute(delete(KnowledgeLessonRelation).where(KnowledgeLessonRelation.source_id == source_id))
    db.execute(delete(KnowledgeOutlineNode).where(KnowledgeOutlineNode.source_id == source_id))
    db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.source_id == source_id))
    db.execute(delete(AssessmentSource).where(AssessmentSource.source_id == source_id))
    db.commit()

    return process_knowledge_source(db, source_id)


def delete_knowledge_source(db: Session, source_id: uuid.UUID) -> bool:
    """Deletes source file and purges associated document, assets, units, and questions."""
    source = db.scalar(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    if not source:
        return False

    # Purge child records explicitly to prevent orphaned units in search/RAG
    db.execute(delete(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source_id))
    db.execute(delete(KnowledgeQuestionImageLink).where(
        KnowledgeQuestionImageLink.question_record_id.in_(
            select(KnowledgeQuestionRecord.id).where(KnowledgeQuestionRecord.source_id == source_id)
        )
    ))
    db.execute(delete(KnowledgeQuestionRecord).where(KnowledgeQuestionRecord.source_id == source_id))
    db.execute(delete(KnowledgeAsset).where(KnowledgeAsset.source_id == source_id))
    db.execute(delete(KnowledgeConceptLink).where(KnowledgeConceptLink.source_id == source_id))
    db.execute(delete(KnowledgeConceptRelation).where(KnowledgeConceptRelation.source_id == source_id))
    db.execute(delete(KnowledgeLessonRelation).where(KnowledgeLessonRelation.source_id == source_id))
    db.execute(delete(KnowledgeOutlineNode).where(KnowledgeOutlineNode.source_id == source_id))
    db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.source_id == source_id))
    db.execute(delete(AssessmentSource).where(AssessmentSource.source_id == source_id))

    if os.path.exists(source.storage_path):
        try:
            os.remove(source.storage_path)
        except Exception:
            pass

    db.delete(source)
    db.commit()
    return True
