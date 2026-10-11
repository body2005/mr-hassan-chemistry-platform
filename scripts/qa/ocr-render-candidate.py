"""QA-only bounded render-scale comparison; not a runtime parser dependency.

Uses ALL original SHA fixtures and the unchanged strict comparator. Run each
candidate in a fresh offline container/cache. No dictionaries or answer text.
"""
import argparse
import json
from pathlib import Path
from PIL import Image

from app.services import document_parsers, ocr_quality
from scripts.qa_extract_fidelity import compare


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--scale', type=float, required=True)
    parser.add_argument('--retain-color', action='store_true')
    parser.add_argument('--language', choices=['ara+eng', 'eng+ara', 'ara'], default='ara+eng')
    parser.add_argument('--fixtures', type=Path, default=Path('/srv/tests/fixtures/blind_inputs'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1.25 <= args.scale <= 3:
        parser.error('Scale must be within the existing bounded1.25..3 range')
    original = document_parsers.render_scale
    document_parsers.render_scale = lambda width, height, desired=1.5: original(width, height, desired=args.scale)
    recognize = ocr_quality.recognize
    ocr_quality.recognize = lambda image, lang='ara+eng': recognize(image, lang=args.language)
    if args.retain_color:
        convert = Image.Image.convert
        def retain_color(image, mode=None, *positional, **keywords):
            return image.copy() if mode == 'L' else convert(image, mode, *positional, **keywords)
        Image.Image.convert = retain_color
    manifest = json.loads((args.fixtures / 'reference.json').read_text(encoding='utf-8'))
    cases = dict(manifest['files'])
    for name, reference in manifest['image_reference'].items():
        cases[name] = cases[reference['pdf']][:reference['first_questions']]
    results = [compare(name, args.fixtures / name, expected) for name, expected in cases.items()]
    report = {'candidate': 'QA-only bounded PDF render scale', 'scale': args.scale, 'retain_color': args.retain_color,
              'language': args.language,
              'results': results, 'passed': sum(result['passed'] for result in results),
              'failed': sum(not result['passed'] for result in results), 'skipped': 0}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for result in results:
        print(json.dumps({key: result[key] for key in ('filename', 'actual_count', 'fully_matching_questions',
                                                      'character_error_rate')}, ensure_ascii=False))
    print(json.dumps({key: report[key] for key in ('candidate', 'scale', 'passed', 'failed', 'skipped')}))
    raise SystemExit(int(report['failed'] != 0))


if __name__ == '__main__':
    main()
