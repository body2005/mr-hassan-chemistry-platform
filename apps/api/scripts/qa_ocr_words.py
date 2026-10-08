"""QA-only crop recognition experiment with source-derived boxes, no dictionary."""
import argparse
import json
import re
import shlex
import tempfile
import time
from pathlib import Path

from PIL import Image
import pytesseract
from app.services import ocr_quality, document_parsers
from app.services.extraction_limits import OCR_TIMEOUT_SECONDS, ExtractionLimitError
from scripts.qa_extract_fidelity import compare


def candidate(image, lang='ara+eng', *, tessdata_dir=None, word_psm=8):
    deadline = time.monotonic() + OCR_TIMEOUT_SECONDS
    def read(source, psm):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ExtractionLimitError('Word OCR exhausted its total time budget')
        config = f'--psm {psm}'
        crop_model = tessdata_dir is not None and source is not image
        if crop_model:
            config += ' --tessdata-dir ' + shlex.quote(str(tessdata_dir))
        return ocr_quality.tokens(pytesseract.image_to_data(source, lang='ara' if crop_model else lang, config=config,
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
                recognized = read(enlarged, word_psm)
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
    arg.add_argument('--candidate-tessdata-dir', type=Path)
    arg.add_argument('--word-psm', type=int, choices=[7, 8], default=8)
    args = arg.parse_args()
    if args.candidate_tessdata_dir and not (args.candidate_tessdata_dir/'ara.traineddata').is_file():
        arg.error('Missing explicit candidate Arabic model')
    ocr_quality.recognize = lambda image, lang='ara+eng': candidate(image, lang,
        tessdata_dir=args.candidate_tessdata_dir, word_psm=args.word_psm)
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
