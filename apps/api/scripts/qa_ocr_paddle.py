"""QA-only local neural line-recognition candidate, not a production dependency.

No reference text is supplied to either OCR engine. Models are local; images
are never submitted to a remote OCR API. Run AFTER load/fault/restore, not
during their measurements. Results must pass strict fidelity before adoption.
"""
import argparse
import json
import re
import tempfile
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pytesseract
from paddleocr import TextRecognition
from app.services import document_parsers, ocr_quality
from app.services.extraction_limits import OCR_TIMEOUT_SECONDS, ExtractionLimitError
from scripts.qa_extract_fidelity import compare


def recognizer(model, mode='lines'):
    def candidate(image, lang='ara+eng'):
        deadline = time.monotonic() + OCR_TIMEOUT_SECONDS
        data = pytesseract.image_to_data(image, lang=lang, config='--psm 3',
                                        timeout=OCR_TIMEOUT_SECONDS, output_type=pytesseract.Output.DICT)
        words = ocr_quality.tokens(data)
        if len(words) > 5000:
            raise ExtractionLimitError('Too many OCR words')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ExtractionLimitError('Candidate exceeded its OCR budget')
        alternate = ocr_quality.tokens(pytesseract.image_to_data(image, lang=lang, config='--psm 6',
                         timeout=remaining, output_type=pytesseract.Output.DICT))
        if len(alternate) > 5000:
            raise ExtractionLimitError('Too many alternate OCR words')
        words = ocr_quality.restore_placeholders(words, alternate)
        if mode == 'words':
            proposals = []
            for word in words:
                original = word['text']
                if float(word['conf']) >= 85 or not re.fullmatch(r'[\u0621-\u064a\u064b-\u065f]{3,}', original):
                    continue
                if time.monotonic() >= deadline:
                    raise ExtractionLimitError('Candidate exceeded its total OCR budget')
                bounds = (max(0, word['left']-12), max(0, word['top']-6),
                          min(image.width, word['left']+word['width']+12),
                          min(image.height, word['top']+word['height']+6))
                with image.crop(bounds).convert('RGB') as crop:
                    prediction = list(model.predict(input=np.asarray(crop), batch_size=1))
                if time.monotonic() > deadline:
                    raise ExtractionLimitError('Candidate exceeded its total OCR budget')
                if len(prediction) != 1:
                    continue
                recognized, score = str(prediction[0]['rec_text']), float(prediction[0]['rec_score'])
                accepted = score >= .97 and bool(re.fullmatch(r'[\u0621-\u064a\u064b-\u065f]{3,}', recognized))
                proposals.append({'original': original, 'candidate': recognized, 'score': score, 'accepted': accepted})
                if accepted:
                    word['text'] = recognized
            print(json.dumps({'word_proposals': proposals}, ensure_ascii=False))
            return ocr_quality.assemble_lines(words)
        groups = OrderedDict()
        for word in words:
            groups.setdefault((word['block_num'], word['par_num'], word['line_num']), []).append(word)
        # Same geometry-only blank attachment as the baseline, before taking
        # a line crop. Never let an OCR-engine comparison lose a known blank.
        for key, symbols in list(groups.items()):
            if not all(re.fullmatch(r'\.{3,}', word['text']) for word in symbols):
                continue
            top = min(word['top'] for word in symbols)
            bottom = max(word['top'] + word['height'] for word in symbols)
            targets = []
            for other, line in groups.items():
                if other == key or not any(re.search(r'[\u0621-\u064a]', word['text']) for word in line):
                    continue
                start = min(word['top'] for word in line)
                end = max(word['top'] + word['height'] for word in line)
                if min(bottom, end)-max(top, start) >= min(bottom-top, end-start)*.5:
                    targets.append(other)
            if len(targets) == 1:
                target = groups[targets[0]]
                for symbol in symbols:
                    position = next((i for i, word in enumerate(target) if word['left'] < symbol['left']), len(target))
                    target.insert(position, symbol)
                del groups[key]
        result, proposals = [], []
        for line in groups.values():
            original = ' '.join(w['text'] for w in line)
            # This Arabic-only model must never replace Latin/science lines.
            if re.search(r'[A-Za-z₀-₉⁰-⁹=+−/*^%Ω]', original) or not re.search(r'[\u0621-\u064a]', original):
                result.append(original)
                continue
            if time.monotonic() >= deadline:
                raise ExtractionLimitError('Candidate exceeded its total OCR budget')
            left = max(0, min(w['left'] for w in line)-8)
            top = max(0, min(w['top'] for w in line)-8)
            right = min(image.width, max(w['left']+w['width'] for w in line)+8)
            bottom = min(image.height, max(w['top']+w['height'] for w in line)+8)
            with image.crop((left, top, right, bottom)).convert('RGB') as crop:
                predictions = list(model.predict(input=np.asarray(crop), batch_size=1))
            if time.monotonic() > deadline:
                raise ExtractionLimitError('Candidate exceeded its total OCR budget')
            if len(predictions) != 1:
                result.append(original)
                continue
            recognized = str(predictions[0]['rec_text'])
            score = float(predictions[0]['rec_score'])
            # Preserve source-derived numbers and placeholders, not a nicer
            # model output that silently loses or changes protected elements.
            preserve = (re.findall(r'[0-9٠-٩]+', original) == re.findall(r'[0-9٠-٩]+', recognized)
                        and len(re.findall(r'\.{3,}', original)) == len(re.findall(r'\.{3,}', recognized)))
            chosen = recognized if score >= .95 and preserve else original
            proposals.append({'original': original, 'candidate': recognized, 'score': score, 'accepted': chosen != original})
            result.append(chosen)
        print(json.dumps({'line_proposals': proposals}, ensure_ascii=False))
        return '\n'.join(result)
    return candidate


def main():
    arg = argparse.ArgumentParser(__doc__)
    arg.add_argument('--model-dir', type=Path, required=True)
    arg.add_argument('--output', type=Path, required=True)
    arg.add_argument('--mode', choices=('lines', 'words'), default='lines')
    args = arg.parse_args()
    model = TextRecognition(model_name='arabic_PP-OCRv5_mobile_rec', model_dir=str(args.model_dir),
                            device='cpu', cpu_threads=1, enable_mkldnn=False)
    ocr_quality.recognize = recognizer(model, args.mode)
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
