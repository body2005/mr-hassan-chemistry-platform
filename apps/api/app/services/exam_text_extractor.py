"""Exam text extraction helpers (local, deterministic, no AI).

Pulled out of the removed Knowledge Center service so the quiz/assignment
extraction pipeline keeps its pure rule-based text/question parsers. Every
function here is deterministic string/table processing over already-parsed
document text — no LLM, embeddings, vector store, or network calls.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from app.services.document_parsers import clean_chemical_formula_text, fix_arabic_bidi_scrambling

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
    r"انتهت\s+الأسئل[ةه]",
    r"مع\s+أطيب\s+الأمنيات",
    r"والدرجات\s+العلا",
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





# UI chrome strings that leak into extracted text when exam files are
# rendered/printed from a screen. Stripped deterministically from every text
# block before question classification (conservative: short token removal only).
_UI_LEAK_PATTERNS = [
    re.compile(r"svgsvg", re.IGNORECASE),
    re.compile(r"\bsvg\b", re.IGNORECASE),
    re.compile(r"^\s*تعديل\s*$"),
    re.compile(r"مساحة إجابة الطالب"),
    re.compile(r"خانة إجابة الطالب"),
    re.compile(r"^\s*الدرجة[:：]?\s*$"),
    re.compile(r"^\s*(?:اختيار من متعدد|صح أو خطأ|سؤال مقالي|أكمل الفراغات|MCQ)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:حدد الدرجة|حدد الإجابة الصحيحة)\s*$"),
]


def strip_ui_leak_lines(lines: list[str]) -> list[str]:
    """Drop lines that are pure UI chrome; trim inline chrome from others."""
    kept: list[str] = []
    for line in lines:
        text = line
        for pattern in _UI_LEAK_PATTERNS:
            text = pattern.sub("", text)
        if text.strip():
            kept.append(text.rstrip())
    return kept


def sanitize_source_filename(name: str) -> str:
    base = os.path.basename(name).strip()
    base = base.replace("\x00", "").replace("/", "_").replace("\\", "_")
    base = re.sub(r'[\r\n\t]', '', base)
    while ".." in base:
        base = base.replace("..", "_")
    if not base or base.startswith("."):
        base = f"file_{base.lstrip('.')}" if base.lstrip('.') else "uploaded_file"
    return base[:200]


def extract_explicit_points(text: str) -> tuple[int | None, bool]:
    """
    Extracts explicit point values from question text.
    Returns (points, needs_points_assignment).
    Strictly deterministic: returns integer points ONLY if explicitly stated in text;
    NEVER defaults to 5 or guesses points.
    """
    if not text:
        return (None, True)

    text_norm = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

    # 1. Arabic word representations
    if re.search(r"[\(\[]\s*(?:درجتان|علامتان)\s*[\)\]]", text):
        return (2, False)
    if re.search(r"[\(\[]\s*(?:درجة\s+واحدة|علامة\s+واحدة|درجة|علامة)\s*[\)\]]", text):
        return (1, False)

    # 2. Bracketed digit patterns: [3 درجات], (5 marks), [10 pts], (4 درجات)
    m = re.search(
        r"[\(\[]\s*(\d+)\s*(?:درجات|درجة|علامات|علامة|marks?|pts?|points?)\s*[\)\]]",
        text_norm,
        re.IGNORECASE,
    )
    if m:
        val = int(m.group(1))
        if 1 <= val <= 100:
            return (val, False)

    # 3. Trailing delimiter patterns e.g. " -- 3 درجات" or " - 2 درجات"
    m_end = re.search(
        r"[-–—:]\s*(\d+)\s*(?:درجات|درجة|علامات|علامة|marks?|pts?|points?)\s*$",
        text_norm,
        re.IGNORECASE,
    )
    if m_end:
        val = int(m_end.group(1))
        if 1 <= val <= 100:
            return (val, False)

    return (None, True)


def clean_points_tokens_from_text(text: str) -> str:
    """Removes point annotation tokens like '(3 درجات)' from question stems."""
    cleaned = re.sub(
        r"[\(\[]\s*(?:\d+\s*(?:درجات|درجة|علامات|علامة|marks?|pts?|points?)|درجتان|علامتان|درجة\s+واحدة|علامة\s+واحدة|درجة|علامة)\s*[\)\]]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"[-–—:]\s*(?:\d+\s*(?:درجات|درجة|علامات|علامة|marks?|pts?|points?)|درجتان|علامتان|درجة\s+واحدة|علامة\s+واحدة)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


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
                    r"(?:س|q|question)?\s*\(?(\d+)\)?\s*[\:\.\-\)]\s*\(?([أبجدA-Da-d]|[^\n\r\,\;]{1,100})\)?",
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
        "حفظ التعديل", "الدرجة:", "svg", "تعديل",
        "مساحة إجابة الطالب", "خانة إجابة الطالب",
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
    if lines and all(bool(re.match(r"^\(?\d+\)?\s*[\:\.\-\)]\s*[أبجدA-Da-d]\b", l)) for l in lines):
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
    OPT_PATTERN = re.compile(r"^[\(\[]?\s*([أبجدA-Da-d1-4]|i|z|s|\)\()\s*[\)\]\.\:\-\/]\s*(.*)$")
    OPT_SUFFIX_PATTERN = re.compile(r"^(.*?)\s*[\(\[]\s*([أبجدA-Da-d1-4]|i|z|s|\)\()\s*[\)\]][\.\:\-]?$")
    ANS_PATTERN = re.compile(
        r"^(?:الإجاب[ةه](?:\s+الصحيح[ةه])?|الجواب(?:\s+الصحيح)?|الحل(?:\s+الصحيح)?|فكرة\s+الحل|Answer|Key)\s*[\:\.\-\/]?\s*(.*)$",
        re.IGNORECASE,
    )
    INLINE_OPT_PATTERN = re.compile(
        r"(?:^|\s+)[\(\[]?\s*([أبجدA-D1-4]|i|z)\s*[\)\]\.\:\-\/]\s*(.*?)(?=(?:\s+[\(\[]?\s*[أبجدA-D1-4]|i|z\s*[\)\]\.\:\-\/]|$))"
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

    # Extract marks only if explicitly written in the source text; NEVER default to 5
    extracted_points, needs_points_assignment = extract_explicit_points(clean_t)
    if extracted_points is not None:
        q_stem = clean_points_tokens_from_text(q_stem)

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
            "needs_points_assignment": needs_points_assignment,
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
            "needs_points_assignment": needs_points_assignment,
            "classification_confidence": "uncertain",
            "needs_answer_review": True,
            "raw_text": clean_t,
        })
    else:
        return ("content", None)


class ExamQuestionSegmenter:
    """
    Deterministic state machine for segmenting exam questions across lines and blocks.
    Tracks section context, handles multiline questions and option sets,
    and guarantees no question invention, points guessing, or stale cross-file bleed.
    """

    def __init__(self, distant_keys: dict[str, str] | None = None, filename: str = ""):
        self.distant_keys = distant_keys or {}
        self.filename = filename
        self.current_section_type: str | None = None
        self.current_section_title: str | None = None
        self.extracted_questions: list[dict[str, Any]] = []

        # Current pending question builder state
        self._q_stem_parts: list[str] = []
        self._options: list[tuple[str, str]] = []
        self._answer_raw: str | None = None
        self._explicit_points: int | None = None
        self._needs_points_assignment: bool = True
        self._source_page: int | None = None
        self._source_block_ids: list[str] = []
        self._raw_lines: list[str] = []
        self._q_num: str | None = None
        self._section_hint: str | None = None

    def _flush_active_question(self) -> None:
        if not self._q_stem_parts and not self._raw_lines:
            return

        stem_text = " ".join(self._q_stem_parts).strip()
        stem_text = clean_points_tokens_from_text(stem_text)
        stem_text = clean_chemical_formula_text(fix_arabic_bidi_scrambling(stem_text))
        for pattern in _UI_LEAK_PATTERNS:
            stem_text = pattern.sub("", stem_text)
        stem_text = re.sub(r"[ \t]{2,}", " ", stem_text).strip()

        # Drop if empty or too short
        if len(stem_text.split()) < 2 and not (self._options and len(stem_text) >= 2):
            self._reset_builder()
            return

        # Check if stem is purely an administrative or excluded header
        if any(re.search(pat, stem_text, re.IGNORECASE) for pat in ADMINISTRATIVE_METADATA_PATTERNS):
            self._reset_builder()
            return

        if any(re.search(pat, stem_text, re.IGNORECASE) for pat in BLOOM_OBJECTIVE_PATTERNS):
            self._reset_builder()
            return

        # If answer was not in question, check distant keys with question number
        ans_raw = self._answer_raw
        if not ans_raw and self._q_num and self._q_num in self.distant_keys:
            ans_raw = self.distant_keys[self._q_num]

        # Build options
        formatted_options: list[dict[str, Any]] = []
        for k, txt in self._options:
            clean_opt_txt = clean_chemical_formula_text(fix_arabic_bidi_scrambling(txt))
            m_opt_paren = re.match(r"^(\([^\)]+\))\s+([\u0600-\u06FF\s]{3,})$", clean_opt_txt)
            if m_opt_paren:
                clean_opt_txt = f"{m_opt_paren.group(2).strip()} {m_opt_paren.group(1).strip()}"
            for pattern in _UI_LEAK_PATTERNS:
                clean_opt_txt = pattern.sub("", clean_opt_txt)
            clean_opt_txt = re.sub(r"[ \t]{2,}", " ", clean_opt_txt).strip()
            formatted_options.append({"key": k, "text": clean_opt_txt, "is_correct": False})

        corr_text, needs_rev = resolve_correct_answer_text(
            formatted_options if formatted_options else None, ans_raw
        )

        # Determine Canonical Question Type
        has_opts = len(formatted_options) >= 2
        hint = self._section_hint or self.current_section_type

        if has_opts:
            if len(formatted_options) == 2 and any(
                "صح" in o["text"] or "خطأ" in o["text"] or "True" in o["text"] or "False" in o["text"]
                for o in formatted_options
            ):
                canonical_type = "TRUE_FALSE"
                primary_type = "true_false"
            else:
                canonical_type = "MCQ"
                primary_type = "multiple_choice"
        elif hint == "TRUE_FALSE" or any(w in stem_text for w in ["صح أم خطأ", "ضع علامة", "True/False", "صواب أم خطأ", "صح أو خطأ"]):
            canonical_type = "TRUE_FALSE"
            primary_type = "true_false"
            if not formatted_options:
                opt_true = {"key": "أ", "text": "صح", "is_correct": False}
                opt_false = {"key": "ب", "text": "خطأ", "is_correct": False}
                if ans_raw:
                    if any(t in ans_raw for t in ["صح", "صواب", "✓", "✔", "true"]):
                        opt_true["is_correct"] = True
                        corr_text = "صح"
                        needs_rev = False
                    elif any(f in ans_raw for f in ["خطأ", "خطا", "✗", "✘", "false"]):
                        opt_false["is_correct"] = True
                        corr_text = "خطأ"
                        needs_rev = False
                formatted_options = [opt_true, opt_false]
        elif hint == "FILL_BLANK" or any(w in stem_text for w in ["أكمل الفراغ", "أكمل ما يأتي", "أكمل العبارات", "Fill in the blank"]) or re.search(r"(\.{3,}|_{3,}|\[\s*\]|\[\.+\])", stem_text):
            canonical_type = "FILL_BLANK"
            primary_type = "fill_in_blank"
        elif hint == "ESSAY" or any(w in stem_text for w in ["علل", "بم تفسر", "وضح", "اشرح", "قارن", "اذكر", "ما المقصود", "اكتب", "احسب", "كيف"]):
            canonical_type = "ESSAY"
            primary_type = "essay"
        elif "؟" in stem_text or "?" in stem_text or len(stem_text.split()) >= 4:
            canonical_type = "ESSAY"
            primary_type = "essay"
        else:
            canonical_type = "UNKNOWN"
            primary_type = "unknown"
            needs_rev = True

        if canonical_type == "ESSAY":
            formatted_options = []
            corr_text = None
            needs_rev = False

        answer_confidence = "confirmed" if (corr_text and not needs_rev) else "unknown"

        record = {
            "question_text": stem_text,
            "question_type": primary_type,
            "canonical_type": canonical_type,
            "options": formatted_options if canonical_type == "ESSAY" else (formatted_options if formatted_options else None),
            "correct_answer": corr_text,
            "needs_answer_review": needs_rev,
            "answer_confidence": answer_confidence,
            "points": self._explicit_points,
            "needs_points_assignment": self._needs_points_assignment,
            "topic": self.filename or "عام",
            "classification_confidence": "high" if canonical_type != "UNKNOWN" else "uncertain",
            "source_page": self._source_page,
            "source_block_ids": list(self._source_block_ids),
            "raw_text": "\n".join(self._raw_lines),
        }
        self.extracted_questions.append(record)
        self._reset_builder()

    def _reset_builder(self) -> None:
        self._q_stem_parts = []
        self._options = []
        self._answer_raw = None
        self._explicit_points = None
        self._needs_points_assignment = True
        self._source_page = None
        self._source_block_ids = []
        self._raw_lines = []
        self._q_num = None
        self._section_hint = None

    def process_block(self, block_text: str, page_number: int | None = None, block_id: str | None = None) -> None:
        # Strip Unicode directional marks
        clean_block = re.sub(r"[\u200e\u200f\u202a-\u202e\ufeff]", "", block_text).strip()
        if not clean_block:
            return

        # Reject PDF binary corruption tokens
        if any(tok in clean_block for tok in ["FlateDecode", "endobj", "endstream", "/Type /Page", "/Resources", "/Contents"]):
            return

        lines = [l.strip() for l in clean_block.split("\n") if l.strip()]
        lines = strip_ui_leak_lines(lines)
        if not lines:
            return

        # Check if entire block is a distant answer key section
        if any(re.search(pat, clean_block, re.IGNORECASE) for pat in KEY_SECTION_PATTERNS):
            self._flush_active_question()
            return

        # Key normalization dictionary
        KEY_NORM = {
            'i': 'أ', '1': 'أ', 'a': 'أ', 'A': 'أ', 'أ': 'أ', 'ا': 'أ', 'ع': 'أ',
            '2': 'ب', 'b': 'ب', 'B': 'ب', 'ب': 'ب',
            '3': 'ج', 'c': 'ج', 'C': 'ج', 'ج': 'ج',
            '4': 'د', 'd': 'د', 'D': 'د', 'د': 'د',
        }
        OPT_PATTERN = re.compile(r"^[\(\[]?\s*([أبجدA-Da-d]|i)\s*[\)\]\.\:\-\/]\s*(.*)$")
        OPT_SUFFIX_PATTERN = re.compile(r"^(.*?)\s*[\(\[]\s*([أبجدA-Da-d]|i)\s*[\)\]][\.\:\-]?$")
        ANS_PATTERN = re.compile(
            r"^(?:الإجاب[ةه](?:\s+الصحيح[ةه])?|الجواب(?:\s+الصحيح)?|الحل(?:\s+الصحيح)?|فكرة\s+الحل|Answer|Key)\s*[\:\.\-\/]?\s*(.*)$",
            re.IGNORECASE,
        )
        INLINE_OPT_PATTERN = re.compile(
            r"(?:^|\s+)[\(\[]?\s*([أبجدA-D1-4]|i)\s*[\)\]\.\:\-\/]\s*(.*?)(?=(?:\s+[\(\[]?\s*[أبجدA-D1-4]|i\s*[\)\]\.\:\-\/]|$))"
        )
        HEADER_ONLY_PATTERN = re.compile(
            r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)|س\s*\d+|Question\s*\d+|Q\d+)\s*[\:\.\-\)]?\s*(?:\(?\s*\d+\s*(?:درجات|درجة|marks?|pts?)\s*\)?)?$",
            re.IGNORECASE,
        )

        SECTION_LOCAL_PATTERNS: list[tuple[re.Pattern, str]] = [
            (re.compile(r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)\s*[:\.\-]?\s*)?(?:اختر|إختر)\s+(?:الإجابة|الاجابة)\s+(?:الصحيحة|المناسبة|الأصح)", re.IGNORECASE), "MCQ"),
            (re.compile(r"^(?:أسئلة\s+الاختيار\s+من\s+متعدد|Multiple\s+Choice\s+Questions|MCQ)\b", re.IGNORECASE), "MCQ"),
            (re.compile(r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)\s*[:\.\-]?\s*)?(?:ضع\s+علامة|أجب\s+بـ|بين\s+مدى\s+صحة|صواب|صح)\b.*(?:صح|صواب|✓|✔).*(?:خطأ|خطا|✗|✘)", re.IGNORECASE), "TRUE_FALSE"),
            (re.compile(r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)\s*[:\.\-]?\s*)?(?:صواب|صح)\s*(?:أم|أو)\s*(?:خطأ|خطا)", re.IGNORECASE), "TRUE_FALSE"),
            (re.compile(r"^(?:True\s*(?:or|\/)\s*False)\b", re.IGNORECASE), "TRUE_FALSE"),
            (re.compile(r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)\s*[:\.\-]?\s*)?أكمل\s+(?:العبارات|الجمل|الفراغات|مكان\s+النقط|ما\s+يأتي)", re.IGNORECASE), "FILL_BLANK"),
            (re.compile(r"^(?:Fill\s+in\s+the\s+blanks?)\b", re.IGNORECASE), "FILL_BLANK"),
            (re.compile(r"^(?:\[?\s*(?:ثانياً|أولاً)?\s*[:\.]?\s*)?(?:الأسئلة\s+المقالية)\b", re.IGNORECASE), "ESSAY"),
            (re.compile(r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)\s*[:\.\-]?\s*)?(?:أجب|اجب)\s+عن\s+الأسئلة\s+(?:الآتية|التالية)", re.IGNORECASE), "ESSAY"),
        ]

        for line in lines:
            # 1. Section Header check
            is_section_header = False
            if not (self._q_num is not None and not self._q_stem_parts):
                for sec_pat, sec_type in SECTION_LOCAL_PATTERNS:
                    if sec_pat.search(line):
                        self._flush_active_question()
                        self.current_section_type = sec_type
                        self.current_section_title = line
                        is_section_header = True
                        break
            if is_section_header:
                continue

            # 2. Exclude administrative metadata
            if any(re.search(pat, line, re.IGNORECASE) for pat in ADMINISTRATIVE_METADATA_PATTERNS):
                continue

            # 3. Answer Line
            ans_match = ANS_PATTERN.match(line)
            if ans_match:
                raw_ans = ans_match.group(1).strip()
                raw_ans = re.sub(r"^(?:الصحيح[ةه]|الصواب)\s*[\:\.\-]?\s*", "", raw_ans, flags=re.IGNORECASE).strip()
                clean_ans = raw_ans.lstrip(":.-/ ").strip()
                if self._q_stem_parts:
                    self._answer_raw = clean_ans
                    self._raw_lines.append(line)
                continue

            # 4. Inline Options (e.g. (أ) ... (ب) ... (ج) ... (د) ...)
            inline_opts = INLINE_OPT_PATTERN.findall(line)
            if len(inline_opts) >= 2:
                for k, txt in inline_opts:
                    norm_k = KEY_NORM.get(k, k)
                    self._options.append((norm_k, txt.strip()))
                self._raw_lines.append(line)
                continue

            # 5. Single Line Option
            opt_m = OPT_PATTERN.match(line)
            opt_suff_m = OPT_SUFFIX_PATTERN.match(line)
            if self._q_stem_parts and opt_m and len(line.split()) < 30:
                norm_k = KEY_NORM.get(opt_m.group(1), opt_m.group(1))
                self._options.append((norm_k, opt_m.group(2).strip()))
                self._raw_lines.append(line)
                continue
            elif self._q_stem_parts and opt_suff_m and len(line.split()) <= 15:
                norm_k = KEY_NORM.get(opt_suff_m.group(2), opt_suff_m.group(2))
                self._options.append((norm_k, opt_suff_m.group(1).strip()))
                self._raw_lines.append(line)
                continue

            # 6. Question Start Detection
            norm_line = line.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
            is_q_start = bool(
                re.match(r"^(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)", norm_line, re.IGNORECASE)
                or re.match(r"^س\s*\d+\s*[\:\.\-\)]", norm_line)
                or re.match(r"^(?:Question|Q)\s*\d+\s*[\:\.\-\)]", norm_line, re.IGNORECASE)
                or re.match(r"^\(?\d{1,3}\)?\s*[\.\-\:]\s*(?!\d)", norm_line)
            )

            if is_q_start:
                self._flush_active_question()
                # Extract question number
                q_num_m = re.search(r"\(?(\d+)\)?", norm_line)
                self._q_num = q_num_m.group(1) if q_num_m else None
                # Clean prefix from stem
                clean_start = re.sub(
                    r"^(?:(?:السؤال|سؤال)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)|س\s*\d+|Question\s*\d+|Q\d+|^\(?\d{1,3}\)?)\s*[\:\.\-\)]?\s*",
                    "",
                    line,
                )
                # Check points in line
                pts, needs_pts = extract_explicit_points(line)
                self._explicit_points = pts
                self._needs_points_assignment = needs_pts
                self._section_hint = self.current_section_type
                self._source_page = page_number
                if block_id:
                    self._source_block_ids.append(block_id)
                self._raw_lines.append(line)
                if clean_start.strip():
                    clean_stem_start = clean_points_tokens_from_text(clean_start).strip()
                    if clean_stem_start:
                        self._q_stem_parts.append(clean_stem_start)
                continue

            # 7. Narrative or Continuation line
            if (self._q_stem_parts or self._q_num is not None) and not self._options:
                self._q_stem_parts.append(line)
                self._raw_lines.append(line)
                if not self._explicit_points:
                    pts, needs_pts = extract_explicit_points(line)
                    if pts is not None:
                        self._explicit_points = pts
                        self._needs_points_assignment = needs_pts
            elif not self._q_stem_parts:
                has_q_mark = "؟" in line or "?" in line
                starts_with_cmd = bool(re.match(r"^(?:علل|بم\s+تفسر|وضح|اشرح|قارن|ما\s+المقصود|اذكر|كيف|متى|أين|هل|ماذا)\b", line))
                if has_q_mark or starts_with_cmd or (self.current_section_type and len(line.split()) >= 3):
                    self._flush_active_question()
                    pts, needs_pts = extract_explicit_points(line)
                    self._explicit_points = pts
                    self._needs_points_assignment = needs_pts
                    self._section_hint = self.current_section_type
                    self._source_page = page_number
                    if block_id:
                        self._source_block_ids.append(block_id)
                    self._raw_lines.append(line)
                    self._q_stem_parts.append(line)

    def finish(self) -> list[dict[str, Any]]:
        self._flush_active_question()
        return self.extracted_questions


def segment_exam_document(
    parsed_doc: Any,
    distant_keys: dict[str, str] | None = None,
    filename: str = "",
) -> list[dict[str, Any]]:
    """
    Parses a ParsedDocument through the state machine ExamQuestionSegmenter.
    Extracts table questions first, then segments blocks and pages.
    """
    distant_keys = distant_keys or {}
    candidates: list[dict[str, Any]] = []

    # 1. Extract table questions
    table_questions = parse_table_questions(parsed_doc, distant_keys)
    candidates.extend(table_questions)

    # 2. Extract structured block questions via state machine
    segmenter = ExamQuestionSegmenter(distant_keys=distant_keys, filename=filename)
    if hasattr(parsed_doc, "pages"):
        for page in parsed_doc.pages:
            p_num = getattr(page, "page_number", 1)
            blocks = getattr(page, "blocks", [])
            for block in blocks:
                b_text = getattr(block, "text", "")
                b_id = getattr(block, "block_id", None)
                if b_text:
                    segmenter.process_block(b_text, page_number=p_num, block_id=b_id)
    elif isinstance(parsed_doc, str):
        segmenter.process_block(parsed_doc, page_number=1)
    elif isinstance(parsed_doc, list):
        for idx, item in enumerate(parsed_doc):
            segmenter.process_block(str(item), page_number=idx + 1)

    block_questions = segmenter.finish()
    candidates.extend(block_questions)

    for idx, q in enumerate(candidates, start=1):
        q["id"] = idx

    return candidates



