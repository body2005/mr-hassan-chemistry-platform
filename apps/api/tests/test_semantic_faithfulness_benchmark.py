"""
=============================================================================
SEMANTIC FAITHFULNESS & ANTI-HALLUCINATION 20-SEGMENT BENCHMARK SUITE
=============================================================================
Evaluates:
1. Faithfulness (100% supported by source)
2. No-Expansion (0% external fact injection)
3. No-Loss (100% core technical concepts preserved)
4. Anti-Hallucination Gate rejection of unsupported extensions
5. Multi-disciplinary coverage (Geology, Physics, Chemistry, Biology, CS, History, Math)
=============================================================================
"""
import pytest
from app.services.educational_normalizer import (
    clean_spoken_noise,
    extract_knowledge_units,
    generate_educational_mcq,
    generate_educational_true_false,
    generate_educational_essay,
    generate_educational_fill_in_blank,
)
from app.services.semantic_rewriter import validate_semantic_containment

# 20 Diverse Real Multi-Disciplinary Segments
BENCHMARK_20_SEGMENTS = [
    # 1. Geology - Geophysics
    ("الجيوفيزي علم اللي بيستخدم أجهزة وأدوات فيزيائية عشان نعرف اللي تحت الأرض من غير ما نحفر", 10.0, 25.0, "Geology"),
    # 2. Geology - Building Stones
    ("بص يا سيدي بناء زي مين زي حاجة اسمها الحجر الجيري بيستخدم في البناء", 30.0, 45.0, "Geology"),
    # 3. Geology - Structural Joints
    ("عدد الفواصل يتلسب عكسي مع السمك والمسافه بين كل فاصل والتاني", 50.0, 65.0, "Geology"),
    # 4. Geology - Crustal Movement
    ("البحر رجع يعني الأرض رفعت نتيجة حركة رافعة", 70.0, 85.0, "Geology"),
    
    # 5. Physics - Ohm's Law
    ("قانون أوم بيقول إن شدة التيار بتتناسب طردي مع فرق الجهد عند ثبوت درجة الحرارة", 90.0, 110.0, "Physics"),
    # 6. Physics - Newton's Second Law
    ("القوة المحصلة المؤثرة على جسم بتكسبه تسارع بيتناسب طردياً مع القوة وعكسياً مع الكتلة", 115.0, 135.0, "Physics"),
    # 7. Physics - Electromagnetic Waves
    ("الموجات الكهرومغناطيسية بتنتشر في الفراغ بسرعة ثابتة هي سرعة الضوء", 140.0, 155.0, "Physics"),
    
    # 8. Chemistry - Periodic Table
    ("الجدول الدوري بيرتب العناصر تصاعدياً حسب أعدادها الذرية وتدرج خواصها الكيميائية", 160.0, 180.0, "Chemistry"),
    # 9. Chemistry - Neutralization
    ("تفاعل التعادل هو تفاعل حمض مع قلوي عشان ينتج ملح ومياه", 185.0, 200.0, "Chemistry"),
    # 10. Chemistry - Covalent Bond
    ("الرابطة التساهمية بتنشأ من مشاركة كل ذرة بإلكترون أو أكثر لتكوين زوج إلكتروني", 205.0, 220.0, "Chemistry"),
    
    # 11. Biology - Genetics
    ("تحتوي نواة الخلية البشرية على 46 كروموسوم بيحمل المادة الوراثية DNA", 225.0, 245.0, "Biology"),
    # 12. Biology - Photosynthesis
    ("عملية البناء الضوئي في النباتات بتحول الطاقة الضوئية لطاقة كيميائية مخزنة في الجلوكوز", 250.0, 270.0, "Biology"),
    # 13. Biology - Enzymes
    ("الإنزيمات هي عوامل حفازة حيوية بتسرع معدل التفاعلات الكيميائية داخل الكائن الحي", 275.0, 290.0, "Biology"),
    
    # 14. Computer Science - Python len()
    ("بنستخدم دالة len في لغة بايثون عشان نحدد عدد العناصر داخل القوائم والنصوص", 295.0, 310.0, "Computer Science"),
    # 15. Computer Science - For Loops
    ("الحلقات التكرارية for loop بتسمح لنا بالمرور على كل عناصر المصفوفة خطوة بخطوة", 315.0, 330.0, "Computer Science"),
    # 16. Computer Science - Functions
    ("الدوال البرمجية بتساعد في إعادة استخدام الكود وتقليل التكرار في المشروع", 335.0, 350.0, "Computer Science"),
    
    # 17. History - Industrial Revolution
    ("قامت الثورة الصناعية في بريطانيا في القرن الثامن عشر نتيجة استخدام المحركات البخارية", 355.0, 375.0, "History"),
    # 18. History - Treaty of Versailles
    ("أدت معاهدة فرساي لفرض قيود وشروط سياسية واقتصادية صارمة على ألمانيا بعد الحرب العالمية الأولى", 380.0, 400.0, "History"),
    
    # 19. Mathematics - Calculus
    ("مشتقة الدالة الثابتة بتساوي صفر دائماً في حساب التفاضل والتكامل", 405.0, 420.0, "Mathematics"),
    # 20. Mathematics - Linear Algebra
    ("المصفوفة المربعة هي مصفوفة بيتساوى فيها عدد الصفوف مع عدد الأعمدة", 425.0, 440.0, "Mathematics"),
]


def test_20_segments_faithfulness_and_no_loss():
    """Validates semantic faithfulness, no-expansion, and no-loss across all 20 segments."""
    segments_input = [
        {"id": f"seg_{i}", "start_time": s[1], "end_time": s[2], "text": s[0]}
        for i, s in enumerate(BENCHMARK_20_SEGMENTS)
    ]

    units = extract_knowledge_units(segments_input, lesson_id="benchmark_lesson_01")
    assert len(units) == 20, f"Expected 20 knowledge units, got {len(units)}"

    for i, unit in enumerate(units):
        raw_text, start_t, end_t, discipline = BENCHMARK_20_SEGMENTS[i]
        
        # 1. Verify exact timestamp retention
        assert unit.start_time == start_t
        assert unit.end_time == end_t
        assert unit.source_segment_ids == [f"seg_{i}"]

        # 2. Verify Anti-Hallucination Containment Gate
        is_valid, reason, overlap_ratio = validate_semantic_containment(raw_text, unit.statement)
        assert is_valid, f"Segment {i} ({discipline}) failed containment: {reason}"
        assert overlap_ratio > 0.35, f"Segment {i} ({discipline}) has low semantic overlap: {overlap_ratio:.2f}"

        # 3. Verify clean formal Arabic (zero vocalic fillers in statement)
        for filler in ["بص", "ركز معايا", "سمي الله", "يعني", "بقى", "اهو", "كده"]:
            assert filler not in unit.statement, f"Filler '{filler}' found in statement: {unit.statement}"


def test_anti_hallucination_rejects_unsupported_expansion():
    """
    Critical Regression Test:
    Ensures that adding unsupported outside facts (e.g. high compressive strength when only construction was taught)
    is caught and rejected by the containment validator.
    """
    raw_taught = "الحجر الجيري بيستخدم في البناء"
    hallucinated_statement = "يُستخدم الحجر الجيري في بناء الجسور نظرًا لارتفاع مقاومته للضغط وتحمله للأحمال الثقيلة."

    is_valid, reason, _ = validate_semantic_containment(raw_taught, hallucinated_statement)
    # Must be rejected because 'مقاومة الضغط' and 'الأحمال الثقيلة' were never taught in raw_taught
    assert not is_valid
    assert "expansion" in reason.lower() or "unsupported" in reason.lower()


def test_anti_hallucination_accepts_faithful_rewrite():
    """Ensures faithful pedagogical rewrite of the same statement passes containment."""
    raw_taught = "الحجر الجيري بيستخدم في البناء"
    faithful_statement = "يُستخدم صخر الحجر الجيري في مجال أعمال البناء."

    is_valid, reason, _ = validate_semantic_containment(raw_taught, faithful_statement)
    assert is_valid
