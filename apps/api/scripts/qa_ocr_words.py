"""QA-only crop recognition experiment with source-derived boxes, no dictionary."""
import argparse
import json
import re
import tempfile
import time
from pathlib import Path

from PIL import Image
import pytesseract
from app.services import ocr_quality, document_parsers
from app.services.extraction_limits import OCR_TIMEOUT_SECONDS, ExtractionLimitError
from scripts.qa_extract_fidelity import compare


def candidate(image, lang='ara+eng'):
    deadline = time.monotonic() + OCR_TIMEOUT_SECONDS
    def read(source, psm):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ExtractionLimitError('Word OCR exhausted its total time budget')
        return ocr_quality.tokens(pytesseract.image_to_data(source, lang=lang, config=f'--psm {psm}',
                     timeout=remaining, output_type=pytesseract.Output.DICT))
    words = read(image, 3)
    alternatives = read(image, 6)
    ocr_quality.restore_placeholders(words, alternatives)
    proposals = []
    for word in words:
        text = word['text'].strip('\u200e\u200f')
        if not re.fullmatch(r'[\u0621-\u065f]{3,}', text) or float(word['conf']) >= 95:
            continue
        left, top = word['left'], word['top']
        with image.crop((max(0, left-4), max(0, top-5), min(image.width, left+word['width']+4),
                         min(image.height, top+word['height']+5))) as crop:
            with crop.resize((crop.width*2, crop.height*2), Image.Resampling.LANCZOS) as enlarged:
                recognized = read(enlarged, 8)
        if len(recognized) != 1:
            continue
        other = recognized[0]
        if text != other['text']:
            proposals.append({'original': text, 'alternative': other['text'], 'base_conf': word['conf'], 'alternate_conf': other['conf']})
        if (re.fullmatch(r'[\u0621-\u065f]{3,}', other['text']) and float(other['conf']) >= 85
                and float(other['conf']) >= float(word['conf']) + 10):
            word['text'] = other['text']
    print(json.dumps({'proposals': proposals}, ensure_ascii=False))
    return ocr_quality.assemble_lines(words)


def main():
    arg = argparse.ArgumentParser(__doc__)
    arg.add_argument('--output', type=Path, required=True)
    args = arg.parse_args()
    ocr_quality.recognize = candidate
    root = Path('/srv/tests/fixtures/blind_inputs')
    manifest = json.loads((root/'reference.json').read_text())['files']
    with tempfile.TemporaryDirectory() as folder:
        document_parsers.__file__ = str(Path(folder)/'app/services/document_parsers.py')
        results = [compare(name, root/name, manifest['05_biology_image_only_pdf.pdf'][:5] if name.endswith('.png') else manifest[name])
                   for name in ('05_biology_image_only_pdf.pdf', '05_biology_first_page.png')]
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    for item in results:
        print(json.dumps({key: item[key] for key in ('filename', 'actual_count', 'fully_matching_questions', 'character_error_rate')}))
    raise SystemExit(0 if all(item['passed'] for item in results) else 1)


if __name__ == '__main__':
    main()
