import io
import pdfplumber
from app.services.assignment_sheet import render_assignment_sheet_pdf, _shape


def test_mixed_arabic_latin_and_scientific_glyphs_are_not_dropped():
    english = 'Choose the mass unit. 12 kg.'
    science = 'H₂O Na⁺ ΔH −25 kJ/mol x² β 3 × 10⁻³ 25 °C'
    arabic = 'اشرح قانون حفظ الكتلة'
    data = render_assignment_sheet_pdf(title='Science Units', prompt='\n'.join([arabic, english, science]), max_score=7, due_at=None)
    with pdfplumber.open(io.BytesIO(data)) as document:
        chars = ''.join(character['text'] for page in document.pages for character in page.chars)
    # Glyph coverage and exact Latin/science preservation supplement, not
    # replace, the explicit rendered PNG review.
    assert english in chars and 'Science Units' in chars
    assert science in chars
    for glyph in _shape(arabic).replace(' ', ''):
        assert glyph in chars
