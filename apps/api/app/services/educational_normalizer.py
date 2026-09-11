"""
=============================================================================
MATGAR LMS - DYNAMIC EDUCATIONAL NORMALIZATION & KNOWLEDGE UNITS LAYER
=============================================================================
Architecture:
    Raw Transcript (ASR Output)
        ↓
    Transcript Segments (Raw preserved with timestamps)
        ↓
    Semantic / Educational Normalization (Generic MSA Linguistic Processing)
        ↓
    Knowledge Units (Dynamically Extracted Concepts & Propositions)
        ↓
    Pedagogical Question Generation (Purely Dynamic, Domain-Agnostic)

CRITICAL CONTRACT:
    - Absolutely ZERO hardcoded educational questions, concepts, answers, or facts.
    - Works seamlessly across all disciplines: Mathematics, Physics, Chemistry,
      Biology, Computer Science, Geology, History, Languages, etc.
    - Grounded in the lesson's transcript: The lesson content defines WHAT the
      questions are about; the code only defines HOW to synthesize questions.
=============================================================================
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeUnit:
    """A semantic pedagogical knowledge unit derived dynamically from normalized speech."""
    id: str
    lesson_id: str
    concept: str
    statement: str
    raw_text: str
    start_time: float
    end_time: float
    source_segment_ids: list[str] = field(default_factory=list)
    category: str = "general"  # definition, application, relationship, classification, general
    keywords: list[str] = field(default_factory=list)
    semantic_confidence: float = 1.0
    image_asset_ids: list[str] = field(default_factory=list)
    document_id: str | None = None
    page_number: int | None = None


# -----------------------------------------------------------------------------
# 1. DOMAIN-AGNOSTIC ARABIC COLLOQUIAL FILLER & SPEECH DISFLUENCY FILTERING
# -----------------------------------------------------------------------------

# Spoken conversational fillers that carry no educational substance in any subject
VOCALIC_FILLERS: list[str] = [
    r"\bبص\b", r"\bركز معايا\b", r"\bسمي الله\b", r"\bجميل جدا\b", r"\bزي ما انت شايف\b",
    r"\bيا سيدي\b", r"\bيا باشا\b", r"\bيا ابني\b", r"\bيا بنتي\b", r"\bيا دكتور\b", r"\bيا هندسة\b",
    r"\bيعني\b", r"\bها\b", r"\bبقى\b", r"\bاهو\b", r"\bكده\b", r"\bماشي\b", r"\bتمام\b",
    r"\bخلاص\b", r"\bيلا بينا\b", r"\bسواء كنت ميح\b", r"\bأو دحيح\b", r"\bهتفرم لك\b", r"\bحدوتة\b",
    r"\bحاول انت\b", r"\bده برضه\b", r"\bشايف ده\b", r"\bشايف ازاي\b", r"\bطول ما انت\b",
    r"\bعلشان كده\b", r"\bعلشان تبقى عارف\b", r"\bعايزك تعرف\b", r"\bتعال كده\b", r"\bبص كده\b",
    r"\bادي\b", r"\bزي مين زي\b", r"\bحاجة اسمها\b", r"\bعلى طابليه\b", r"\bبجامتك\b",
    r"\bمساء الخير\b", r"\bصباح الخير\b", r"\bيا شباب\b", r"\bيا رجالة\b", r"\bيا بنات\b",
    r"\bتكات وفنيات\b", r"\bسيب في الكومنتات\b", r"\bاشترك في القناة\b",
    r"\bsmartwatches\b", r"\bairpods\b", r"\bهدايا وجوائز\b", r"\bقرعة عشوائية\b"
]

# Pure grammatical conversions from Egyptian dialect conjugations to Modern Standard Arabic (MSA)
GENERIC_DIALECT_CONVERSIONS: list[tuple[str, str]] = [
    (r"\bإحنا بندرس\b", "ندرس"),
    (r"\bاحنا بندرس\b", "ندرس"),
    (r"\bبندرس\b", "ندرس"),
    (r"\bبيستخدم في\b", "يُستخدم في"),
    (r"\bبنستخدمه في\b", "يُستخدم في"),
    (r"\bبنستخدم\b", "نستخدم"),
    (r"\bبتستخدم\b", "تعتمد على"),
    (r"\bبيستخدم\b", "يستخدم"),
    (r"\bبتأثر في\b", "تؤثر في"),
    (r"\bبيأثر في\b", "يؤثر في"),
    (r"\bبيأثر على\b", "يؤثر على"),
    (r"\bعشان نعرف\b", "لمعرفة"),
    (r"\bعشان نحدد\b", "لتحديد"),
    (r"\bعشان ينتج\b", "لينتج"),
    (r"\bعشان\b", "بهدف"),
    (r"\bعلشان\b", "لكي"),
    (r"\bمن غير ما\b", "دون"),
    (r"\bيتلسب عكسي\b", "يتناسب عكسياً"),
    (r"\bبيتناسب عكسي\b", "يتناسب عكسياً"),
    (r"\bيتلسب طردي\b", "يتناسب طردياً"),
    (r"\bبيتناسب طردي\b", "يتناسب طردياً"),
    (r"\bبيقول إن\b", "ينص على أن"),
    (r"\bبيقول\b", "ينص"),
    (r"\bبتكسبه\b", "تكسبه"),
    (r"\bبتساوي\b", "تساوي"),
    (r"\bبيتساوى\b", "يتساوى"),
    (r"\bبيرتب\b", "يرتب"),
    (r"\bبيحمل\b", "يحمل"),
    (r"\bبتحول\b", "تحول"),
    (r"\bبتسرع\b", "تسرع"),
    (r"\bبتسمح\b", "تسمح"),
    (r"\bبتساعد\b", "تساعد"),
    (r"\bبتنتشر\b", "تنتشر"),
    (r"\bبتنشأ\b", "تنشأ"),
]

# Arabic stopwords to filter when extracting head concept titles
STOPWORDS_AR: set[str] = {
    "في", "من", "على", "عن", "إلى", "الى", "مع", "أو", "او", "ثم", "حيث", "أن", "ان",
    "هذا", "هذه", "ذلك", "تلك", "التي", "الذي", "الذين", "اللاتي", "ما", "ماذا", "لماذا",
    "كيف", "متى", "أين", "اين", "هل", "كل", "جميع", "بعض", "غير", "بين", "أمام", "خلف",
    "تحت", "فوق", "عند", "لدى", "مثل", "نحو", "قد", "لقد", "كان", "كانت", "يكون", "تكون",
    "هو", "هي", "هم", "هن", "نحن", "أنا", "انت", "أنت", "تعتبر", "يُعد", "يعد", "تعد",
    "توضح", "يوضح", "تتضمن", "يتضمن", "يقوم", "تقوم", "بهدف", "لكي", "دون", "ندرس"
}


def clean_spoken_noise(raw_text: str) -> str:
    """
    Cleans ASR formatting artifacts, marketing chatter, and vocalic fillers,
    converting spoken Egyptian verb patterns into formal Modern Standard Arabic (MSA).
    Zero domain or subject assumptions.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    # 1. Remove vocalic fillers and social media banter
    for pat in VOCALIC_FILLERS:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)

    # 2. Fix repeated word stuttering disfluencies (e.g. "في في", "من من")
    text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text)
    text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text)

    # 3. Apply dialectical grammatical conversions
    for pat, repl in GENERIC_DIALECT_CONVERSIONS:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # 4. Normalize spaces and punctuation
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[\s\.\,\:\-\؛\،]+", "", text)
    text = re.sub(r"[\s\.\,\:\-\؛\،]+$", "", text)
    return text


# -----------------------------------------------------------------------------
# 2. DYNAMIC KNOWLEDGE UNIT EXTRACTION (ZERO HARDCODED FACTS)
# -----------------------------------------------------------------------------

def reconstruct_educational_statement(cleaned_text: str) -> tuple[str, str, str]:
    """
    Dynamically reconstructs a formal educational statement and extracts its concept
    head noun phrase without any hardcoded subject knowledge.
    """
    t = cleaned_text.strip()
    words = t.split()
    if not words:
        return ("", "", "general")

    # 1. Dynamically extract the concept head noun phrase
    meaningful_words: list[str] = []
    for w in words:
        cleaned_w = re.sub(r"[^\w\u0621-\u064A]", "", w)
        if cleaned_w and cleaned_w not in STOPWORDS_AR and len(cleaned_w) > 1:
            meaningful_words.append(cleaned_w)
            if len(meaningful_words) >= 4:
                break

    if meaningful_words:
        concept = " ".join(meaningful_words)
    else:
        concept = " ".join(words[:min(4, len(words))])

    # 2. Structure formal statement
    statement = t
    if not statement.endswith("."):
        statement += "."

    # 3. Dynamically determine category based on grammatical relationships
    t_lower = t.lower()
    if any(k in t_lower for k in ["يتناسب", "علاقة", "تؤدي إلى", "يؤدي إلى", "نتيجة", "بسبب", "تأثير"]):
        category = "relationship"
    elif any(k in t_lower for k in ["يُستخدم", "يستخدم", "تطبيق", "طريقة", "استخدام", "تعتمد على"]):
        category = "application"
    elif any(k in t_lower for k in ["هو علم", "هي علم", "يُعرف", "تعريف", "المقصود", "يختص بدراسة", "عبارة عن"]):
        category = "definition"
    elif any(k in t_lower for k in ["ينقسم", "تتكون من", "يتكون من", "أنواع", "أقسام", "تصنيف"]):
        category = "classification"
    else:
        category = "general"

    return (concept, statement, category)


def extract_knowledge_units(
    segments: list[Any],
    lesson_id: str | uuid.UUID,
) -> list[KnowledgeUnit]:
    """
    Transforms raw ASR speech segments from ANY discipline into normalized,
    high-quality KnowledgeUnits with full timestamp traceability and anti-hallucination containment.
    """
    if not segments:
        return []

    from app.services.semantic_rewriter import (
        invoke_llm_semantic_rewriting,
        verify_semantic_faithfulness,
    )

    knowledge_units: list[KnowledgeUnit] = []
    seen_statements: set[str] = set()

    for idx, seg in enumerate(segments):
        raw_text = getattr(seg, "text", "") if hasattr(seg, "text") else seg.get("text", "")
        start_time = float(getattr(seg, "start_time", 0.0) if hasattr(seg, "start_time") else seg.get("start_time", 0.0))
        end_time = float(getattr(seg, "end_time", 0.0) if hasattr(seg, "end_time") else seg.get("end_time", 0.0))
        seg_id = str(getattr(seg, "id", f"seg_{idx}") if hasattr(seg, "id") else seg.get("id", f"seg_{idx}"))

        cleaned = clean_spoken_noise(raw_text)
        if len(cleaned.split()) < 3:
            continue

        # 1. Attempt LLM Semantic Rewriting
        llm_res = invoke_llm_semantic_rewriting(cleaned, raw_text, timeout=2.0)
        if llm_res and isinstance(llm_res, dict):
            concept = llm_res.get("concept", "")
            statement = llm_res.get("statement", "")
            category = llm_res.get("category", "general")
        else:
            concept, statement, category = reconstruct_educational_statement(cleaned)

        if not concept or not statement:
            continue

        # 2. Strict Independent Semantic Verification Layer
        verification = verify_semantic_faithfulness(raw_text, statement)
        if not verification.is_faithful:
            # Fallback to deterministic conservative rewrite if LLM added unsupported expansions or omitted facts
            concept, statement, category = reconstruct_educational_statement(cleaned)
            verification = verify_semantic_faithfulness(raw_text, statement)

        # Deduplicate identical consecutive propositions
        if statement in seen_statements:
            continue
        seen_statements.add(statement)

        ku = KnowledgeUnit(
            id=f"ku_{uuid.uuid4().hex[:12]}",
            lesson_id=str(lesson_id),
            concept=concept,
            statement=statement,
            raw_text=raw_text,
            start_time=start_time,
            end_time=end_time,
            source_segment_ids=[seg_id],
            category=category,
            keywords=[w for w in re.findall(r"\w+", concept.lower()) if len(w) > 2 and w not in STOPWORDS_AR],
            semantic_confidence=verification.semantic_confidence,
        )
        knowledge_units.append(ku)

    return knowledge_units


# -----------------------------------------------------------------------------
# 3. LEGACY / UNUSED QUESTION GENERATION GATES (DEPRECATED)
# IMPORTANT ARCHITECTURAL NOTE:
# The production quiz draft endpoint (/quiz/draft in ai_demo.py) uses
# `app.services.quiz_engine.generate_quiz`.
# These functions below are legacy/benchmark-only and are NOT invoked in the
# active LMS web application flow. Do not edit them for production quiz behavior.
# -----------------------------------------------------------------------------

def validate_question_quality(
    question_text: str,
    correct_answer: str | None,
    options: list[dict[str, Any]] | None,
    source_unit: KnowledgeUnit | None,
) -> tuple[bool, str]:
    """
    Validates linguistic, semantic, and pedagogical quality before returning a question.
    Rejects colloquial fillers, malformed sentences, and incomplete structures.
    """
    banned_tokens = [
        "بص", "ركز معايا", "سمي الله", "جميل جدا", "يا سيدي", "يا باشا",
        "بقى", "اهو", "كده", "ميح", "دحيح", "هتفرم",
        "smartwatches", "airpods", "زي مين زي", "حاجة اسمها", "ده برضه"
    ]
    full_text = f"{question_text} {correct_answer or ''}"
    if options:
        full_text += " " + " ".join(o.get("text", "") for o in options)

    for token in banned_tokens:
        if re.search(rf"\b{re.escape(token)}\b", full_text, flags=re.IGNORECASE):
            return False, f"Question contains banned colloquial/filler token: '{token}'"

    words = question_text.strip().split()
    if len(words) < 4:
        return False, "Question stem is too short to be semantically clear"

    if options:
        if len(options) not in (2, 4):
            return False, "Question must have either 2 options (True/False) or 4 options (MCQ)"
        option_texts = [o.get("text", "").strip() for o in options]
        if len(set(option_texts)) < len(option_texts):
            return False, "Options cannot contain duplicate choices"
        for opt in option_texts:
            if len(opt.split()) < 1:
                return False, "Option text cannot be empty"

    return True, "Valid"


# -----------------------------------------------------------------------------
# 4. PURELY DYNAMIC QUESTION GENERATION (ZERO HARDCODED FACTS)
# -----------------------------------------------------------------------------

def generate_educational_mcq(
    unit: KnowledgeUnit,
    all_units: list[KnowledgeUnit],
    idx: int,
) -> dict[str, Any]:
    """
    Dynamically generates a multiple-choice question from a KnowledgeUnit.
    All question stems, correct options, and distractors are constructed purely
    from the current lesson's units, with NO hardcoded domain facts.
    """
    import random
    seed_val = (idx + abs(hash(str(unit.id)))) % 100000
    random.seed(seed_val)

    # 1. Dynamic Question Stem based on grammatical category
    if unit.category == "definition":
        stem_templates = [
            f"ما المقصود بـ «{unit.concept}» وفقاً لما تم شرحه في الدرس؟",
            f"أي العبارات التالية تمثل التعريف الدقيق لـ «{unit.concept}»؟",
            f"ما المفهوم العلمي/الأكاديمي الدقيق الذي تناوله الدرس بخصوص «{unit.concept}»؟",
        ]
    elif unit.category == "application":
        stem_templates = [
            f"في أي السياقات أو المجالات يتم الاستناد إلى «{unit.concept}» وفقاً لما ورد في الشرح؟",
            f"أي من الخيارات التالية يمثل التطبيق الصحيح لـ «{unit.concept}»؟",
        ]
    elif unit.category == "relationship":
        stem_templates = [
            f"ما طبيعة العلاقة أو النتيجة التي تحكم «{unit.concept}» كما وضح المعلم؟",
            f"وفقاً لما تم شرحه في الدرس، ما النتيجة المترتبة على «{unit.concept}»؟",
        ]
    elif unit.category == "classification":
        stem_templates = [
            f"أي من المفاهيم أو العناصر التالية يرتبط بـ «{unit.concept}» وفق سياق الشرح؟",
            f"ما الخصائص المميزة لـ «{unit.concept}» بناءً على ما ورد في المحاضرة؟",
        ]
    else:
        stem_templates = [
            f"بناءً على ما تم شرحه في الدرس، أي من الخيارات التالية يعبّر بدقة عن «{unit.concept}»؟",
            f"وفقاً للمحتوى المشروح، ما التفسير الأنسب لما تم تناوله بخصوص «{unit.concept}»؟",
        ]

    q_text = stem_templates[idx % len(stem_templates)]
    correct_text = unit.statement

    # 2. Dynamic Distractors (prefer same category first, skip similarity > 0.7)
    def _token_sim(s1: str, s2: str) -> float:
        t1 = set(re.findall(r"\w+", s1.lower()))
        t2 = set(re.findall(r"\w+", s2.lower()))
        if not t1 or not t2:
            return 0.0
        return len(t1 & t2) / max(len(t1), len(t2))

    same_cat_statements = [
        u.statement for u in all_units
        if u.id != unit.id and getattr(u, "category", "") == unit.category
        and len(u.statement.split()) >= 4 and _token_sim(u.statement, correct_text) <= 0.7
    ]
    diff_cat_statements = [
        u.statement for u in all_units
        if u.id != unit.id and getattr(u, "category", "") != unit.category
        and len(u.statement.split()) >= 4 and _token_sim(u.statement, correct_text) <= 0.7
    ]

    available = same_cat_statements + diff_cat_statements
    if len(available) >= 3:
        if len(same_cat_statements) >= 3:
            sampled_distractors = random.sample(same_cat_statements, 3)
        else:
            remaining = 3 - len(same_cat_statements)
            sampled_distractors = list(same_cat_statements) + random.sample(diff_cat_statements, remaining)
        distractor_1, distractor_2, distractor_3 = sampled_distractors[0], sampled_distractors[1], sampled_distractors[2]
    else:
        distractor_1 = f"عدم انطباق الأثر أو المفهوم المشروح بخصوص «{unit.concept}»."
        distractor_2 = f"حدوث تأثير عكسي تماماً يؤدي إلى نفي النتيجة المشروحة."
        distractor_3 = f"انعدام أي ارتباط بين العناصر والمفاهيم المتناولة في هذا السياق."

    options_raw = [
        {"text": correct_text, "is_correct": True},
        {"text": distractor_1, "is_correct": False},
        {"text": distractor_2, "is_correct": False},
        {"text": distractor_3, "is_correct": False},
    ]

    # Rotate choices deterministically
    shift = idx % 4
    rotated_options = options_raw[shift:] + options_raw[:shift]
    arabic_keys = ["أ", "ب", "ج", "د"]
    final_options = [
        {"key": arabic_keys[k], "text": opt["text"], "is_correct": opt["is_correct"]}
        for k, opt in enumerate(rotated_options)
    ]

    if unit.start_time > 0 or unit.end_time > 0:
        start_min = int(unit.start_time) // 60
        start_sec = int(unit.start_time) % 60
        end_min = int(unit.end_time) // 60
        end_sec = int(unit.end_time) % 60
        time_fmt = f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"
        explanation = (
            f"الإجابة الصحيحة مستندة مباشرة إلى شرح الدرس عند التوقيت [{time_fmt}]: "
            f"«{unit.statement}»."
        )
    elif getattr(unit, "page_number", None):
        explanation = (
            f"الإجابة الصحيحة مستندة مباشرة إلى مذكرات الدرس (صفحة {unit.page_number}): "
            f"«{unit.statement}»."
        )
    else:
        explanation = f"الإجابة الصحيحة مستندة مباشرة إلى محتوى الدرس المشروح: «{unit.statement}»."

    media_ids = getattr(unit, "image_asset_ids", None) or getattr(unit, "source_media_ids_json", None) or []

    return {
        "question_text": q_text,
        "correct_answer": correct_text,
        "options": final_options,
        "explanation": explanation,
        "source_concept": unit.concept,
        "source_start_time": unit.start_time,
        "source_end_time": unit.end_time,
        "source_segment_ids": unit.source_segment_ids,
        "image_asset_ids": media_ids,
    }


def generate_educational_true_false(
    unit: KnowledgeUnit,
    all_units: list[KnowledgeUnit],
    idx: int,
    with_correction: bool = False,
) -> dict[str, Any]:
    """
    Dynamically generates a True/False question grounded in the KnowledgeUnit.
    Zero domain-specific hardcoded statements.
    """
    is_true_variant = (idx % 2 == 0)

    if is_true_variant:
        q_text = unit.statement
        corr_ans = "صح"
        expl = f"العبارة صحيحة ومطابقة تماماً لما تم شرحه في الدرس بخصوص «{unit.concept}»."
    else:
        # Formulate false proposition by contrasting with another unit from the same lesson
        other_units = [u for u in all_units if u.id != unit.id]
        if other_units:
            contrast_unit = other_units[idx % len(other_units)]
            q_text = f"يرتبط «{unit.concept}» بـ {contrast_unit.statement}"
        else:
            q_text = f"تنعدم صحة المفهوم أو النتيجة المرتبطة بـ «{unit.concept}» وفقاً لما تم شرحه."
        corr_ans = "خطأ"
        expl = f"العبارة خاطئة؛ لأن الصواب وفق ما ورد في الدرس هو: «{unit.statement}»."

    if with_correction:
        q_text += " (مع تصحيح الخطأ إن وجد)"

    if unit.start_time > 0 or unit.end_time > 0:
        start_min = int(unit.start_time) // 60
        start_sec = int(unit.start_time) % 60
        end_min = int(unit.end_time) // 60
        end_sec = int(unit.end_time) % 60
        time_fmt = f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"
        source_note = f" (المصدر: توقيت [{time_fmt}])"
    elif getattr(unit, "page_number", None):
        source_note = f" (المصدر: صفحة {unit.page_number})"
    else:
        source_note = " (المصدر: مذكرات الدرس)"

    media_ids = getattr(unit, "image_asset_ids", None) or getattr(unit, "source_media_ids_json", None) or []

    return {
        "question_text": q_text,
        "correct_answer": corr_ans,
        "options": [
            {"key": "أ", "text": "صح", "is_correct": corr_ans == "صح"},
            {"key": "ب", "text": "خطأ", "is_correct": corr_ans == "خطأ"},
        ],
        "explanation": f"{expl}{source_note}.",
        "withCorrection": with_correction,
        "source_concept": unit.concept,
        "source_start_time": unit.start_time,
        "source_end_time": unit.end_time,
        "source_segment_ids": unit.source_segment_ids,
        "image_asset_ids": media_ids,
    }


def generate_educational_essay(
    unit: KnowledgeUnit,
    idx: int,
) -> dict[str, Any]:
    """
    Dynamically generates an essay question and model answer from the KnowledgeUnit.
    """
    essay_q = (
        f"اشرح بالتفصيل ما تم تناوله في سياق «{unit.concept}» وفقاً لما ورد في المحاضرة، "
        f"موضحاً الأهمية والنتائج والمفاهيم المرتبطة بها."
    )
    model_answer = (
        f"نموذج الإجابة: {unit.statement} "
        f"مع توضيح الشواهد والأمثلة التي أوردها المعلم في سياق الشرح."
    )

    if unit.start_time > 0 or unit.end_time > 0:
        start_min = int(unit.start_time) // 60
        start_sec = int(unit.start_time) % 60
        end_min = int(unit.end_time) // 60
        end_sec = int(unit.end_time) % 60
        time_fmt = f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"
        expl = f"يقيس هذا السؤال الفهم التحليلي لـ «{unit.concept}» الواردة عند التوقيت [{time_fmt}]."
    elif getattr(unit, "page_number", None):
        expl = f"يقيس هذا السؤال الفهم التحليلي لـ «{unit.concept}» الواردة في صفحة {unit.page_number}."
    else:
        expl = f"يقيس هذا السؤال الفهم التحليلي لـ «{unit.concept}» الواردة في مذكرات الدرس."

    media_ids = getattr(unit, "image_asset_ids", None) or getattr(unit, "source_media_ids_json", None) or []

    return {
        "question_text": essay_q,
        "correct_answer": model_answer,
        "options": None,
        "explanation": expl,
        "source_concept": unit.concept,
        "source_start_time": unit.start_time,
        "source_end_time": unit.end_time,
        "source_segment_ids": unit.source_segment_ids,
        "image_asset_ids": media_ids,
    }


def generate_educational_fill_in_blank(
    unit: KnowledgeUnit,
    idx: int,
) -> dict[str, Any]:
    """
    Dynamically generates a fill-in-the-blank question by masking a key content word.
    """
    words = unit.statement.split()
    if len(words) >= 4:
        candidate_indices = [
            i for i, w in enumerate(words)
            if i > 0 and i < len(words) - 1 and re.sub(r"[^\w\u0621-\u064A]", "", w) not in STOPWORDS_AR and len(w) > 2
        ]
        target_idx = candidate_indices[len(candidate_indices) // 2] if candidate_indices else len(words) // 2
        target_word = words[target_idx].strip("،.؛:()")
        masked_words = list(words)
        masked_words[target_idx] = "__________"
        blank_q = f"أكمل العبارة التالية بما يناسب محتوى الشرح: {' '.join(masked_words)}"
        correct_term = target_word
    else:
        blank_q = f"المفهوم أو المصطلح الذي يعبّر عنه «{unit.statement}» هو __________."
        correct_term = unit.concept

    if unit.start_time > 0 or unit.end_time > 0:
        start_min = int(unit.start_time) // 60
        start_sec = int(unit.start_time) % 60
        end_min = int(unit.end_time) // 60
        end_sec = int(unit.end_time) % 60
        time_fmt = f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"
        expl = f"المصطلح أو العبارة المكملة وفقاً للدرس عند التوقيت [{time_fmt}]."
    elif getattr(unit, "page_number", None):
        expl = f"المصطلح أو العبارة المكملة وفقاً للدرس في صفحة {unit.page_number}."
    else:
        expl = "المصطلح أو العبارة المكملة وفقاً لمحتوى مذكرات الدرس."

    media_ids = getattr(unit, "image_asset_ids", None) or getattr(unit, "source_media_ids_json", None) or []

    return {
        "question_text": blank_q,
        "correct_answer": correct_term,
        "options": None,
        "explanation": expl,
        "source_concept": unit.concept,
        "source_start_time": unit.start_time,
        "source_end_time": unit.end_time,
        "source_segment_ids": unit.source_segment_ids,
        "image_asset_ids": media_ids,
    }
