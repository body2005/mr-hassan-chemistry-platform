"""
=============================================================================
REAL ASR TRANSCRIPT 50-SEGMENT QUALITY & PEDAGOGICAL GATE BENCHMARK
=============================================================================
Tests against genuine QwenCleo-ASR transcribed segments from the Egyptian
secondary lecture across Beginning, Middle, and End.
=============================================================================
"""
import pytest
from tests.real_50_asr_dataset import REAL_50_ASR_SEGMENTS
from app.services.educational_normalizer import (
    clean_spoken_noise,
    extract_knowledge_units,
    validate_question_quality,
)
from app.services.semantic_rewriter import verify_semantic_faithfulness
from app.services.quiz_engine import (
    generate_quiz,
    map_concepts,
    validate_single_question,
    validate_quiz_diversity,
    BANNED_GENERIC_DISTRACTORS,
)


def test_50_real_asr_segments_quality_and_containment():
    """Evaluates all 50 real ASR segments for faithfulness, no-expansion, and no-loss."""
    segments_input = [
        {"id": s["id"], "start_time": s["start_time"], "end_time": s["end_time"], "text": s["raw"]}
        for s in REAL_50_ASR_SEGMENTS
    ]

    units = extract_knowledge_units(segments_input, lesson_id="real_geology_lecture_50")
    assert len(units) == 50, f"Expected 50 units, got {len(units)}"

    faithful_count = 0
    no_expansion_count = 0
    no_loss_count = 0
    clarity_count = 0

    for i, unit in enumerate(units):
        raw_item = REAL_50_ASR_SEGMENTS[i]
        raw_text = raw_item["raw"]

        # Timestamp traceability
        assert unit.start_time == raw_item["start_time"]
        assert unit.end_time == raw_item["end_time"]
        assert unit.source_segment_ids == [raw_item["id"]]

        # Independent Verifier Evaluation
        verif = verify_semantic_faithfulness(raw_text, unit.statement)

        if verif.is_faithful:
            faithful_count += 1
        if not verif.has_expansion:
            no_expansion_count += 1
        if not verif.has_loss:
            no_loss_count += 1
        if verif.clarity_score >= 0.8:
            clarity_count += 1

        assert unit.semantic_confidence >= 0.7, f"Segment {i} had low confidence: {unit.semantic_confidence}"

    assert faithful_count == 50
    assert no_expansion_count == 50
    assert no_loss_count == 50
    assert clarity_count == 50


def test_20_real_educational_quiz_questions():
    """Generates and evaluates 20 dynamic educational quiz questions from real Knowledge Units."""
    segments_input = [
        {"id": s["id"], "start_time": s["start_time"], "end_time": s["end_time"], "text": s["raw"]}
        for s in REAL_50_ASR_SEGMENTS
    ]
    units = extract_knowledge_units(segments_input, lesson_id="real_geology_lecture_50")

    # Generate diverse quiz using the new quiz engine
    questions, meta = generate_quiz(
        units,
        [
            {"id": "multiple_choice", "count": 10},
            {"id": "true_false", "count": 5, "withCorrection": True},
            {"id": "essay", "count": 3},
            {"id": "fill_in_blank", "count": 2},
        ],
        20,
    )

    # Must generate a meaningful number of questions from 50 concepts
    assert len(questions) >= 15, f"Expected at least 15 questions, got {len(questions)}"

    # Every question must pass independent validation
    for q in questions:
        result = validate_single_question(q)
        assert result.is_valid, f"Question failed validation: {result.rejection_reasons}"

    # No generic distractors allowed
    for q in questions:
        if q.get("options"):
            for opt in q["options"]:
                for banned in BANNED_GENERIC_DISTRACTORS:
                    assert banned not in opt.get("text", ""), f"Generic distractor found: {banned}"

    # Check concept diversity
    concepts = set(q.get("source_concept", "") for q in questions)
    assert len(concepts) >= 10, f"Expected at least 10 distinct concepts, got {len(concepts)}"

    # Check grounding (timestamps)
    for q in questions:
        assert q.get("source_start_time") is not None
        assert q.get("source_end_time") is not None
        assert q.get("source_concept")
