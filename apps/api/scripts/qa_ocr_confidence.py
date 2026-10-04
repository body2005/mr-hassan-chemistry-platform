"""Inspect OCR word confidence; diagnostic only, never supplies answers."""
import io
import json
from pathlib import Path
from PIL import Image, ImageOps
import pytesseract
import pypdfium2 as pdfium
from app.core.config import get_tesseract_cmd
from app.services.document_parsers import extract_pdf_page_images
from app.services.extraction_limits import check_image, ocr_slot, OCR_TIMEOUT_SECONDS


def main():
    get_tesseract_cmd()
    root = Path(__file__).resolve().parents[1] / "tests/fixtures/blind_inputs"
    report = []
    pdf = root / "05_biology_image_only_pdf.pdf"
    sources = [("png", (root / "05_biology_first_page.png").read_bytes())]
    sources += [(f"native-page-{n}", extract_pdf_page_images(None, n, file_path=str(pdf))[0][0]) for n in (1, 2)]
    with pdfium.PdfDocument(str(pdf)) as doc:
        page = doc[1]; bitmap = page.render(scale=1.5); image = bitmap.to_pil()
        buff = io.BytesIO(); image.save(buff, format="PNG")
        sources.append(("rendered-page-2-108dpi", buff.getvalue()))
        image.close(); bitmap.close(); page.close()
    for label, data in sources:
        for language in ("ara+eng", "ara"):
            with Image.open(io.BytesIO(data)) as source:
                check_image(source)
                with ImageOps.grayscale(source) as gray, ImageOps.autocontrast(gray) as prepared, ocr_slot():
                    words = pytesseract.image_to_data(prepared, lang=language, config="--psm 3", timeout=OCR_TIMEOUT_SECONDS,
                                                     output_type=pytesseract.Output.DICT)
            tokens = [{key: words[key][i] for key in ("text", "conf", "left", "top", "width", "height", "block_num", "par_num", "line_num")}
                      for i, t in enumerate(words["text"]) if t.strip()]
            weighted = sum(max(0, float(t["conf"])) * len(t["text"]) for t in tokens) / max(1, sum(len(t["text"]) for t in tokens))
            report.append({"source": label, "language": language, "weighted_confidence": weighted, "tokens": tokens})
            print(json.dumps({"source": label, "language": language, "weighted_confidence": weighted}))
    Path("/qa/ocr-confidence.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
