"""QA-only model comparison. Does not change production models or references.

Mount a private model directory read-only and run --help for exact arguments.
Never import this module from a request handler or production parser.
"""
import argparse
import hashlib
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--tessdata-dir', type=Path, required=True)
    parser.add_argument('--ara-sha256', required=True)
    parser.add_argument('--eng-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for name, expected in (('ara', args.ara_sha256), ('eng', args.eng_sha256)):
        path = args.tessdata_dir / (name + '.traineddata')
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
            parser.error('Missing or unsafe QA model file')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected.lower():
            parser.error('Model SHA-256 mismatch')
    os.environ['TESSDATA_PREFIX'] = str(args.tessdata_dir.resolve())
    from app.services import document_parsers
    # Parser cache must NOT mix production and candidate-model results.
    document_parsers.PARSER_OCR_VERSION += '-qa-best-' + args.ara_sha256[:12]
    from scripts import qa_extract_fidelity
    sys.argv = [sys.argv[0], '--output', str(args.output)]
    qa_extract_fidelity.main()


if __name__ == '__main__':
    main()
