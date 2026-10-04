"""Pre-allocation document/OCR budgets; no question-specific content rules."""
import io
import math
import os
import zipfile
from contextlib import contextmanager

from PIL import Image

from app.core.config import get_settings
from app.core.rate_limit import _get_redis_client

MAX_PAGES = 100
MAX_PAGE_POINTS = 14_400
MAX_RENDER_SIDE = 4096
MAX_RENDER_PIXELS = 8_000_000
MAX_IMAGE_PIXELS = 64_000_000
MAX_IMAGE_SIDE = 16_000
OCR_TIMEOUT_SECONDS = 20
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class ExtractionLimitError(ValueError):
    pass


def render_scale(width: float, height: float, desired: float = 3.0) -> float:
    if not all(math.isfinite(v) and 0 < v <= MAX_PAGE_POINTS for v in (width, height)):
        raise ExtractionLimitError("Page dimensions exceed safe extraction limits")
    # Budget before render, including rounding up the bitmap dimensions.
    scale = min(desired, (MAX_RENDER_SIDE - 1) / width, (MAX_RENDER_SIDE - 1) / height,
                math.sqrt((MAX_RENDER_PIXELS - 2 * MAX_RENDER_SIDE) / (width * height)))
    return scale


def check_image(image: Image.Image) -> None:
    if image.width < 1 or image.height < 1 or max(image.size) > MAX_IMAGE_SIDE or image.width * image.height > MAX_IMAGE_PIXELS:
        raise ExtractionLimitError("Image dimensions exceed safe extraction limits")


def check_archive(source: bytes | str) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(source) if isinstance(source, bytes) else source) as archive:
            entries = archive.infolist()
            if len(entries) > 4096 or sum(item.file_size for item in entries) > 256 * 1024**2:
                raise ExtractionLimitError("Document archive exceeds extraction limits")
            for item in entries:
                if item.file_size > 32 * 1024**2 or item.file_size / max(1, item.compress_size) > 200:
                    raise ExtractionLimitError("Unsafe document archive compression ratio or member size")
                if ".." in item.filename.replace("\\", "/").split("/") or item.filename.startswith(("/", "\\")):
                    raise ExtractionLimitError("Unsafe document archive path")
    except zipfile.BadZipFile as exc:
        raise ExtractionLimitError("Invalid document archive") from exc


@contextmanager
def ocr_slot():
    # One OCR process across API workers, not one budget per worker. Timeout
    # exceeds the bounded Tesseract invocation plus image preparation only.
    store = _get_redis_client()
    lock = store.lock("extraction:ocr:process", timeout=60, blocking_timeout=2) if store else None
    acquired = False
    if get_settings().redis_required and lock is None:
        raise ExtractionLimitError("OCR capacity service temporarily unavailable")
    try:
        if lock:
            acquired = lock.acquire()
            if not acquired:
                raise ExtractionLimitError("OCR is busy; retry after the current extraction finishes")
        os.environ.setdefault("OMP_THREAD_LIMIT", "1")
        yield
    finally:
        if acquired:
            lock.release()
