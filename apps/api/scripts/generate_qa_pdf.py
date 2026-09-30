"""Generate a valid, reproducible multi-megabyte PDF (real embedded raster pages)."""
import os
from pathlib import Path
import random
import pymupdf

directory = Path(os.getenv("QA_MEDIA_DIR", "/qa/media"))
directory.mkdir(parents=True, exist_ok=True)
document = pymupdf.open()
rng = random.Random(84782)
for number in range(8):
    page = document.new_page(width=720, height=960)
    pix = pymupdf.Pixmap(pymupdf.csRGB, 1200, 900, rng.randbytes(1200 * 900 * 3), False)
    page.insert_image(pymupdf.Rect(30, 80, 690, 850), pixmap=pix)
    page.insert_text((40, 50), f"Chemistry QA large PDF page {number + 1}")
document.save(str(directory / "large.pdf"), deflate=False)
document.close()
print({"pdf_bytes": (directory / "large.pdf").stat().st_size, "pages": 8})
