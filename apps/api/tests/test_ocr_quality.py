from app.services.ocr_quality import recover_scripts
from app.services.exam_text_extractor import segment_exam_document


def word(text, confidence=60, left=100):
    return dict(text=text, conf=confidence, left=left, top=100, width=40, height=20)


def test_confidence_recovery_uses_matching_source_geometry_not_a_dictionary():
    base = [word('abcd'), word('different', left=200)]
    alternate = [word('كلمة', 94), word('أخرى', 94, left=400)]
    assert [w['text'] for w in recover_scripts(base, alternate)] == ['كلمة', 'different']


def test_recovery_never_changes_numbers_signs_units_or_formulas():
    protected = ['12', '3.5', 'm/s', 'cm', 'Hz', 'HCl', 'Na2CO3', 'DNA', 'x²', '−8']
    for source in protected:
        assert recover_scripts([word(source)], [word('كلمة', 99)])[0]['text'] == source


def test_mirrored_numeric_options_do_not_swallow_numbered_questions():
    questions = segment_exam_document('1. ما قيمة المتغير؟\n)1( اختيار أول\n(2) اختيار ثان\n2. اشرح الطريقة.')
    assert len(questions) == 2
    assert questions[0]['question_text'] == 'ما قيمة المتغير؟'
    assert [o['text'] for o in questions[0]['options']] == ['اختيار أول', 'اختيار ثان']
    assert questions[1]['question_text'] == 'اشرح الطريقة.'
