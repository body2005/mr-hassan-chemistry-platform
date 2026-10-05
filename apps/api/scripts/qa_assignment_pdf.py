"""Generate a synthetic mixed-script sheet for visual glyph/layout QA.

Run inside the isolated QA image: python -m scripts.qa_assignment_pdf.
The sample is test data only, not a replacement for a teacher's question.
"""
from pathlib import Path
from app.services.assignment_sheet import render_assignment_sheet_pdf


def main():
    prompt = '\n'.join([
        'اشرح قانون حفظ الكتلة مع ذكر مثال.',
        'Choose the mass unit. 12 kg.',
        'قارن سرعة الجسم v = 12 m/s مع سرعة الصوت.',
        'H₂O + Na⁺ → products; ΔH = −25 kJ/mol; x² + β = 3 × 10⁻³; 25 °C',
        '(A) kilogram    (B) second',
    ])
    target = Path('/qa/role-pdf-fonts.pdf')
    target.write_bytes(render_assignment_sheet_pdf(title='Science Units — وحدات القياس', prompt=prompt, max_score=7, due_at=None))
    print(f'Generated synthetic PDF: {target.name}; {target.stat().st_size} bytes')


if __name__ == '__main__':
    main()
