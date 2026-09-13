"""
=============================================================================
MATGAR LMS — QUIZ INTELLIGENCE ENGINE & ASSESSMENT KNOWLEDGE HUB
=============================================================================
Architecture:

    Full Lesson Knowledge Units + Assessment Style Bank
            ↓
    ConceptMapper — groups KUs by concept, ranks educational importance
            ↓
    QuestionSuitabilityAnalyzer — determines valid question types per concept
            ↓
    DiversityPlanner — selects distinct concepts, assigns question types
            ↓
    QuestionGenerator & Bank Selector — Mode A (Reuse), Mode B (Novel), Mode C (Hybrid)
            ↓
    Image-Aware Asset Attacher — attaches diagrams/figures with media[] roles
            ↓
    IndependentValidator — rejects duplicates, generics, unsupported facts
            ↓
    Final Quiz

Priority order:
    Educational quality > Content diversity > Grounding > Requested count

CRITICAL CONTRACT:
    - Zero hardcoded educational questions, concepts, answers, or facts.
    - Works across ALL disciplines.
    - The lesson/sources determine WHAT the quiz contains.
    - The code determines HOW the quiz is generated.
=============================================================================
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.educational_normalizer import KnowledgeUnit

# Arabic stopwords for semantic comparison
_STOPWORDS: set[str] = {
    "في", "من", "على", "عن", "إلى", "الى", "مع", "أو", "او", "ثم", "حيث", "أن", "ان",
    "هذا", "هذه", "ذلك", "تلك", "التي", "الذي", "ما", "هو", "هي", "هم", "هن",
    "كل", "جميع", "بعض", "غير", "بين", "عند", "مثل", "نحو", "قد", "كان", "كانت",
    "يكون", "تكون", "نحن", "أنا", "انت", "أنت", "تم", "يتم", "دون", "بهدف",
    "لكي", "بأن", "لما", "ليس", "ليست", "جدا", "جداً", "خاصة",
}

# Banned generic distractor phrases — these must NEVER appear in production output
BANNED_GENERIC_DISTRACTORS: list[str] = [
    "عدم انطباق الأثر",
    "عدم انطباق المفهوم",
    "انعدام الارتباط",
    "انعدام أي ارتباط",
    "حدوث تأثير عكسي",
    "لا شيء مما سبق",
    "كل ما سبق",
    "جميع ما سبق",
    "لا توجد إجابة صحيحة",
    "تنعدم صحة المفهوم",
]

# Banned essay meta-question patterns
BANNED_ESSAY_PATTERNS: list[str] = [
    "اشرح بالتفصيل ما تم تناوله في سياق",
    "اشرح الكلام المذكور",
    "ماذا تم شرحه",
    "اشرح ما تم تناوله",
    "وضح ما تم ذكره",
]

# Banned colloquial tokens in questions
BANNED_COLLOQUIAL: list[str] = [
    "بص", "ركز معايا", "سمي الله", "جميل جدا", "يا سيدي", "يا باشا",
    "يعني", "بقى", "اهو", "كده", "ميح", "دحيح", "هتفرم",
    "زي مين زي", "حاجة اسمها", "ده برضه", "smartwatches", "airpods",
]


# =============================================================================
# 1. CONCEPT MAPPING
# =============================================================================

@dataclass
class ConceptGroup:
    """Groups related KnowledgeUnits under one learning concept."""
    concept_id: str
    label: str
    knowledge_units: list[KnowledgeUnit] = field(default_factory=list)
    importance_score: float = 0.0
    richness_score: float = 0.0
    semantic_type: str = "general"
    source_times: list[tuple[float, float]] = field(default_factory=list)
    supporting_claims: list[str] = field(default_factory=list)


def _normalize_concept_key(text: str) -> str:
    """Normalize a concept string for semantic grouping comparison."""
    t = re.sub(r"[\u064B-\u0652\u0640]", "", text.lower().strip())
    t = re.sub(r"[إأآا]", "ا", t)
    t = re.sub(r"[ة]", "ه", t)
    t = re.sub(r"[ى]", "ي", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _extract_content_tokens(text: str) -> set[str]:
    """Extract meaningful content tokens, excluding stopwords."""
    return {
        _normalize_concept_key(w)
        for w in text.split()
        if len(w) > 2 and w not in _STOPWORDS
    }


def _token_overlap_ratio(a: str, b: str) -> float:
    """Compute bidirectional token overlap ratio between two texts."""
    tokens_a = _extract_content_tokens(a)
    tokens_b = _extract_content_tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    return overlap / min(len(tokens_a), len(tokens_b))


def _infer_semantic_type(units: list[KnowledgeUnit]) -> str:
    """Infer the dominant semantic type from a group of KnowledgeUnits."""
    type_signals: dict[str, int] = {
        "definition": 0, "fact": 0, "classification": 0,
        "relationship": 0, "cause_effect": 0, "comparison": 0,
        "process": 0, "application": 0, "quantitative": 0,
    }

    for u in units:
        text = u.statement.lower()
        if u.category == "definition" or any(k in text for k in ("هو علم", "هي علم", "يُعرف", "المقصود", "عبارة عن", "يختص بدراسة", "تعريف")):
            type_signals["definition"] += 2
        if u.category == "relationship" or any(k in text for k in ("تؤدي إلى", "يؤدي إلى", "نتيجة", "بسبب", "تأثير", "علاقة")):
            type_signals["relationship"] += 2
            if any(k in text for k in ("بسبب", "نتيجة", "تؤدي", "يؤدي")):
                type_signals["cause_effect"] += 1
        if u.category == "application" or any(k in text for k in ("يستخدم", "يُستخدم", "تطبيق", "استخدام", "تعتمد على")):
            type_signals["application"] += 2
        if u.category == "classification" or any(k in text for k in ("ينقسم", "تتكون من", "يتكون من", "أنواع", "أقسام", "نوعين")):
            type_signals["classification"] += 2
        if any(k in text for k in ("مقارنة", "بينما", "على عكس", "الفرق بين", "في حين")):
            type_signals["comparison"] += 2
        if any(k in text for k in ("خطوات", "مراحل", "أولاً", "ثانياً", "ثم", "بعد ذلك")):
            type_signals["process"] += 2
        if re.search(r"\d+\s*(كيلو|متر|جرام|درجة|سنتي|مليون|في المية|%)", text):
            type_signals["quantitative"] += 2

    best_type = max(type_signals, key=lambda k: type_signals[k])
    return best_type if type_signals[best_type] > 0 else "fact"


def map_concepts(units: list[KnowledgeUnit]) -> list[ConceptGroup]:
    """
    Groups KnowledgeUnits into ConceptGroups by semantic similarity.
    Two KUs are grouped when they describe the same underlying learning concept.
    """
    if not units:
        return []

    groups: list[ConceptGroup] = []

    for unit in units:
        best_match: ConceptGroup | None = None
        best_overlap = 0.0

        for group in groups:
            # Compare concept labels and statement content
            concept_sim = _token_overlap_ratio(unit.concept, group.label)
            statement_sim = max(
                _token_overlap_ratio(unit.statement, ku.statement)
                for ku in group.knowledge_units
            )
            combined = max(concept_sim, statement_sim * 0.8)

            if combined > best_overlap and combined >= 0.55:
                best_match = group
                best_overlap = combined

        if best_match is not None:
            best_match.knowledge_units.append(unit)
            best_match.source_times.append((unit.start_time, unit.end_time))
            best_match.supporting_claims.append(unit.statement)
        else:
            groups.append(ConceptGroup(
                concept_id=f"cg_{unit.id}",
                label=unit.concept,
                knowledge_units=[unit],
                source_times=[(unit.start_time, unit.end_time)],
                supporting_claims=[unit.statement],
            ))

    # Score each group
    for group in groups:
        group.semantic_type = _infer_semantic_type(group.knowledge_units)
        n_units = len(group.knowledge_units)

        # Richness: average content word count across supporting claims
        avg_words = sum(len(c.split()) for c in group.supporting_claims) / max(1, n_units)
        group.richness_score = min(1.0, avg_words / 15.0)

        # Importance: multi-signal scoring
        importance = 0.0
        importance += min(3.0, n_units) * 0.15  # more supporting KUs = more important (capped)
        importance += group.richness_score * 0.25  # richer = more important
        if group.semantic_type in ("definition", "classification"):
            importance += 0.25  # definitions and classifications are high-value
        if group.semantic_type in ("cause_effect", "comparison", "process"):
            importance += 0.2  # analytical concepts are high-value
        if group.semantic_type == "quantitative":
            importance += 0.15  # specific facts are testable
        group.importance_score = min(1.0, importance)

    # Sort by importance (highest first)
    groups.sort(key=lambda g: g.importance_score, reverse=True)
    return groups


# =============================================================================
# 2. QUESTION SUITABILITY ANALYSIS
# =============================================================================

@dataclass
class SuitabilityProfile:
    """Determines which question types a concept can meaningfully support."""
    multiple_choice: bool = False
    true_false: bool = False
    essay: bool = False
    fill_blank: bool = False
    short_answer: bool = False
    numerical: bool = False
    image_question: bool = False


def assess_question_suitability(
    group: ConceptGroup,
    total_groups: int,
) -> SuitabilityProfile:
    """
    Determines which question types a concept group can meaningfully support.
    Does NOT force all types onto every concept.
    """
    profile = SuitabilityProfile()
    primary_statement = group.supporting_claims[0] if group.supporting_claims else ""
    word_count = len(primary_statement.split())
    sem_type = group.semantic_type

    # MCQ: needs enough content for a clear question + needs other groups for distractors
    if word_count >= 5 and total_groups >= 3:
        profile.multiple_choice = True

    # True/False: needs a clear factual/definitional claim
    if word_count >= 5 and sem_type in ("definition", "fact", "classification", "quantitative", "relationship", "cause_effect", "application"):
        profile.true_false = True

    # Essay: needs analytical depth — relationships, cause/effect, comparisons, processes, classifications
    if sem_type in ("cause_effect", "comparison", "process", "classification", "relationship") and word_count >= 8:
        profile.essay = True
    elif len(group.knowledge_units) >= 2 and word_count >= 8:
        # Multiple supporting KUs → enough depth for essay
        profile.essay = True

    # Fill-in-blank: needs a key identifiable term
    content_words = [
        w for w in primary_statement.split()
        if len(w) > 2 and w not in _STOPWORDS and re.sub(r"[^\w\u0621-\u064A]", "", w)
    ]
    if len(content_words) >= 3:
        profile.fill_blank = True

    # A short response can be grounded in any sufficiently explicit source claim.
    if word_count >= 5:
        profile.short_answer = True
    # Do not fabricate a calculation: only offer this when the source itself has
    # a number, an equation, or a quantitative semantic classification.
    if sem_type == "quantitative" or re.search(r"\d|[=+*/^]", primary_statement):
        profile.numerical = True
    # Image questions always retain a source-media attachment and therefore are
    # only planned for units that actually reference a stored image.
    if getattr(group.knowledge_units[0], "image_asset_ids", None):
        profile.image_question = True

    return profile


# =============================================================================
# 3. DIVERSITY PLANNING
# =============================================================================

@dataclass
class QuestionPlan:
    """A planned question before generation."""
    concept_group: ConceptGroup
    question_type: str  # multiple_choice, true_false, essay, fill_in_blank, short_answer, numerical, image_question
    learning_objective: str  # recall, understanding, comparison, application, analysis, classification, cause_effect
    difficulty: str  # easy, medium, hard
    primary_unit: KnowledgeUnit  # the main KU sourcing this question


def _assign_learning_objective(sem_type: str, q_type: str) -> str:
    """Assign a learning objective based on semantic type and question type."""
    objective_map: dict[tuple[str, str], str] = {
        ("definition", "multiple_choice"): "recall",
        ("definition", "true_false"): "understanding",
        ("definition", "fill_in_blank"): "recall",
        ("definition", "essay"): "understanding",
        ("definition", "short_answer"): "recall",
        ("fact", "multiple_choice"): "recall",
        ("fact", "true_false"): "recall",
        ("fact", "fill_in_blank"): "recall",
        ("classification", "multiple_choice"): "classification",
        ("classification", "true_false"): "understanding",
        ("classification", "essay"): "classification",
        ("classification", "fill_in_blank"): "recall",
        ("relationship", "multiple_choice"): "understanding",
        ("relationship", "true_false"): "understanding",
        ("relationship", "essay"): "analysis",
        ("cause_effect", "multiple_choice"): "cause_effect",
        ("cause_effect", "true_false"): "cause_effect",
        ("cause_effect", "essay"): "analysis",
        ("comparison", "multiple_choice"): "comparison",
        ("comparison", "essay"): "comparison",
        ("application", "multiple_choice"): "application",
        ("application", "true_false"): "application",
        ("application", "essay"): "application",
        ("process", "multiple_choice"): "understanding",
        ("process", "essay"): "analysis",
        ("quantitative", "multiple_choice"): "recall",
        ("quantitative", "true_false"): "recall",
        ("quantitative", "fill_in_blank"): "recall",
        ("quantitative", "numerical"): "application",
        ("quantitative", "short_answer"): "understanding",
    }
    return objective_map.get((sem_type, q_type), "understanding")


def _assign_difficulty(q_type: str, sem_type: str) -> str:
    """Assign difficulty based on cognitive demand, not sentence length."""
    if q_type == "essay":
        return "hard"
    if q_type == "numerical":
        return "medium" if sem_type == "quantitative" else "hard"
    if q_type == "image_question":
        return "medium"
    if q_type == "short_answer":
        return "easy" if sem_type in ("definition", "fact") else "medium"
    if q_type == "fill_in_blank":
        return "easy" if sem_type in ("definition", "fact") else "medium"
    if q_type == "true_false":
        return "easy" if sem_type in ("definition", "fact") else "medium"
    # MCQ
    if sem_type in ("comparison", "cause_effect", "process", "application"):
        return "hard"
    if sem_type in ("classification", "relationship"):
        return "medium"
    return "medium"


def plan_question_diversity(
    concept_groups: list[ConceptGroup],
    type_allocations: list[dict[str, Any]],
    requested_count: int,
) -> tuple[list[QuestionPlan], dict[str, Any]]:
    """
    Plans a diverse question set across concepts, types, and timeline.
    Returns (plans, metadata) where metadata includes requested/generated counts.
    """
    if not concept_groups:
        return [], {"requested_count": requested_count, "generated_count": 0, "insufficient_content": True}

    total_groups = len(concept_groups)
    profiles: list[tuple[ConceptGroup, SuitabilityProfile]] = [
        (g, assess_question_suitability(g, total_groups))
        for g in concept_groups
    ]

    type_counts: dict[str, int] = {}
    type_extras: dict[str, dict[str, Any]] = {}
    if type_allocations:
        for alloc in type_allocations:
            tid = alloc.get("id", "multiple_choice")
            count = int(alloc.get("count", 0))
            if count > 0:
                type_counts[tid] = count
                type_extras[tid] = alloc
    else:
        type_counts["multiple_choice"] = max(1, requested_count - 1)
        type_counts["essay"] = 1

    plans: list[QuestionPlan] = []
    used_concept_ids: set[str] = set()

    for q_type, count in type_counts.items():
        suitability_key = {
            "multiple_choice": "multiple_choice",
            "true_false": "true_false",
            "essay": "essay",
            "fill_in_blank": "fill_blank",
            "short_answer": "short_answer",
            "numerical": "numerical",
            "image_question": "image_question",
        }.get(q_type, "multiple_choice")

        eligible = [
            (g, p) for g, p in profiles
            if getattr(p, suitability_key, False)
        ]

        if not eligible:
            continue

        generated_for_type = 0
        cycle = 0
        while generated_for_type < count:
            unused_eligible = [(g, p) for g, p in eligible if g.concept_id not in used_concept_ids]
            pool = unused_eligible if unused_eligible else eligible

            if not pool:
                break

            idx = cycle % len(pool)
            group, _ = pool[idx]

            ku_idx = cycle % len(group.knowledge_units)
            primary_unit = group.knowledge_units[ku_idx]

            plan = QuestionPlan(
                concept_group=group,
                question_type=q_type,
                learning_objective=_assign_learning_objective(group.semantic_type, q_type),
                difficulty=_assign_difficulty(q_type, group.semantic_type),
                primary_unit=primary_unit,
            )
            plans.append(plan)
            used_concept_ids.add(group.concept_id)
            generated_for_type += 1
            cycle += 1

            if cycle >= len(eligible) * 2:
                break

    if plans:
        plans.sort(key=lambda p: p.primary_unit.start_time)

    if plans:
        all_times = [p.primary_unit.start_time for p in plans]
        min_t, max_t = min(all_times), max(all_times)
        span = max(1.0, max_t - min_t)
        third = span / 3.0
        timeline = {
            "beginning": sum(1 for t in all_times if t < min_t + third),
            "middle": sum(1 for t in all_times if min_t + third <= t < min_t + 2 * third),
            "end": sum(1 for t in all_times if t >= min_t + 2 * third),
        }
    else:
        timeline = {"beginning": 0, "middle": 0, "end": 0}

    metadata = {
        "requested_count": requested_count,
        "generated_count": len(plans),
        "insufficient_content": len(plans) < requested_count,
        "distinct_concepts": len(used_concept_ids),
        "timeline_coverage": timeline,
    }

    return plans, metadata


# =============================================================================
# 4. QUESTION GENERATION — ZERO HARDCODED CONTENT
# =============================================================================

def _format_time(seconds: float) -> str:
    """Format seconds into MM:SS."""
    m, s = int(seconds) // 60, int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def _build_explanation(unit: KnowledgeUnit, context: str = "") -> str:
    """Build a grounded explanation citing the document page or lesson timestamp."""
    if getattr(unit, "page_number", None) and unit.page_number > 0:
        base = f"مستند إلى وثائق ومذكرات الدرس (الصفحة {unit.page_number})"
    elif (getattr(unit, "start_time", 0.0) or 0.0) > 0 or (getattr(unit, "end_time", 0.0) or 0.0) > 0:
        time_range = f"{_format_time(unit.start_time)} - {_format_time(unit.end_time)}"
        base = f"مستند إلى شرح الدرس عند التوقيت [{time_range}]"
    else:
        base = "مستند مباشرة إلى نص ومذكرات الدرس"

    if context:
        return f"{context} ({base})."
    return f"{base}: «{unit.statement}»."


def _is_valid_distractor_statement(stmt: str, target_stmt: str) -> bool:
    """Validates that a statement is a coherent, complete explanatory distractor."""
    s = stmt.strip()
    if not s or s == target_stmt:
        return False
    words = s.split()
    if len(words) < 5 or len(words) > 35:
        return False
    target_has_arrow = any(a in target_stmt for a in ["->", "→", "<=>", "⇌"])
    if not target_has_arrow and any(a in s for a in ["->", "→", "<=>", "⇌"]):
        return False
    if re.match(r"^[\(\[]?\s*[أبجدA-Da-d]\s*[\)\]\.\:\-]", s):
        return False
    if any(k in s for k in ["الإجابة الصحيحة", "الحل:", "Answer:", "Key:"]):
        return False
    if any(banned in s for banned in BANNED_GENERIC_DISTRACTORS):
        return False
    return True


def generate_mcq(
    plan: QuestionPlan,
    all_groups: list[ConceptGroup],
) -> dict[str, Any] | None:
    """
    Generates a high-quality MCQ with concept-aware distractors.
    Returns None if valid distractors cannot be created.
    """
    import random
    random.seed(hash(plan.primary_unit.id) % (2**31))

    unit = plan.primary_unit
    group = plan.concept_group
    sem_type = group.semantic_type
    concept_label = group.label

    if sem_type == "definition":
        stems = [
            f"أي العبارات التالية تمثل التعريف الدقيق لـ «{concept_label}»؟",
            f"ما المقصود بـ «{concept_label}» وفقاً لما ورد في الدرس؟",
        ]
    elif sem_type == "classification":
        stems = [
            f"أي التصنيفات التالية ينطبق على «{concept_label}» وفقاً للدرس؟",
            f"ما الخصائص المميزة لـ «{concept_label}» بناءً على المحاضرة؟",
        ]
    elif sem_type in ("relationship", "cause_effect"):
        stems = [
            f"ما النتيجة المترتبة على «{concept_label}» كما وضّح المعلم؟",
            f"ما العلاقة التي تربط «{concept_label}» بالمفاهيم المشروحة في الدرس؟",
        ]
    elif sem_type == "application":
        stems = [
            f"في أي سياق يُستخدم «{concept_label}» وفقاً للدرس؟",
            f"ما التطبيق العملي لـ «{concept_label}» بناءً على المحاضرة؟",
        ]
    elif sem_type == "comparison":
        stems = [
            f"أي العبارات التالية تصف «{concept_label}» بدقة وفقاً للمقارنة الواردة في الدرس؟",
        ]
    elif sem_type == "quantitative":
        stems = [
            f"ما القيمة أو المقدار المرتبط بـ «{concept_label}» وفقاً للدرس؟",
        ]
    else:
        stems = [
            f"أي العبارات التالية يعبّر بدقة عن «{concept_label}» وفقاً للدرس؟",
        ]

    q_text = stems[hash(unit.id) % len(stems)]
    correct_text = unit.statement

    # Concept-aware distractors prioritizing same semantic category
    other_groups = [g for g in all_groups if g.concept_id != group.concept_id]
    same_type_candidates: list[str] = []
    other_type_candidates: list[str] = []

    for og in other_groups:
        for ku in og.knowledge_units:
            stmt = ku.statement
            if _is_valid_distractor_statement(stmt, correct_text):
                if og.semantic_type == sem_type:
                    same_type_candidates.append(stmt)
                else:
                    other_type_candidates.append(stmt)

    random.shuffle(same_type_candidates)
    random.shuffle(other_type_candidates)

    combined_candidates = same_type_candidates + other_type_candidates
    seen_st: set[str] = set()
    candidate_distractors: list[str] = []
    for c in combined_candidates:
        if c not in seen_st:
            seen_st.add(c)
            candidate_distractors.append(c)

    if len(candidate_distractors) < 3:
        return None

    distractors = candidate_distractors[:3]

    options_raw = [
        {"text": correct_text, "is_correct": True},
        {"text": distractors[0], "is_correct": False},
        {"text": distractors[1], "is_correct": False},
        {"text": distractors[2], "is_correct": False},
    ]
    shift = hash(unit.id) % 4
    rotated = options_raw[shift:] + options_raw[:shift]
    keys = ["أ", "ب", "ج", "د"]
    final_options = [
        {"key": keys[i], "text": opt["text"], "is_correct": opt["is_correct"]}
        for i, opt in enumerate(rotated)
    ]

    return {
        "question_type": "multiple_choice",
        "question_text": q_text,
        "correct_answer": correct_text,
        "options": final_options,
        "explanation": _build_explanation(unit, "الإجابة الصحيحة مستندة مباشرة إلى شرح الدرس"),
        "source_concept": concept_label,
        "source_start_time": unit.start_time,
        "source_end_time": unit.end_time,
        "source_segment_ids": unit.source_segment_ids,
        "source_knowledge_unit_ids": [unit.id],
        "learning_objective": plan.learning_objective,
        "difficulty": plan.difficulty,
    }


def generate_true_false(
    plan: QuestionPlan,
    all_groups: list[ConceptGroup],
    with_correction: bool = False,
) -> dict[str, Any]:
    """Generates a True/False question targeting identifiable misconceptions."""
    import random
    random.seed(hash(plan.primary_unit.id) % (2**31))

    unit = plan.primary_unit
    group = plan.concept_group
    is_true = (hash(unit.id) % 2 == 0)

    if is_true:
        q_text = unit.statement
        correct = "صح"
        explanation = f"العبارة صحيحة ومطابقة لما ورد في الدرس بخصوص «{group.label}»."
    else:
        other_groups = [g for g in all_groups if g.concept_id != group.concept_id]
        false_statement = ""
        if other_groups and len(unit.statement.split()) >= 6:
            words = unit.statement.split()
            content_indices = [
                i for i, w in enumerate(words)
                if len(w) > 2 and w not in _STOPWORDS and re.sub(r"[^\w\u0621-\u064A]", "", w)
            ]

            if content_indices and other_groups:
                swap_idx = content_indices[len(content_indices) // 2]
                original_word = words[swap_idx]

                replacement = None
                for og in other_groups:
                    for claim in og.supporting_claims:
                        claim_tokens = [
                            w for w in claim.split()
                            if len(w) > 2 and w not in _STOPWORDS
                        ]
                        for ct in claim_tokens:
                            if ct != original_word and len(ct) >= 3:
                                replacement = ct
                                break
                        if replacement:
                            break
                    if replacement:
                        break

                if replacement:
                    modified_words = list(words)
                    modified_words[swap_idx] = replacement
                    false_statement = " ".join(modified_words)

        if not false_statement:
            false_statement = f"لا يرتبط «{group.label}» بالمفهوم الوارد في عبارة: {unit.statement}"

        q_text = false_statement
        correct = "خطأ"
        explanation = f"العبارة خاطئة؛ الصواب وفق الدرس: «{unit.statement}»."

    suffix = " (مع تصحيح الخطأ إن وجد)" if with_correction else ""
    q_text += suffix

    return {
        "question_type": "true_false",
        "question_text": q_text,
        "correct_answer": correct,
        "options": [
            {"key": "أ", "text": "صح", "is_correct": correct == "صح"},
            {"key": "ب", "text": "خطأ", "is_correct": correct == "خطأ"},
        ],
        "explanation": _build_explanation(unit, explanation),
        "withCorrection": with_correction,
        "source_concept": group.label,
        "source_start_time": unit.start_time,
        "source_end_time": unit.end_time,
        "source_segment_ids": unit.source_segment_ids,
        "source_knowledge_unit_ids": [unit.id],
        "learning_objective": plan.learning_objective,
        "difficulty": plan.difficulty,
    }


def generate_essay(
    plan: QuestionPlan,
    all_groups: list[ConceptGroup],
) -> dict[str, Any]:
    """Generates a targeted analytical essay question."""
    unit = plan.primary_unit
    group = plan.concept_group
    sem_type = group.semantic_type
    concept_label = group.label

    other_groups = [g for g in all_groups if g.concept_id != group.concept_id]
    related_concept = other_groups[0].label if other_groups else None

    if sem_type == "comparison" and related_concept:
        q_text = f"قارن بين «{concept_label}» و«{related_concept}» موضحاً أوجه التشابه والاختلاف بينهما وفقاً لما ورد في الدرس."
    elif sem_type == "cause_effect":
        q_text = f"وضّح العلاقة السببية المرتبطة بـ «{concept_label}»، مبيناً الأسباب والنتائج كما شرحها المعلم."
    elif sem_type == "process":
        q_text = f"اشرح المراحل والخطوات المتعلقة بـ «{concept_label}» وفقاً للدرس، مع ترتيبها المنطقي."
    elif sem_type == "classification" and len(group.knowledge_units) >= 2:
        q_text = f"صنّف «{concept_label}» مبيناً الأنواع والفروق الرئيسية بينها وفقاً للمحاضرة."
    elif sem_type == "application":
        q_text = f"اشرح كيف يُستخدم «{concept_label}» عملياً مع ذكر الأمثلة الواردة في الدرس."
    elif sem_type == "definition" and related_concept:
        q_text = f"عرّف «{concept_label}» موضحاً خصائصه الرئيسية وعلاقته بـ «{related_concept}» وفقاً للمحاضرة."
    elif sem_type == "relationship" and related_concept:
        q_text = f"وضّح العلاقة بين «{concept_label}» و«{related_concept}» وأثر كل منهما على الآخر وفقاً للدرس."
    else:
        q_text = f"عرّف «{concept_label}» موضحاً خصائصه الرئيسية وأهميته العلمية وفقاً لما ورد في المحاضرة."

    claims = group.supporting_claims[:3]
    model_answer = " ".join(claims) + "."

    return {
        "question_type": "essay",
        "question_text": q_text,
        "correct_answer": model_answer,
        "options": None,
        "explanation": _build_explanation(unit, f"يقيس هذا السؤال القدرة التحليلية للطالب بخصوص «{concept_label}»"),
        "source_concept": concept_label,
        "source_start_time": unit.start_time,
        "source_end_time": unit.end_time,
        "source_segment_ids": unit.source_segment_ids,
        "source_knowledge_unit_ids": [ku.id for ku in group.knowledge_units],
        "learning_objective": plan.learning_objective,
        "difficulty": plan.difficulty,
    }


def generate_fill_blank(plan: QuestionPlan) -> dict[str, Any]:
    """Generates a fill-in-the-blank question masking the actual key learning term."""
    unit = plan.primary_unit
    group = plan.concept_group
    words = unit.statement.split()

    candidate_indices = [
        i for i, w in enumerate(words)
        if len(w) > 2
        and w not in _STOPWORDS
        and re.sub(r"[^\w\u0621-\u064A]", "", w)
        and i > 0
    ]

    if candidate_indices and len(words) >= 4:
        concept_tokens = _extract_content_tokens(group.label)
        label_matches = [i for i in candidate_indices if _normalize_concept_key(words[i]) in concept_tokens]

        target_idx = label_matches[0] if label_matches else candidate_indices[len(candidate_indices) // 2]
        target_word = words[target_idx].strip("،.؛:()")
        masked_words = list(words)
        masked_words[target_idx] = "________"
        q_text = f"أكمل: {' '.join(masked_words)}"
        correct_term = target_word
    else:
        q_text = f"ما المصطلح الذي يعبّر عن: «{unit.statement}»؟"
        correct_term = group.label

    return {
        "question_type": "fill_in_blank",
        "question_text": q_text,
        "correct_answer": correct_term,
        "options": None,
        "explanation": _build_explanation(unit, f"الكلمة المطلوبة وفقاً للدرس هي «{correct_term}»"),
        "source_concept": group.label,
        "source_start_time": unit.start_time,
        "source_end_time": unit.end_time,
        "source_segment_ids": unit.source_segment_ids,
        "source_knowledge_unit_ids": [unit.id],
        "learning_objective": plan.learning_objective,
        "difficulty": plan.difficulty,
    }


def _grounded_question_base(plan: QuestionPlan, question_type: str, question_text: str) -> dict[str, Any]:
    """Return shared, provenance-preserving fields for non-MCQ question types."""
    unit = plan.primary_unit
    return {
        "question_type": question_type,
        "question_text": question_text,
        "options": None,
        "source_concept": plan.concept_group.label,
        "source_start_time": unit.start_time,
        "source_end_time": unit.end_time,
        "source_segment_ids": unit.source_segment_ids,
        "source_knowledge_unit_ids": [unit.id],
        "image_asset_ids": list(getattr(unit, "image_asset_ids", None) or []),
        "learning_objective": plan.learning_objective,
        "difficulty": plan.difficulty,
    }


def generate_short_answer(plan: QuestionPlan) -> dict[str, Any]:
    """Generate a concise response question whose model answer is source text."""
    unit = plan.primary_unit
    question = _grounded_question_base(
        plan,
        "short_answer",
        f"اكتب إجابة قصيرة توضّح «{plan.concept_group.label}» وفقاً لما ورد في الدرس.",
    )
    question.update({
        "correct_answer": unit.statement,
        "explanation": _build_explanation(unit, "الإجابة النموذجية مقتبسة من المعلومة المفهرسة"),
        "rubric": {"expected_points": [unit.statement], "max_words": 60},
    })
    return question


def generate_numerical(plan: QuestionPlan) -> dict[str, Any]:
    """Ask for a value/equation already present in the source; never invent operands."""
    unit = plan.primary_unit
    question = _grounded_question_base(
        plan,
        "numerical",
        f"استخرج القيمة أو العلاقة الرياضية المرتبطة بـ «{plan.concept_group.label}» كما وردت في المصدر.",
    )
    question.update({
        "correct_answer": unit.statement,
        "explanation": _build_explanation(unit, "لا يتطلب السؤال افتراض أرقام أو معطيات غير موجودة في المصدر"),
        "rubric": {"requires_source_value": True, "accept_equivalent_notation": True},
    })
    return question


def generate_image_question(plan: QuestionPlan) -> dict[str, Any] | None:
    """Generate an image-linked question only when the source unit has stored media."""
    unit = plan.primary_unit
    media_ids = list(getattr(unit, "image_asset_ids", None) or [])
    if not media_ids:
        return None
    question = _grounded_question_base(
        plan,
        "image_question",
        f"بالاستناد إلى الصورة/الرسم المرفق، ماذا يوضّح «{plan.concept_group.label}» وفقاً للمحتوى المحيط بها؟",
    )
    question.update({
        "correct_answer": unit.statement,
        "explanation": _build_explanation(unit, "الإجابة مربوطة بالصورة وبالنص المفهرس المحيط بها"),
        "image_asset_ids": media_ids,
    })
    return question


# =============================================================================
# 5. INDEPENDENT VALIDATION LAYER
# =============================================================================

@dataclass
class ValidationResult:
    """Result of independent question validation."""
    is_valid: bool
    rejection_reasons: list[str] = field(default_factory=list)


def _contains_banned_generic(text: str) -> bool:
    """Check if text contains banned generic distractor phrases."""
    for phrase in BANNED_GENERIC_DISTRACTORS:
        if phrase in text:
            return True
    return False


def _contains_banned_essay_pattern(text: str) -> bool:
    """Check if text contains banned essay meta-question patterns."""
    for pattern in BANNED_ESSAY_PATTERNS:
        if pattern in text:
            return True
    return False


def _contains_colloquial(text: str) -> bool:
    """Check if text contains banned colloquial/ASR artifacts."""
    for token in BANNED_COLLOQUIAL:
        if re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE):
            return True
    return False


def validate_single_question(question: dict[str, Any]) -> ValidationResult:
    """Independent validation of a single generated question."""
    reasons: list[str] = []
    q_text = question.get("question_text", "")
    correct = question.get("correct_answer", "")
    options = question.get("options")
    q_type = question.get("question_type", "")

    full_text = f"{q_text} {correct or ''}"
    if options:
        full_text += " " + " ".join(o.get("text", "") for o in options)

    if _contains_colloquial(full_text):
        reasons.append("contains_colloquial_artifact")

    if len(q_text.split()) < 4:
        reasons.append("question_stem_too_short")

    if q_type == "essay" and _contains_banned_essay_pattern(q_text):
        reasons.append("essay_is_meta_question")

    if q_type == "multiple_choice" and options:
        if len(options) != 4:
            reasons.append("mcq_must_have_4_options")

        option_texts = [o.get("text", "").strip() for o in options]
        if len(set(option_texts)) < len(option_texts):
            reasons.append("duplicate_options")

        for opt in option_texts:
            if _contains_banned_generic(opt):
                reasons.append(f"generic_distractor: {opt[:30]}")

        correct_count = sum(1 for o in options if o.get("is_correct"))
        if correct_count != 1:
            reasons.append("must_have_exactly_one_correct")

    if q_type == "true_false" and options:
        if len(options) != 2:
            reasons.append("true_false_must_have_2_options")

    if not question.get("source_start_time") and question.get("source_start_time") != 0:
        reasons.append("missing_source_timestamp")
    if not question.get("source_concept"):
        reasons.append("missing_source_concept")

    return ValidationResult(
        is_valid=len(reasons) == 0,
        rejection_reasons=reasons,
    )


def validate_quiz_diversity(questions: list[dict[str, Any]]) -> ValidationResult:
    """Validates quiz-level diversity: no duplicate concepts, answers, or near-duplicates."""
    reasons: list[str] = []

    if not questions:
        return ValidationResult(is_valid=True)

    concepts = [q.get("source_concept", "") for q in questions]
    concept_counts: dict[str, int] = {}
    for c in concepts:
        concept_counts[c] = concept_counts.get(c, 0) + 1

    for concept, count in concept_counts.items():
        if count > 2:
            reasons.append(f"concept_over_represented: {concept} ({count} times)")

    answers = [q.get("correct_answer", "") for q in questions if q.get("correct_answer")]
    answer_set: set[str] = set()
    for ans in answers:
        normalized = _normalize_concept_key(ans)
        if normalized in answer_set:
            reasons.append("duplicate_answer_detected")
            break
        answer_set.add(normalized)

    objectives = [q.get("learning_objective", "") for q in questions]
    if len(set(objectives)) == 1 and len(questions) > 3:
        reasons.append("all_questions_same_learning_objective")

    return ValidationResult(
        is_valid=len(reasons) == 0,
        rejection_reasons=reasons,
    )


# =============================================================================
# 6. MAIN QUIZ ENGINE ORCHESTRATOR (MODES A, B, C & IMAGE ATTACHMENT)
# =============================================================================

def generate_quiz(
    knowledge_units: list[KnowledgeUnit],
    type_allocations: list[dict[str, Any]],
    requested_count: int,
    mode: str = "mode_b_novel",  # mode_a_reuse, mode_b_novel, mode_c_hybrid
    existing_bank_questions: list[dict[str, Any]] | None = None,
    used_hashes: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Full quiz generation pipeline supporting Modes A (Reuse Bank), Mode B (Novel), Mode C (Hybrid),
    deduplication fingerprinting, and image asset attachments.
    """
    used_hashes = used_hashes or set()
    existing_bank = existing_bank_questions or []
    raw_questions: list[dict[str, Any]] = []

    # MODE A / MODE C: Select questions from existing teacher assessment bank
    if mode in ("mode_a_reuse", "mode_c_hybrid") and existing_bank:
        reuse_target = requested_count if mode == "mode_a_reuse" else max(1, requested_count // 2)
        for bank_q in existing_bank:
            q_text = bank_q.get("question_text", "")
            q_hash = hashlib.sha256(re.sub(r"\s+", "", q_text.lower()).encode("utf-8")).hexdigest()
            
            if q_hash in used_hashes:
                continue

            used_hashes.add(q_hash)
            raw_questions.append({
                "question_type": bank_q.get("question_type", "multiple_choice"),
                "question_text": q_text,
                "correct_answer": bank_q.get("correct_answer"),
                "options": bank_q.get("options_json") or bank_q.get("options"),
                "explanation": bank_q.get("explanation", "من بنك أسئلة المدرس السابق."),
                "source_concept": bank_q.get("topic_concept", "سؤال بنك سابق"),
                "source_start_time": bank_q.get("source_start_time", 0.0),
                "source_end_time": bank_q.get("source_end_time", 0.0),
                "learning_objective": bank_q.get("learning_objective", "understanding"),
                "difficulty": bank_q.get("difficulty", "medium"),
                "media": bank_q.get("media_ids_json") or bank_q.get("media"),
                "is_reused_from_bank": True,
            })
            if len(raw_questions) >= reuse_target:
                break

    # MODE B / MODE C: Generate novel questions from Knowledge Units
    novel_needed = requested_count - len(raw_questions)

    if novel_needed > 0 and knowledge_units:
        concept_groups = map_concepts(knowledge_units)
        plans, meta = plan_question_diversity(concept_groups, type_allocations, novel_needed)

        for plan in plans:
            question: dict[str, Any] | None = None

            if plan.question_type == "multiple_choice":
                question = generate_mcq(plan, concept_groups)
            elif plan.question_type == "true_false":
                with_corr = any(bool(a.get("withCorrection")) for a in type_allocations if a.get("id") == "true_false")
                question = generate_true_false(plan, concept_groups, with_corr)
            elif plan.question_type == "essay":
                question = generate_essay(plan, concept_groups)
            elif plan.question_type == "fill_in_blank":
                question = generate_fill_blank(plan)
            elif plan.question_type == "short_answer":
                question = generate_short_answer(plan)
            elif plan.question_type == "numerical":
                question = generate_numerical(plan)
            elif plan.question_type == "image_question":
                question = generate_image_question(plan)

            if question is None:
                continue

            # Deduplication fingerprint check
            q_hash = hashlib.sha256(re.sub(r"\s+", "", question["question_text"].lower()).encode("utf-8")).hexdigest()
            if q_hash in used_hashes:
                continue
            used_hashes.add(q_hash)

            # Independent validation
            val = validate_single_question(question)
            if val.is_valid:
                raw_questions.append(question)

    diversity_res = validate_quiz_diversity(raw_questions)

    times = [q.get("source_start_time", 0.0) for q in raw_questions]
    min_t, max_t = (min(times), max(times)) if times else (0.0, 0.0)
    span = max(1.0, max_t - min_t)
    third = span / 3.0
    timeline = {
        "beginning": sum(1 for t in times if t < min_t + third),
        "middle": sum(1 for t in times if min_t + third <= t < min_t + 2 * third),
        "end": sum(1 for t in times if t >= min_t + 2 * third),
    } if times else {"beginning": 0, "middle": 0, "end": 0}

    metadata = {
        "requested_count": requested_count,
        "generated_count": len(raw_questions),
        "insufficient_content": len(raw_questions) < requested_count,
        "distinct_concepts": len(set(q.get("source_concept", "") for q in raw_questions)),
        "mode": mode,
        "reused_count": sum(1 for q in raw_questions if q.get("is_reused_from_bank")),
        "novel_count": sum(1 for q in raw_questions if not q.get("is_reused_from_bank")),
        "timeline_coverage": timeline,
        "diversity_issues": diversity_res.rejection_reasons if not diversity_res.is_valid else [],
    }

    return raw_questions, metadata
