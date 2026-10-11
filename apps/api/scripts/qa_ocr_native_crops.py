"""QA-only: retain PDF page layout, re-read uncertain glyphs from native scan.

The manual reference is used only by the independent comparison afterwards.
"""
import argparse
import io
import json
import re
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageOps
import pytesseract
from app.services import document_parsers as parsing, ocr_quality
from app.services.extraction_limits import check_image, OCR_TIMEOUT_SECONDS, ExtractionLimitError
from scripts.qa_extract_fidelity import compare


def main():
    cli = argparse.ArgumentParser(__doc__)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    original = parsing.ocr_pdf_page
    original_recognize = ocr_quality.recognize
    proposals = []

    def pdf_ocr(file_bytes=None, page_number=1, lang="ara+eng", pdfium_doc=None, file_path=None):
        images = parsing.extract_pdf_page_images(file_bytes, page_number, file_path=file_path)
        if len(images) != 1 or not images[0][3]:
            return original(file_bytes, page_number, lang, pdfium_doc, file_path)
        data, _, _, bounds = images[0]
        native = Image.open(io.BytesIO(data))
        check_image(native)

        def recognize(image, lang="ara+eng"):
            deadline = time.monotonic() + OCR_TIMEOUT_SECONDS
            words = ocr_quality.tokens(pytesseract.image_to_data(image, lang=lang, config="--psm 3",
                timeout=OCR_TIMEOUT_SECONDS, output_type=pytesseract.Output.DICT))
            if len(words) > 5000:
                raise ExtractionLimitError("OCR word limit")
            page = pdfium_doc[page_number-1]
            try:
                width, height = page.get_size()
            finally:
                page.close()
            # Native image coordinates are derived only from source placement.
            sx, sy = image.width/width, image.height/height
            x0, y0, x1, y1 = bounds
            for word in words:
                text = word['text'].strip('\u200e\u200f')
                if not re.fullmatch(r'[\u0621-\u065f]{2,}', text) or float(word['conf']) >= 95:
                    continue
                box = ((word['left']/sx-x0)*native.width/(x1-x0),
                       (word['top']/sy-y0)*native.height/(y1-y0),
                       ((word['left']+word['width'])/sx-x0)*native.width/(x1-x0),
                       ((word['top']+word['height'])/sy-y0)*native.height/(y1-y0))
                box = (max(0, int(box[0])-8), max(0, int(box[1])-8),
                       min(native.width, int(box[2])+8), min(native.height, int(box[3])+8))
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise ExtractionLimitError("Native crop total OCR timeout")
                with native.crop(box) as crop, ImageOps.grayscale(crop) as gray:
                    found = ocr_quality.tokens(pytesseract.image_to_data(gray, lang=lang, config="--psm 8",
                        timeout=remaining, output_type=pytesseract.Output.DICT))
                if len(found) != 1:
                    continue
                other = found[0]
                if other['text'] != text:
                    proposals.append({'page': page_number, 'base': text, 'base_conf': word['conf'],
                                      'native': other['text'], 'native_conf': other['conf']})
                if (re.fullmatch(r'[\u0621-\u065f]{2,}', other['text']) and float(other['conf']) >= 95
                        and float(other['conf']) >= float(word['conf']) + 10):
                    word['text'] = other['text']
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise ExtractionLimitError("Native crop total OCR timeout")
            alternate = ocr_quality.tokens(pytesseract.image_to_data(image, lang=lang, config="--psm 6",
                timeout=remaining, output_type=pytesseract.Output.DICT))
            return ocr_quality.assemble_lines(ocr_quality.restore_placeholders(words, alternate))

        ocr_quality.recognize = recognize
        try:
            return original(file_bytes, page_number, lang, pdfium_doc, file_path)
        finally:
            ocr_quality.recognize = original_recognize
            native.close()

    parsing.ocr_pdf_page = pdf_ocr
    root = Path('/srv/tests/fixtures/blind_inputs')
    manifest = json.loads((root/'reference.json').read_text())
    with tempfile.TemporaryDirectory() as folder:
        parsing.__file__ = str(Path(folder)/'app/services/document_parsers.py')
        results = [compare(name, root/name, expected) for name, expected in manifest['files'].items()]
        results.append(compare('05_biology_first_page.png', root/'05_biology_first_page.png',
                               manifest['files']['05_biology_image_only_pdf.pdf'][:5]))
    args.output.write_text(json.dumps({'proposals': proposals, 'results': results}, ensure_ascii=False, indent=2))
    for result in results:
        print(json.dumps({key: result[key] for key in ('filename','actual_count','fully_matching_questions','character_error_rate')}))
    print(json.dumps({'proposals': proposals}, ensure_ascii=False))
    raise SystemExit(0 if all(result['passed'] for result in results) else 1)


if __name__ == '__main__':
    main()
