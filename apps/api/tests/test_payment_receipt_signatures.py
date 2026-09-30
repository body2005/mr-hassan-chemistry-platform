from io import BytesIO

import fitz
from PIL import Image

from app.api.routes.payments import _valid_receipt_file


def test_payment_receipts_reject_fake_and_mismatched_formats(tmp_path) -> None:
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"not a PDF")
    assert not _valid_receipt_file(str(fake_pdf), ".pdf")

    picture = Image.new("RGB", (4, 4), "white")
    buffer = BytesIO()
    picture.save(buffer, format="PNG")
    png = tmp_path / "real.png"
    png.write_bytes(buffer.getvalue())
    assert _valid_receipt_file(str(png), ".png")
    assert not _valid_receipt_file(str(png), ".jpg")

    pdf = tmp_path / "real.pdf"
    document = fitz.open()
    document.new_page()
    document.save(str(pdf))
    document.close()
    assert _valid_receipt_file(str(pdf), ".pdf")
