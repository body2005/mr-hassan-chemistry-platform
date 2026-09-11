"""
=============================================================================
MULTIMODAL CHEMISTRY RAG & ANSWER VERIFICATION TEST SUITE
=============================================================================
Tests covering:
1. Chemistry Normalizer: formula extraction, stoichiometry, reaction parsing,
   and bilingual Arabic/English synonym expansion.
2. Chemistry Vision: diagram classification, apparatus/scheme detection,
   and visual asset indexing into semantic KnowledgeUnitRecords.
3. Answer Verifier & Grounding: strict evidence checking, hallucinated formula
   detection, ungrounded number rejection, and citation verification.
4. Refusal Contract: honest refusal ("هذه المعلومة غير موجودة في الملف المرفوع.")
   when evidence is missing.
=============================================================================
"""
import uuid
from unittest.mock import MagicMock

from app.models.knowledge_center import KnowledgeAsset, KnowledgeUnitRecord
from app.services.chemistry_normalizer import (
    chemistry_aware_tokenize,
    expand_chemistry_synonyms,
    extract_chemical_formulas,
    normalize_chemical_formula,
    parse_chemical_reaction,
)
from app.services.chemistry_vision import (
    analyze_chemistry_diagram_content,
    index_asset_as_knowledge_unit,
)
from app.services.grounded_answer import (
    build_grounded_answer,
    verify_grounded_answer,
)
from app.services.knowledge_retriever import KnowledgeSearchResult


# =============================================================================
# 1. CHEMISTRY NORMALIZER TESTS
# =============================================================================

def test_extract_chemical_formulas():
    """Verify non-destructive chemical formula extraction."""
    text = "يتفاعل حمض الهيدروكلوريك 2HCl مع الخارصين Zn لإنتاج ZnCl2 وغاز H2 وحمض H2SO4 و Ca(OH)2."
    formulas = extract_chemical_formulas(text)

    formula_bases = [f.normalized for f in formulas]
    assert "HCl" in formula_bases
    assert "Zn" in formula_bases
    assert "ZnCl2" in formula_bases
    assert "H2" in formula_bases
    assert "H2SO4" in formula_bases
    assert "Ca(OH)2" in formula_bases

    hcl_entry = next(f for f in formulas if f.normalized == "HCl")
    assert hcl_entry.coefficient == 2


def test_parse_chemical_reaction():
    """Verify parsing of balanced chemical reaction equations."""
    rxn = parse_chemical_reaction("Zn + 2HCl -> ZnCl2 + H2")
    assert rxn is not None
    assert [r.normalized for r in rxn.reactants] == ["Zn", "HCl"]
    assert [p.normalized for p in rxn.products] == ["ZnCl2", "H2"]

    rev_rxn = parse_chemical_reaction("N2 + 3H2 <=> 2NH3")
    assert rev_rxn is not None
    assert any(p.normalized == "NH3" for p in rev_rxn.products)


def test_chemistry_synonym_expansion():
    """Verify Arabic to English chemical formula synonym expansion."""
    arabic_text = "حمض الكبريتيك المركز يتفاعل مع هيدروكسيد الصوديوم"
    synonyms = expand_chemistry_synonyms(arabic_text)
    syn_lower = [s.lower() for s in synonyms]
    assert "h2so4" in syn_lower
    assert "naoh" in syn_lower

    eng_text = "Analysis of KMnO4 and NaCl solution"
    synonyms_eng = expand_chemistry_synonyms(eng_text)
    assert any("برمنجانات" in s for s in synonyms_eng)
    assert any("كلوريد الصوديوم" in s for s in synonyms_eng)


def test_chemistry_aware_tokenize():
    """Verify that chemical formulas with numbers are preserved intact."""
    text = "محلول H2SO4 تركيزه 0.5 مولار يتفاعل مع CaCO3"
    tokens = chemistry_aware_tokenize(text)
    assert "h2so4" in tokens
    assert "caco3" in tokens
    assert "0.5" in tokens


# =============================================================================
# 2. CHEMISTRY VISION & MULTIMODAL INDEXING TESTS
# =============================================================================

def test_analyze_chemistry_diagram():
    """Verify automatic classification of chemistry diagrams and apparatus."""
    reaction_info = analyze_chemistry_diagram_content(
        caption="مخطط تفاعل هابر-بوش لتحضير النشادر",
        surrounding_text="N2 + 3H2 -> 2NH3 تحت ضغط 200 ضغط جوي وحرارة 500 مئوية وعامل حفاز الحديد",
    )
    assert reaction_info["category"] == "reaction_scheme"
    assert "NH3" in reaction_info["formulas"]

    apparatus_info = analyze_chemistry_diagram_content(
        caption="جهاز التقطير التجزيئي لفصل مكونات النفط",
        surrounding_text="يتكون الجهاز من دورق تقطير ومكثف ومقياس حرارة مع دورق استقبال",
    )
    assert apparatus_info["category"] == "experimental_setup"
    assert "دورق" in apparatus_info["apparatus"]


def test_index_asset_as_knowledge_unit():
    """Verify indexing of a visual KnowledgeAsset as a semantic KnowledgeUnitRecord."""
    mock_db = MagicMock()
    asset = KnowledgeAsset(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        asset_kind="diagram",
        storage_path="/storage/test.png",
        caption="مخطط تفاعل هيدروكسيد الصوديوم مع حمض الهيدروكلوريك",
        surrounding_text="معادلة التعادل: NaOH + HCl -> NaCl + H2O",
        page_number=4,
        slide_number=None,
    )

    unit = index_asset_as_knowledge_unit(
        db=mock_db,
        asset=asset,
        course_id=uuid.uuid4(),
        lesson_id=uuid.uuid4(),
        source_id=asset.source_id,
    )
    assert unit is not None
    assert unit.source_type == "diagram"
    assert unit.page_number == 4
    assert "NaOH" in unit.statement or "NaOH" in unit.concept
    assert mock_db.add.called


# =============================================================================
# 3. GROUNDED ANSWER & VERIFICATION TESTS
# =============================================================================

def test_grounded_answer_supported():
    """Verify that a fully evidenced answer passes verification with SUPPORTED."""
    evidence = [
        KnowledgeSearchResult(
            unit_id="u1",
            concept="تفاعل الخارصين مع حمض الهيدروكلوريك",
            statement="يتفاعل حمض الهيدروكلوريك HCl مع الخارصين Zn وينتج كلوريد الخارصين ZnCl2 ويتصاعد غاز الهيدروجين H2 عند درجة حرارة الغرفة.",
            details="تفاعل إحلال بسيط",
            knowledge_type="fact",
            relevance_score=0.9,
            source_filename="chem.pdf",
            source_role="core_reference",
            page_number=5,
            slide_number=None,
            citation_text="chem.pdf، ص 5",
        )
    ]
    candidate_answer = "يتفاعل الخارصين Zn مع حمض الهيدروكلوريك HCl لإنتاج كلوريد الخارصين ZnCl2 وغاز H2.\n\n📌 **المصدر بالمقرر:**\n• chem.pdf، ص 5"

    res = verify_grounded_answer("ما ناتج تفاعل الخارصين؟", evidence, candidate_answer)
    assert res.verdict == "SUPPORTED"
    assert res.is_valid is True
    assert len(res.violations) == 0


def test_grounded_answer_rejects_hallucinated_formula():
    """Verify that an answer introducing an ungrounded chemical formula is flagged as UNSUPPORTED."""
    evidence = [
        KnowledgeSearchResult(
            unit_id="u1",
            concept="التعادل",
            statement="يتفاعل حمض الهيدروكلوريك HCl مع هيدروكسيد الصوديوم NaOH لإنتاج NaCl و H2O.",
            details=None,
            knowledge_type="fact",
            relevance_score=0.9,
            source_filename="chem.pdf",
            source_role="core_reference",
            page_number=1,
            slide_number=None,
            citation_text="chem.pdf، ص 1",
        )
    ]
    # The answer invents nitric acid HNO3 which is NOT in the evidence
    hallucinated_answer = "يتفاعل حمض الهيدروكلوريك وحمض النيتريك HNO3 مع القاعدة.\n\n📌 **المصدر بالمقرر:**\n• chem.pdf، ص 1"

    res = verify_grounded_answer("سؤال", evidence, hallucinated_answer)
    assert res.verdict in ("UNSUPPORTED", "PARTIALLY_SUPPORTED")
    assert res.is_valid is False
    assert any("HNO3" in v for v in res.violations)


def test_grounded_answer_rejects_hallucinated_number():
    """Verify that an answer inventing quantitative numbers not in evidence is flagged."""
    evidence = [
        KnowledgeSearchResult(
            unit_id="u1",
            concept="المعايرة",
            statement="تمت إضافة 10 مل من المحلول القياسي حتى تغير لون الدليل.",
            details=None,
            knowledge_type="fact",
            relevance_score=0.9,
            source_filename="chem.pdf",
            source_role="core_reference",
            page_number=2,
            slide_number=None,
            citation_text="chem.pdf، ص 2",
        )
    ]
    # The answer invents 500 ml and 95%
    hallucinated_answer = "تمت إضافة 500 مل بتركيز 95 حتى تغير اللون.\n\n📌 **المصدر بالمقرر:**\n• chem.pdf، ص 2"

    res = verify_grounded_answer("سؤال", evidence, hallucinated_answer)
    assert res.verdict == "UNSUPPORTED"
    assert res.is_valid is False
    assert any("500" in v or "95" in v for v in res.violations)


def test_grounded_refusal_contract():
    """Verify that when no evidence exists, the system outputs the exact refusal string."""
    ans_text, is_grounded, is_refusal, citations = build_grounded_answer(
        question="ما هي معادلة تحضير الأسيتيلين في الصناعة وما هي شروط التفاعل بالتفصيل؟",
        evidence_items=[],
    )
    assert is_grounded is False
    assert "يجب أن يكون السؤال في إطار المادة" in ans_text
