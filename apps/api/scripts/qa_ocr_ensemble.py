"""QA-only bounded source-geometry OCR experiment; no content dictionaries."""
import argparse
import json
import re
import tempfile
import time
from pathlib import Path
from PIL import Image
import pytesseract
from app.services import ocr_quality, document_parsers
from app.services.extraction_limits import OCR_TIMEOUT_SECONDS
from scripts.qa_extract_fidelity import compare


def candidate(image, lang='ara+eng'):
    deadline = time.monotonic() + OCR_TIMEOUT_SECONDS
    def read(source, psm=3):
        return ocr_quality.tokens(pytesseract.image_to_data(source, lang=lang, config=f'--psm {psm}',
                     timeout=max(.1, deadline-time.monotonic()), output_type=pytesseract.Output.DICT))
    base = read(image)
    alternatives = [read(image, 6)]
    for scale in (.93333333, 1.1):
        with image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS) as source:
            words = read(source)
            for word in words:
                for key in ('left', 'top', 'width', 'height'):
                    word[key] /= scale
            alternatives.append(words)
    proposals = []
    for word in base:
        text = word['text'].strip('\u200e\u200f')
        if not re.fullmatch(r'[\u0621-\u065f]+', text) or ocr_quality.protected(text):
            continue
        choices = []
        for alternative in alternatives:
            matches = [other for other in alternative if re.fullmatch(r'[\u0621-\u065f]+', other['text'].strip('\u200e\u200f'))
                       and ocr_quality.overlap(word, other) >= .65]
            if len(matches) == 1:
                choices.append(matches[0])
        for candidate_text in sorted({w['text'] for w in choices}):
            agreeing = [w for w in choices if w['text'] == candidate_text]
            if candidate_text != text:
                proposals.append({'original': text, 'alternative': candidate_text, 'base_conf': word['conf'],
                                  'alternate_conf': [w['conf'] for w in agreeing], 'votes': len(agreeing)})
            if (candidate_text != text and len(agreeing) >= 2 and float(word['conf']) < 80
                    and min(float(w['conf']) for w in agreeing) >= float(word['conf']) + 10):
                word['text'] = candidate_text
                break
    base = ocr_quality.restore_placeholders(base, alternatives[0])
    text = ocr_quality.assemble_lines(base)
    print(json.dumps({'changes': proposals}, ensure_ascii=False))
    return text


def main():
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); ocr_quality.recognize = candidate
    root = Path('/srv/tests/fixtures/blind_inputs'); manifest = json.loads((root/'reference.json').read_text())['files']
    with tempfile.TemporaryDirectory() as folder:
        document_parsers.__file__ = str(Path(folder)/'app/services/document_parsers.py')
        results = [compare(name, root/name, manifest['05_biology_image_only_pdf.pdf'][:5] if name.endswith('.png') else manifest[name])
                   for name in ('05_biology_image_only_pdf.pdf', '05_biology_first_page.png')]
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    for item in results: print(json.dumps({key: item[key] for key in ('filename','actual_count','fully_matching_questions','character_error_rate')}))
    raise SystemExit(0 if all(item['passed'] for item in results) else 1)


if __name__ == '__main__': main()
