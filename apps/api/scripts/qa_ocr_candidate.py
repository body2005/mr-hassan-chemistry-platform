"""Evaluate one bounded OCR candidate without changing the running API.

Models must be pre-downloaded/checksummed. Reports use the independent manual
reference; no reference text is supplied to Tesseract or runtime parsing.
"""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile

import pytesseract
from app.services import document_parsers as parsing
from scripts.qa_extract_fidelity import compare


def main():
    arg = argparse.ArgumentParser(__doc__)
    arg.add_argument("--scale", type=float, default=3.0)
    arg.add_argument("--language", default="ara+eng")
    arg.add_argument("--model-dir", type=Path)
    arg.add_argument("--native-pdf", action="store_true", help="QA only: OCR original full-page raster")
    arg.add_argument('--preprocess', choices=('none', 'contrast', 'threshold'), default='none')
    arg.add_argument("--psm", type=int, choices=(3, 4, 6, 11), default=3)
    arg.add_argument("--output", type=Path, required=True)
    args = arg.parse_args()
    if not 1.0 <= args.scale <= 3.0:
        raise ValueError("Candidate scale must remain within render budgets")
    if args.model_dir:
        os.environ["TESSDATA_PREFIX"] = str(args.model_dir)
    original_ocr, original_data, original_scale = pytesseract.image_to_string, pytesseract.image_to_data, parsing.render_scale

    def candidate(image, **kwargs):
        kwargs["lang"] = args.language
        kwargs["config"] = re.sub(r"--psm\s+\d+", f"--oem 1 --psm {args.psm}", kwargs.get("config", "--psm 3"))
        return original_ocr(image, **kwargs)

    # Process-local overrides only. The shared API containers are untouched.
    pytesseract.image_to_string = candidate
    def candidate_data(image, **kwargs):
        transformed = None
        if args.preprocess != 'none':
            from PIL import ImageOps
            transformed = ImageOps.autocontrast(image) if args.preprocess == 'contrast' else image.point(lambda value: 255 if value > 160 else 0)
        if args.language != "ara+eng":
            kwargs["lang"] = args.language
        kwargs["config"] = re.sub(r"--psm\s+\d+", f"--oem 1 --psm {args.psm}", kwargs.get("config", "--psm 3"))
        try:
            return original_data(transformed if transformed is not None else image, **kwargs)
        finally:
            if transformed is not None:
                transformed.close()
    pytesseract.image_to_data = candidate_data
    parsing.render_scale = lambda width, height, desired=3.0: original_scale(width, height, args.scale)
    if args.native_pdf:
        def native_pdf(file_bytes=None, page_number=1, lang="ara+eng", pdfium_doc=None, file_path=None):
            images = parsing.extract_pdf_page_images(file_bytes, page_number, file_path=file_path)
            if len(images) != 1:
                raise ValueError("Candidate requires one original raster per page")
            return parsing.ocr_image_bytes(images[0][0], lang=lang)[0]
        parsing.ocr_pdf_page = native_pdf
    fixtures = Path(__file__).resolve().parents[1] / "tests/fixtures/blind_inputs"
    manifest = json.loads((fixtures / "reference.json").read_text(encoding="utf-8"))
    cases = {"05_biology_image_only_pdf.pdf": manifest["files"]["05_biology_image_only_pdf.pdf"],
             "05_biology_first_page.png": manifest["files"]["05_biology_image_only_pdf.pdf"][:5]}
    with tempfile.TemporaryDirectory(prefix="qa-ocr-candidate-") as cache_root:
        parsing.__file__ = str(Path(cache_root) / "app/services/document_parsers.py")
        results = [compare(name, fixtures / name, expected) for name, expected in cases.items()]
    report = {"experimental_only": True, "scale": args.scale, "language": args.language, "psm": args.psm,
              "model_dir": str(args.model_dir) if args.model_dir else "distro", "results": results}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in results:
        print(json.dumps({k: item[k] for k in ("filename", "actual_count", "fully_matching_questions", "character_error_rate")}, ensure_ascii=False))
    raise SystemExit(0 if all(r["passed"] for r in results) else 1)


if __name__ == "__main__":
    main()
