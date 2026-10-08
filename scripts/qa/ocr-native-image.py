"""QA-only native embedded-image OCR experiment; NEVER imported by runtime.

Compare all original fixtures without changing references, parser source or
models. A single image/no PDF text is an experiment filter, NOT proof that
every page annotation/transform is represented. Do not adopt solely on count.
"""
import argparse
import io
import json
from pathlib import Path

import pymupdf
from PIL import Image
from app.core.config import get_tesseract_cmd
from app.services import document_parsers, ocr_quality
from app.services.extraction_limits import check_image, ocr_slot
from scripts.qa_extract_fidelity import compare


def main():
    arguments = argparse.ArgumentParser(__doc__)
    arguments.add_argument('--fixtures', type=Path, default=Path('/srv/tests/fixtures/blind_inputs'))
    arguments.add_argument('--output', type=Path, required=True)
    args = arguments.parse_args()
    original = document_parsers.ocr_pdf_page
    used = []

    def recognize_native(file_bytes=None, page_number=1, lang='ara+eng', pdfium_doc=None, file_path=None):
        with (pymupdf.open(file_path) if file_path else pymupdf.open(stream=file_bytes, filetype='pdf')) as reader:
            page = reader[page_number - 1]
            images = page.get_images(full=True)
            if page.get_text().strip() or len(images) != 1 or page.rotation or page.first_annot:
                return original(file_bytes, page_number, lang, pdfium_doc, file_path)
            rects = page.get_image_rects(images[0][0])
            if len(rects) != 1 or (rects[0] & page.rect).get_area() < .98 * page.rect.get_area():
                return original(file_bytes, page_number, lang, pdfium_doc, file_path)
            data = reader.extract_image(images[0][0])['image']
        image = Image.open(io.BytesIO(data))
        try:
            check_image(image)
            get_tesseract_cmd()
            with document_parsers._OCR_SEMAPHORE, ocr_slot(), image.convert('L') as gray:
                result = ocr_quality.recognize(gray, lang=lang)
            used.append({'page': page_number, 'size': list(image.size)})
            return document_parsers.clean_arabic_ocr_text(result or '')
        finally:
            image.close()

    document_parsers.ocr_pdf_page = recognize_native
    manifest = json.loads((args.fixtures / 'reference.json').read_text(encoding='utf-8'))
    cases = dict(manifest['files'])
    for name, ref in manifest['image_reference'].items():
        cases[name] = cases[ref['pdf']][:ref['first_questions']]
    results = [compare(name, args.fixtures / name, expected) for name, expected in cases.items()]
    report = {'candidate': 'QA-only native embedded-image OCR', 'native_pages': used,
              'results': results, 'passed': sum(item['passed'] for item in results),
              'failed': sum(not item['passed'] for item in results), 'skipped': 0}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('candidate', 'native_pages', 'passed', 'failed', 'skipped')}))
    for result in results:
        print(json.dumps({key: result[key] for key in ('filename', 'actual_count', 'fully_matching_questions', 'character_error_rate')}, ensure_ascii=False))
    raise SystemExit(1 if report['failed'] else 0)


if __name__ == '__main__':
    main()
