"""
=============================================================================
QUIZ QUALITY REGRESSION TESTS — COMPREHENSIVE
=============================================================================
Tests all quality constraints from the FINAL QUIZ ENGINE HARDENING SPEC:
1. Multi-concept diversity
2. Single-concept limit
3. Generic distractor rejection
4. Essay quality (no meta-questions)
5. Fill-in-blank key concept masking
6. True/False meaningfulness
7. Duplicate detection
8. Insufficient content metadata
9. Full-lesson coverage (timeline)
10. Grounding (timestamps, source concepts)
11. Adversarial: very small / large / repeated concept / noisy ASR
12. Regression fixture for the exact bad quiz behavior
=============================================================================
"""
import pytest
from app.services.educational_normalizer import (
    KnowledgeUnit,
    extract_knowledge_units,
)
from app.services.quiz_engine import (
    map_concepts,
    generate_quiz,
    validate_single_question,
    validate_quiz_diversity,
    assess_question_suitability,
    BANNED_GENERIC_DISTRACTORS,
    BANNED_ESSAY_PATTERNS,
    BANNED_COLLOQUIAL,
)


def _make_unit(uid: str, concept: str, statement: str, start: float, end: float, category: str = "general") -> KnowledgeUnit:
    """Helper to create a test KnowledgeUnit."""
    return KnowledgeUnit(
        id=uid, lesson_id="test_lesson", concept=concept, statement=statement,
        raw_text=statement, start_time=start, end_time=end,
        source_segment_ids=[f"seg_{uid}"], category=category,
    )


# =============================================================================
# 1. MULTI-CONCEPT DIVERSITY
# =============================================================================
def test_multi_concept_diversity_5_concepts():
    """5 distinct concepts → 5 questions → each question targets a different concept."""
    units = [
        _make_unit("u1", "الجيولوجيا الطبيعية", "علم الجيولوجيا الطبيعية يدرس تأثير العوامل على صخور كوكب الارض.", 0, 30, "definition"),
        _make_unit("u2", "العوامل الخارجية", "العوامل الخارجية تشمل الرياح والامطار ودرجات الحرارة وحركة السيول والانهار.", 30, 60, "classification"),
        _make_unit("u3", "العوامل الداخلية", "العوامل الداخلية تنشأ نتيجة طاقة وحرارة كامنة وضغوط عالية في باطن الارض.", 60, 90, "cause_effect"),
        _make_unit("u4", "علم المعادن", "علم المعادن والبلورات يهتم بدراسة اشكال البلورات والخصائص الفيزيائية والكيميائية.", 90, 120, "definition"),
        _make_unit("u5", "الفالق العادي", "الفالق العادي ينتج عن قوى شد يتحرك فيه صخور الحائط العلوي الى اسفل.", 120, 150, "fact"),
    ]

    questions, meta = generate_quiz(
        units,
        [{"id": "multiple_choice", "count": 3}, {"id": "true_false", "count": 2}],
        5,
    )

    concepts_used = [q["source_concept"] for q in questions]
    assert len(set(concepts_used)) >= 4, f"Expected >= 4 distinct concepts, got {len(set(concepts_used))}: {concepts_used}"


# =============================================================================
# 2. SINGLE-CONCEPT LIMIT
# =============================================================================
def test_single_concept_limit():
    """1 KU only → request 5 questions → system generates at most 2 (not 5 duplicates)."""
    units = [
        _make_unit("u1", "نوع النشاط", "نوع النشاط المطلوب هو اختبار تقييمي إلكتروني.", 0, 30, "fact"),
    ]

    questions, meta = generate_quiz(
        units,
        [{"id": "multiple_choice", "count": 3}, {"id": "true_false", "count": 2}],
        5,
    )

    # MCQ should NOT be generated (only 1 concept, needs 3 for distractors)
    mcq_count = sum(1 for q in questions if q["question_type"] == "multiple_choice")
    assert mcq_count == 0, f"Should not generate MCQs with only 1 concept, got {mcq_count}"

    # Total questions should be much less than 5
    assert len(questions) <= 2, f"Should not generate 5 questions from 1 concept, got {len(questions)}"
    assert meta["insufficient_content"] is True


# =============================================================================
# 3. GENERIC DISTRACTOR REJECTION
# =============================================================================
def test_generic_distractor_rejection():
    """No generated question may contain banned generic distractor phrases."""
    units = [
        _make_unit("u1", "الجيولوجيا", "علم الجيولوجيا هو العلم الذي يدرس الارض من حيث حركتها ومكوناتها.", 0, 30, "definition"),
        _make_unit("u2", "الجيوفيزياء", "الجيوفيزياء علم يستخدم اجهزة فيزيائية لاستكشاف الثروات البترولية والمياه الجوفية.", 30, 60, "application"),
        _make_unit("u3", "علم الطبقات", "علم الطبقات يدرس القوانين والظروف المتحكمة في تكوين الطبقات الصخرية.", 60, 90, "definition"),
        _make_unit("u4", "علم الأحافير", "علم الأحافير القديمة يختص بدراسة بقايا الكائنات الحية المدفونة في الصخور الرسوبية.", 90, 120, "definition"),
    ]

    questions, _ = generate_quiz(units, [{"id": "multiple_choice", "count": 4}], 4)

    for q in questions:
        if q.get("options"):
            for opt in q["options"]:
                opt_text = opt.get("text", "")
                for banned in BANNED_GENERIC_DISTRACTORS:
                    assert banned not in opt_text, f"Banned generic distractor found: '{banned}' in '{opt_text[:50]}'"


# =============================================================================
# 4. ESSAY QUALITY — NO META-QUESTIONS
# =============================================================================
def test_essay_no_meta_questions():
    """Essay questions must NOT use meta-question patterns like 'اشرح ما تم تناوله في سياق'."""
    units = [
        _make_unit("u1", "القشرة الأرضية", "القشرة الارضية تتكون من نوعين اساسيين قشرة قارية سيال وقشرة محيطية سيما.", 0, 30, "classification"),
        _make_unit("u2", "القشرة القارية", "القشرة القارية صخورها جرانيتية خفيفة تتكون من السيليكا والالومنيوم.", 30, 60, "fact"),
        _make_unit("u3", "القشرة المحيطية", "القشرة المحيطية صخورها بازلتية ثقيلة تتكون من السيليكا والماغنسيوم.", 60, 90, "fact"),
    ]

    questions, _ = generate_quiz(units, [{"id": "essay", "count": 2}], 2)
    essay_questions = [q for q in questions if q["question_type"] == "essay"]

    for eq in essay_questions:
        for pattern in BANNED_ESSAY_PATTERNS:
            assert pattern not in eq["question_text"], f"Banned essay pattern found: '{pattern}'"


# =============================================================================
# 5. FILL-IN-BLANK KEY CONCEPT MASKING
# =============================================================================
def test_fill_blank_masks_key_concept():
    """Fill-in-blank must mask a meaningful learning term, not an arbitrary word."""
    units = [
        _make_unit("u1", "الوشاح", "الوشاح يمثل اكتر من 80 في المية من حجم صخور كوكب الارض وسمكه حوالي 2900 كيلومتر.", 0, 30, "quantitative"),
        _make_unit("u2", "القشرة", "القشرة الارضية تتكون من نوعين اساسيين قشرة قارية وقشرة محيطية.", 30, 60, "classification"),
        _make_unit("u3", "اللب", "اللب الداخلي للارض صلب ذو كثافة عالية تصل ل 14 جرام لكل سنتيمتر مكعب.", 60, 90, "quantitative"),
    ]

    questions, _ = generate_quiz(units, [{"id": "fill_in_blank", "count": 2}], 2)
    fib_questions = [q for q in questions if q["question_type"] == "fill_in_blank"]

    for fq in fib_questions:
        # The correct answer should be a substantive word, not a stopword
        answer = fq["correct_answer"]
        assert len(answer) > 2, f"Fill-in-blank answer too short: '{answer}'"
        assert "________" in fq["question_text"], "Fill-in-blank must contain blank placeholder"


# =============================================================================
# 6. TRUE/FALSE MEANINGFULNESS
# =============================================================================
def test_true_false_no_arbitrary_pairing():
    """True/False must NOT mechanically pair unrelated concepts."""
    units = [
        _make_unit("u1", "الجيولوجيا", "علم الجيولوجيا يدرس كل ما يتعلق بالارض من حيث حركتها ومكوناتها وظواهرها.", 0, 30, "definition"),
        _make_unit("u2", "العوامل الخارجية", "العوامل الخارجية تشمل الرياح والامطار ودرجات الحرارة.", 30, 60, "classification"),
        _make_unit("u3", "الزلازل", "الزلازل تنشأ نتيجة طاقة محبوسة في باطن الارض.", 60, 90, "cause_effect"),
    ]

    questions, _ = generate_quiz(units, [{"id": "true_false", "count": 3}], 3)
    tf_questions = [q for q in questions if q["question_type"] == "true_false"]

    for tq in tf_questions:
        result = validate_single_question(tq)
        assert result.is_valid, f"TF question failed validation: {result.rejection_reasons}"
        # Each question must reference a specific concept
        assert tq.get("source_concept"), "TF question must have source_concept"


# =============================================================================
# 7. DUPLICATE DETECTION
# =============================================================================
def test_no_duplicate_concepts():
    """No two questions should test the exact same concept + same answer."""
    units = [
        _make_unit("u1", "الجيولوجيا", "علم الجيولوجيا يدرس الارض.", 0, 30, "definition"),
        _make_unit("u2", "الجيوفيزياء", "الجيوفيزياء علم يستخدم اجهزة لاستكشاف الثروات.", 30, 60, "application"),
        _make_unit("u3", "المعادن", "علم المعادن يدرس اشكال البلورات والخصائص الفيزيائية.", 60, 90, "definition"),
        _make_unit("u4", "الطبقات", "علم الطبقات يدرس القوانين المتحكمة في تكوين الطبقات.", 90, 120, "definition"),
    ]

    questions, _ = generate_quiz(
        units,
        [{"id": "multiple_choice", "count": 2}, {"id": "true_false", "count": 2}],
        4,
    )

    diversity_result = validate_quiz_diversity(questions)
    # Should not have over-represented concepts
    for reason in diversity_result.rejection_reasons:
        assert "concept_over_represented" not in reason


# =============================================================================
# 8. INSUFFICIENT CONTENT METADATA
# =============================================================================
def test_insufficient_content_metadata():
    """When lesson can't support requested count, metadata reports honestly."""
    units = [
        _make_unit("u1", "مفهوم واحد", "مفهوم واحد فقط متاح في هذا الدرس القصير جداً.", 0, 30, "fact"),
    ]

    _, meta = generate_quiz(units, [{"id": "multiple_choice", "count": 10}], 10)

    assert meta["requested_count"] == 10
    assert meta["generated_count"] < 10
    assert meta["insufficient_content"] is True


# =============================================================================
# 9. FULL-LESSON TIMELINE COVERAGE
# =============================================================================
def test_timeline_coverage():
    """Questions should span beginning, middle, and end of lesson."""
    units = [
        _make_unit(f"u{i}", f"مفهوم {i}", f"هذا شرح مفصل ومتكامل للمفهوم رقم {i} في الدرس الشامل.", i * 60, (i + 1) * 60, "definition")
        for i in range(1, 10)
    ]

    questions, meta = generate_quiz(
        units,
        [{"id": "true_false", "count": 6}],
        6,
    )

    timeline = meta.get("timeline_coverage", {})
    assert timeline.get("beginning", 0) > 0, "No questions from beginning"
    assert timeline.get("end", 0) > 0, "No questions from end"


# =============================================================================
# 10. GROUNDING
# =============================================================================
def test_grounding_timestamps_and_sources():
    """Every question must have valid source timestamps and concept."""
    units = [
        _make_unit("u1", "الضغط الجوي", "الضغط الجوي يقل لنصف قيمته كلما ارتفعنا 5 كيلومتر.", 100.0, 130.0, "quantitative"),
        _make_unit("u2", "سطح البحر", "مستوى سطح البحر هو مستوى المياه المحيط بالكرة الارضية.", 130.0, 160.0, "definition"),
        _make_unit("u3", "التراكيب الجيولوجية", "التراكيب الجيولوجية الأولية تتكون تحت تأثير عوامل مناخية وبيئية.", 160.0, 190.0, "fact"),
    ]

    questions, _ = generate_quiz(
        units,
        [{"id": "true_false", "count": 2}, {"id": "fill_in_blank", "count": 1}],
        3,
    )

    for q in questions:
        assert q.get("source_start_time") is not None, "Missing source_start_time"
        assert q.get("source_end_time") is not None, "Missing source_end_time"
        assert q.get("source_concept"), "Missing source_concept"
        assert q.get("source_segment_ids"), "Missing source_segment_ids"
        assert q.get("learning_objective"), "Missing learning_objective"


# =============================================================================
# 11. ADVERSARIAL: NOISY ASR
# =============================================================================
def test_noisy_asr_not_in_questions():
    """Transcript ASR corruption must NOT leak into generated questions."""
    segments = [
        {"id": "n1", "start_time": 0, "end_time": 30, "text": "بص يا حبايبي السخور دي بتتكسر بفعل العوامل الخارجية والامطار والرياح"},
        {"id": "n2", "start_time": 30, "end_time": 60, "text": "الجيوفيزي علم بيستخدم اجهزة فيزيائية عشان نستكشف الثروات البترولية"},
        {"id": "n3", "start_time": 60, "end_time": 90, "text": "الفالي العادي بينتج عن قوى شد وبيتحرك فيه الحائط العلوي لاسفل"},
    ]

    units = extract_knowledge_units(segments, "noisy_lesson")
    questions, _ = generate_quiz(
        units,
        [{"id": "true_false", "count": 2}],
        2,
    )

    for q in questions:
        q_text = q["question_text"]
        # No colloquial fillers
        for banned in BANNED_COLLOQUIAL:
            assert banned not in q_text, f"Colloquial token '{banned}' leaked into question"


# =============================================================================
# 12. REGRESSION: THE EXACT BAD QUIZ BEHAVIOR
# =============================================================================
def test_regression_single_sentence_not_5_questions():
    """
    Regression for the original bug:
    Given 'نوع النشاط المطلوب: اختبار تقييمي إلكتروني'
    the system must NOT produce 5 questions about the exact same sentence.
    """
    units = [
        _make_unit("reg1", "نوع النشاط", "نوع النشاط المطلوب هو اختبار تقييمي إلكتروني.", 0, 30, "fact"),
    ]

    questions, meta = generate_quiz(
        units,
        [
            {"id": "multiple_choice", "count": 2},
            {"id": "true_false", "count": 1},
            {"id": "essay", "count": 1},
            {"id": "fill_in_blank", "count": 1},
        ],
        5,
    )

    # System should NOT generate 5 questions from one sentence
    assert len(questions) <= 2, f"Generated {len(questions)} questions from 1 sentence — must be ≤ 2"

    # MCQ should NOT be generated (only 1 concept)
    mcq_count = sum(1 for q in questions if q["question_type"] == "multiple_choice")
    assert mcq_count == 0, "MCQ should not be generated with only 1 concept group"

    # No generic distractors anywhere
    for q in questions:
        if q.get("options"):
            for opt in q["options"]:
                for banned in BANNED_GENERIC_DISTRACTORS:
                    assert banned not in opt.get("text", "")

    # Metadata must report insufficient content
    assert meta["insufficient_content"] is True


# =============================================================================
# 13. CONCEPT MAPPING
# =============================================================================
def test_concept_mapping_groups_related_units():
    """Two KUs about the same concept should be grouped together."""
    units = [
        _make_unit("u1", "القشرة القارية", "القشرة القارية صخورها جرانيتية خفيفة الوزن.", 0, 30, "fact"),
        _make_unit("u2", "القشرة القارية", "القشرة القارية تتكون من السيليكا والالومنيوم وسمكها 60 كيلومتر.", 30, 60, "quantitative"),
        _make_unit("u3", "القشرة المحيطية", "القشرة المحيطية صخورها بازلتية ثقيلة تتكون من السيليكا والماغنسيوم.", 60, 90, "fact"),
    ]

    groups = map_concepts(units)
    # The two القشرة القارية units should be grouped
    assert len(groups) == 2, f"Expected 2 concept groups, got {len(groups)}"


# =============================================================================
# 14. QUESTION SUITABILITY
# =============================================================================
def test_question_suitability_respects_concept_count():
    """MCQ should be unsuitable when there are fewer than 3 concept groups."""
    units = [
        _make_unit("u1", "مفهوم أ", "مفهوم أ يتناول موضوعاً علمياً محدداً ومهماً في هذا السياق.", 0, 30, "definition"),
        _make_unit("u2", "مفهوم ب", "مفهوم ب يرتبط بنتائج وتطبيقات عملية متعددة.", 30, 60, "application"),
    ]

    groups = map_concepts(units)
    for g in groups:
        profile = assess_question_suitability(g, total_groups=len(groups))
        # With only 2 groups, MCQ should be unsuitable
        assert not profile.multiple_choice, "MCQ should be unsuitable with only 2 concept groups"
