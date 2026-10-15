"""Content normalization must not guess or translate the teacher's source."""
import pytest

from app.services.document_parsers import (
    clean_arabic_ocr_text,
    clean_chemical_formula_text,
    normalize_arabic_presentation_forms,
)


@pytest.mark.parametrize("word", ["of", "in", "to", "and", "ale", "Jol", "wi", "Bale"])
def test_bilingual_source_words_are_not_translated(word):
    source = f"اختر معنى {word} في النص"
    assert clean_arabic_ocr_text(source) == source


@pytest.mark.parametrize("source", ["الأومنيوم", "أنحديد"])
def test_source_spelling_is_not_replaced_by_a_dictionary(source):
    assert clean_arabic_ocr_text(source) == source
    assert normalize_arabic_presentation_forms(source) == source


@pytest.mark.parametrize(
    ("source", "expected"),
    [(r"\Delta S", "Δ S"), (r"\Delta T", "Δ T"), (r"\Delta", "Δ")],
)
def test_delta_does_not_invent_an_enthalpy_symbol(source, expected):
    assert clean_chemical_formula_text(source) == expected


def test_arabic_ligatures_are_normalized_without_changing_scientific_symbols():
    assert clean_arabic_ocr_text("ﻻ N₂ + 3H₂ ⇌ 2NH₃") == "لا N₂ + 3H₂ ⇌ 2NH₃"


def test_question_assembly_preserves_prose_and_renders_explicit_math_only():
    from app.services.exam_text_extractor import _preserve_source_text
    assert _preserve_source_text('a parallel line in PH quad mid') == 'a parallel line in PH quad mid'
    assert _preserve_source_text(r'$Fe_3O_4$ and $\\parallel$'.replace('\\\\', '\\')) == 'Fe₃O₄ and ||'
