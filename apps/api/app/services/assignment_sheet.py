"""Arabic printable assignment sheet (PDF) generation.

Students download the sheet, solve it on paper, then upload photographed or
scanned copies. Rendering is deterministic and uses only the assignment's own
content: title, prompt, max score and due date. No AI, no invention.

Arabic text must be reshaped (contextual glyph forms) and reordered (RTL) before
being drawn with reportlab, which has no bidi support of its own.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

try:  # Optional but required for correct Arabic output; degrade loudly otherwise.
    import arabic_reshaper
    from bidi.algorithm import get_display

    _ARABIC_READY = True
except ImportError:  # pragma: no cover
    _ARABIC_READY = False

# Candidate Arabic-capable fonts installed via fonts-noto-core in Docker.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabicUI-Regular.ttf",
]
# Optional bold companion (present in fonts-noto-core on Debian bookworm).
_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf",
]

_BRAND_DARK = "#0f392b"
_ACCENT = "#059669"


def _find_font(candidates: list[str]) -> str | None:
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _find_arabic_font() -> str | None:
    """Any system Arabic font, or a bundled one next to this module."""
    found = _find_font(_FONT_CANDIDATES)
    if found:
        return found
    bundled = Path(__file__).resolve().parent / "fonts" / "NotoNaskhArabic-Regular.ttf"
    return str(bundled) if bundled.exists() else None


def _shape(text: str) -> str:
    """Reshape + bidi-reorder Arabic text; pass Latin/digits through safely."""
    if not _ARABIC_READY:
        return text
    if not any("\u0600" <= ch <= "\u06FF" for ch in text):
        return text
    return get_display(arabic_reshaper.reshape(text))


def _wrap_rtl(text: str, max_chars: int = 88) -> list[str]:
    """Naive word wrap on the logical string, then shape each line."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and length + extra > max_chars:
            lines.append(" ".join(current))
            current, length = [word], len(word)
        else:
            current.append(word)
            length += extra
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def render_assignment_sheet_pdf(
    *,
    title: str,
    prompt: str,
    max_score: float,
    due_at: datetime | None,
) -> bytes:
    """Return the PDF bytes of the printable assignment sheet."""
    font_path = _find_arabic_font()
    if not font_path:
        raise RuntimeError(
            "No Arabic font available for PDF generation (install fonts-noto-core)"
        )

    bold_path = _find_font(_BOLD_CANDIDATES) or font_path

    buffer = io.BytesIO()
    page_w, page_h = A4
    margin = 18 * mm
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle("ورقة واجب")
    c.setAuthor("منصة الكيمياء التعليمية")

    # Register regular + bold faces so <b> markup works in Paragraph-free drawing.
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont("NotoArabic", font_path))
    pdfmetrics.registerFont(TTFont("NotoArabic-Bold", bold_path))

    y = page_h - margin

    # ── Header band ─────────────────────────────────────────────────────────
    c.setFillColor(_BRAND_DARK)
    c.roundRect(margin, y - 24 * mm, page_w - 2 * margin, 24 * mm, 4 * mm, stroke=0, fill=1)
    c.setFillColor("#ffffff")
    c.setFont("NotoArabic-Bold", 15)
    c.drawRightString(page_w - margin - 8 * mm, y - 9 * mm, _shape("منصة الكيمياء التعليمية — مستر حسن شعبان"))
    c.setFont("NotoArabic", 10)
    c.drawRightString(page_w - margin - 8 * mm, y - 16 * mm, _shape("ورقة واجب — حل على الورق ثم صوّرها وارفعها"))
    c.setFont("NotoArabic-Bold", 12)
    c.drawString(margin + 8 * mm, y - 12 * mm, _shape("درجة الواجب: %g" % max_score))
    y -= 32 * mm

    # ── Title ───────────────────────────────────────────────────────────────
    c.setFillColor("#0f172a")
    for line in _wrap_rtl(title, 60):
        c.setFont("NotoArabic-Bold", 16)
        c.drawRightString(page_w - margin, y, _shape(line))
        y -= 9 * mm

    if due_at:
        c.setFillColor("#475569")
        c.setFont("NotoArabic", 10)
        c.drawRightString(page_w - margin, y, _shape("آخر موعد للتسليم: " + due_at.strftime("%Y-%m-%d")))
        y -= 8 * mm

    y -= 2 * mm

    # ── Separator ───────────────────────────────────────────────────────────
    c.setStrokeColor(_ACCENT)
    c.setLineWidth(1.4)
    c.line(margin, y, page_w - margin, y)
    y -= 10 * mm

    # ── Prompt body (the actual questions/instructions) ─────────────────────
    c.setFillColor("#1e293b")
    for raw_line in prompt.splitlines():
        for line in _wrap_rtl(raw_line.strip(), 84):
            if y < margin + 24 * mm:
                c.showPage()
                y = page_h - margin
            c.setFont("NotoArabic", 12.5)
            c.drawRightString(page_w - margin, y, _shape(line))
            y -= 7.2 * mm
        y -= 1.5 * mm  # paragraph gap between prompt lines

    # ── Answer area ─────────────────────────────────────────────────────────
    y -= 6 * mm
    if y > margin + 46 * mm:
        c.setFillColor("#475569")
        c.setFont("NotoArabic-Bold", 12)
        c.drawRightString(page_w - margin, y, _shape("مساحة إجابة الطالب"))
        y -= 8 * mm
        c.setStrokeColor("#cbd5e1")
        c.setLineWidth(0.8)
        while y > margin + 10 * mm:
            c.line(margin, y, page_w - margin, y)
            y -= 9 * mm

    c.showPage()
    c.save()
    return buffer.getvalue()
