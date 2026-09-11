"""
=============================================================================
BENCHMARK TESTS: QUESTION CLASSIFICATION & DOCUMENT INGESTION
=============================================================================
Tests question block classification across 4+ diverse real-world exam formats:
1. Standard formal Arabic numbering ("السؤال 1: ...") with letter options.
2. Short prefix numbering ("س1: ...") with choices.
3. Plain digit numbering without keywords ("1- ما هي ...؟").
4. Distant answer keys at the bottom of the document (mapping letter to option text).
5. Table-structured questions (reusing table rows).
6. Ambiguous/uncertain blocks flagged as "uncertain" rather than assumed content.
7. Pure textbook content correctly classified as "content".
=============================================================================
"""
import pytest
from app.services.knowledge_center_service import (
    classify_and_parse_question,
    extract_distant_answer_keys,
    parse_table_questions,
    resolve_correct_answer_text,
)


def test_format_1_standard_formal():
    block = """
    السؤال الأول: أي المعادن التالية أكثر صلادة على مقياس موهس للصلادة؟
    أ. الكوارتز
    ب. التلك
    ج. الألماس
    د. الكالسيت
    الإجابة: ج
    """
    state, q_data = classify_and_parse_question(block)
    assert state == "question"
    assert q_data is not None
    assert "أكثر صلادة" in q_data["question_text"]
    assert q_data["question_type"] == "multiple_choice"
    assert len(q_data["options"]) == 4
    assert q_data["correct_answer"] == "الألماس"
    assert q_data["needs_answer_review"] is False


def test_format_2_short_prefix():
    block = """
    س2: ما هي الخاصية البصرية التي تدل على لون مسحوق المعدن؟
    أ) المخدش
    ب) البريق
    ج) الشفافية
    د) عرض الألوان
    الإجابة الصحيحة: أ
    """
    state, q_data = classify_and_parse_question(block)
    assert state == "question"
    assert q_data is not None
    assert "المخدش" in q_data["correct_answer"]
    assert q_data["needs_answer_review"] is False


def test_format_3_plain_number_no_keyword():
    block = """
    3. يعتبر الجرانيت من الصخور النارية:
    أ- الجوفية الحامضية
    ب- السطحية القاعدية
    ج- المتداخلة المتوسطة
    د- البركانية فوق القاعدية
    الحل: أ
    """
    state, q_data = classify_and_parse_question(block)
    assert state == "question"
    assert q_data is not None
    assert "الجرانيت" in q_data["question_text"]
    assert q_data["correct_answer"] == "الجوفية الحامضية"


def test_format_4_distant_answer_key():
    exam_text = """
    س1: الصخر الذي يمثل صخراً نارياً بركانياً قاعدياً هو:
    أ. البازلت
    ب. الريوليت
    ج. الجرانيت
    د. الأنديسايت

    س2: المخدش هو لون مسحوق المعدن عند حكه بمخدش خزفي.
    أ. صح
    ب. خطأ

    === نموذج الإجابات النهائية ===
    1- أ
    2- أ
    """
    distant_keys = extract_distant_answer_keys(exam_text)
    assert distant_keys.get("1") == "أ"
    assert distant_keys.get("2") == "أ"

    q1_block = """
    س1: الصخر الذي يمثل صخراً نارياً بركانياً قاعدياً هو:
    أ. البازلت
    ب. الريوليت
    ج. الجرانيت
    د. الأنديسايت
    """
    state1, data1 = classify_and_parse_question(q1_block, distant_keys=distant_keys)
    assert state1 == "question"
    assert data1["correct_answer"] == "البازلت"
    assert data1["needs_answer_review"] is False


def test_format_5_table_structured_questions():
    table = {
        "headers": ["رقم السؤال", "نص السؤال", "أ", "ب", "ج", "د", "الإجابة الصحيحة"],
        "rows": [
            ["1", "أي مما يلي يمثل صخراً رسوبياً كيميائياً؟", "الحجر الجيري", "البريشيا", "الكونجلوميرات", "الفحم", "الحجر الجيري"],
            ["2", "مقياس موهس يبدأ بمعدن:", "التلك", "الجبس", "الكالسيت", "الفلوريت", "أ"],
        ]
    }
    extracted = parse_table_questions([table])
    assert len(extracted) == 2
    assert extracted[0]["question_text"] == "أي مما يلي يمثل صخراً رسوبياً كيميائياً؟"
    assert extracted[0]["correct_answer"] == "الحجر الجيري"
    assert extracted[0]["needs_answer_review"] is False

    assert extracted[1]["correct_answer"] == "التلك"
    assert extracted[1]["needs_answer_review"] is False


def test_format_6_uncertain_block():
    block = "هل تعلم كيف تتكون الطيات المحدبة والمقعرة في القشرة الأرضية نتيجة قوى الضغط الجانبية؟"
    state, data = classify_and_parse_question(block)
    assert state == "uncertain"
    assert data is not None
    assert data["classification_confidence"] == "uncertain"
    assert data["needs_answer_review"] is True


def test_format_7_pure_content():
    content_block = """
    تعتبر التراكيب الجيولوجية الأولية هي التراكيب التي تتخلف بالصخور الرسوبية تحت تأثير عوامل بيئية ومناخية خاصة
    مثل الرياح والتيارات المائية والحرارة والجفاف دون أي تدخل من جانب القوى التكتونية.
    """
    state, data = classify_and_parse_question(content_block)
    assert state == "content"
    assert data is None


def test_unresolved_answer_falls_back_to_review():
    block = """
    س5: ما الفرق الجوهري بين الفالق العادي والفالق المعكوس؟
    أ. زاوية الميل
    ب. اتجاه حركة صخور الحائط العلوي
    ج. نوع الصخور المتأثرة
    د. لا يوجد فرق
    """
    state, data = classify_and_parse_question(block)
    assert state == "question"
    assert data["correct_answer"] is None
    assert data["needs_answer_review"] is True


def test_format_8_ocr_spacing_and_delimiters():
    # OCR output often introduces irregular spaces inside parentheses or around dots/slashes
    block = """
    السؤال السادس: أي من المعادن التالية ينتمي لمجموعة السيليكات؟
    ( أ ) الكوارتز
    ب . الكالسيت
    ج / الجبس
    د : الهيماتيت
    الحل : أ
    """
    state, data = classify_and_parse_question(block)
    assert state == "question"
    assert data is not None
    assert len(data["options"]) == 4
    assert data["options"][0]["text"] == "الكوارتز"
    assert data["options"][1]["text"] == "الكالسيت"
    assert data["options"][2]["text"] == "الجبس"
    assert data["options"][3]["text"] == "الهيماتيت"
    assert data["correct_answer"] == "الكوارتز"
    assert data["needs_answer_review"] is False


def test_format_9_ocr_inline_options():
    block = """
    1. ما هو المكون الأساسي لصخر الرخام؟
    ( أ ) الكالسيت   ( ب ) الكوارتز   ( ج ) الفلسبار   ( د ) الجبس
    الإجابة: أ
    """
    state, data = classify_and_parse_question(block)
    assert state == "question"
    assert data is not None
    assert len(data["options"]) == 4
    assert data["options"][0]["text"] == "الكالسيت"
    assert data["options"][1]["text"] == "الكوارتز"
    assert data["options"][2]["text"] == "الفلسبار"
    assert data["options"][3]["text"] == "الجبس"
    assert data["correct_answer"] == "الكالسيت"


def test_format_10_administrative_and_narrative_rejection():
    # Administrative committee & credits must never become questions
    admin_block = "أ.د عبدالله محمد إبراهيم أ.د محمد جابر بركات إشراف علمى تنمية مادة العلوم"
    st, dt = classify_and_parse_question(admin_block)
    assert st == "content"
    assert dt is None

    # Narrative paragraph with rhetorical question must not become an assessment question
    narrative_block = "إذا تأملنا فى حياتنا الآن نستطيع أن نقول ماذا فى عالمنا ليس جيولوجيا ؟ وقبل أن نجيب على هذا السؤال يجب علينا أولاً أن نعرف ما الجيولوجيا."
    st, dt = classify_and_parse_question(narrative_block)
    assert st == "content"
    assert dt is None

