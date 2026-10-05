"""QA-only: compare embedded full-page scans without PDF raster resampling.

No fixture labels/words are supplied to recognition; the independent full
source reference is used afterwards. Runtime budgets remain unchanged.
"""
import argparse
import io
import json
from pathlib import Path

from PIL import Image
from app.services import document_parsers as parsing, ocr_quality
from app.services.extraction_limits import check_image
from scripts.qa_extract_fidelity import compare

cli = argparse.ArgumentParser(__doc__)
cli.add_argument('--output', type=Path, required=True)
args = cli.parse_args()
original = parsing.ocr_pdf_page


def native(file_bytes=None, page_number=1, lang='ara+eng', pdfium_doc=None, file_path=None):
    images = parsing.extract_pdf_page_images(file_bytes, page_number, file_path=file_path)
    if len(images) != 1 or not images[0][3] or pdfium_doc is None:
        return original(file_bytes, page_number, lang, pdfium_doc, file_path)
    page = pdfium_doc[page_number - 1]
    try:
        width, height = page.get_size()
    finally:
        page.close()
    data, _, _, bounds = images[0]
    x0, y0, x1, y1 = bounds
    if abs(x0) > 1 or abs(y0) > 1 or abs(x1 - width) > 1 or abs(y1 - height) > 1:
        return original(file_bytes, page_number, lang, pdfium_doc, file_path)
    with Image.open(io.BytesIO(data)) as image:
        check_image(image)
        with image.convert('L') as gray:
            return parsing.clean_arabic_ocr_text(ocr_quality.recognize(gray, lang=lang))


parsing.ocr_pdf_page = native
fixtures = Path('/srv/tests/fixtures/blind_inputs')
manifest = json.loads((fixtures / 'reference.json').read_text(encoding='utf-8'))
cases = dict(manifest['files'])
for name, ref in manifest['image_reference'].items():
    cases[name] = cases[ref['pdf']][:ref['first_questions']]
results = [compare(name, fixtures / name, expected) for name, expected in cases.items()]
report = {'candidate': 'native-full-page-no-resampling', 'results': results,
          'passed': sum(r['passed'] for r in results), 'failed': sum(not r['passed'] for r in results), 'skipped': 0}
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: report[k] for k in ('candidate', 'passed', 'failed', 'skipped')}))
for result in results:
    print(json.dumps({k: result[k] for k in ('filename', 'actual_count', 'fully_matching_questions', 'character_error_rate')}))
raise SystemExit(bool(report['failed']))
