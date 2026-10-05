"""QA-only OCR raster experiment, never a production parser override.

Mount into the isolated qa-tests container and pass --scale and --output.
Uses the unchanged recognition timeout/pixel budgets and full blind reference;
the reference is comparison-only, never used to choose or replace words.
"""
import argparse
import sys

from app.services import document_parsers
from scripts import qa_extract_fidelity

cli = argparse.ArgumentParser(__doc__)
cli.add_argument("--scale", type=float, required=True)
cli.add_argument("--output", required=True)
args = cli.parse_args()
if not 1 <= args.scale <= 4:
    cli.error("scale must be between 1 and 4; pixel/resource caps still apply")
original = document_parsers.render_scale
document_parsers.render_scale = lambda width, height, desired=1.5: original(width, height, desired=args.scale)
document_parsers.PARSER_OCR_VERSION += f"-qa-raster-{args.scale}"
qa_extract_fidelity.PARSER_OCR_VERSION = document_parsers.PARSER_OCR_VERSION
sys.argv = [sys.argv[0], "--output", args.output]
qa_extract_fidelity.main()
