"""QA experiment: geometry-only line recognition, never reference-driven OCR."""
import argparse
import json
import time
from pathlib import Path
import tempfile

import pytesseract
from app.services import document_parsers, ocr_quality
from app.services.extraction_limits import OCR_TIMEOUT_SECONDS, ExtractionLimitError
from scripts.qa_extract_fidelity import compare


def line_candidate(image, lang='ara+eng'):
    deadline = time.monotonic() + OCR_TIMEOUT_SECONDS
    data = pytesseract.image_to_data(image, lang=lang, config='--psm 3', timeout=OCR_TIMEOUT_SECONDS,
                                    output_type=pytesseract.Output.DICT)
    boxes = sorted(ocr_quality.tokens(data), key=lambda word: word['top'] + word['height'] / 2)
    lines = []
    for word in boxes:
        top, bottom = word['top'], word['top'] + word['height']
        matched = next((line for line in lines if min(bottom, line[1]) - max(top, line[0]) > min(word['height'], line[1] - line[0]) * .5), None)
        if matched is None:
            lines.append([top, bottom])
        else:
            matched[0], matched[1] = min(top, matched[0]), max(bottom, matched[1])
    result = []
    for top, bottom in sorted(lines):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ExtractionLimitError('Line OCR exceeded its time budget')
        with image.crop((0, max(0, top - 5), image.width, min(image.height, bottom + 5))) as crop:
            result.append(pytesseract.image_to_string(crop, lang=lang, config='--psm 7', timeout=remaining).strip())
    return '\n'.join(result)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--scale', type=float, default=1.5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    scale = document_parsers.render_scale
    document_parsers.render_scale = lambda width, height, desired=1.5: scale(width, height, args.scale)
    ocr_quality.recognize = line_candidate
    root = Path('/srv/tests/fixtures/blind_inputs')
    manifest = json.loads((root / 'reference.json').read_text())['files']
    with tempfile.TemporaryDirectory() as folder:
        document_parsers.__file__ = str(Path(folder) / 'app/services/document_parsers.py')
        results = [compare(name, root / name, manifest['05_biology_image_only_pdf.pdf'][:5] if name.endswith('.png') else manifest[name])
                   for name in ('05_biology_image_only_pdf.pdf', '05_biology_first_page.png')]
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    for item in results:
        print(json.dumps({key: item[key] for key in ('filename', 'actual_count', 'fully_matching_questions', 'character_error_rate')}))
    raise SystemExit(0 if all(item['passed'] for item in results) else 1)


if __name__ == '__main__':
    main()
