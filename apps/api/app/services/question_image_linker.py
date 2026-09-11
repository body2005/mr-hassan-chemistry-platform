"""Conservative question-to-image linking for extracted assessment content."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_IMAGE_REFERENCE_RE = re.compile(
    r"(?:الصورة|الشكل|الرسم|المخطط|الجدول\s+التالي|فيما\s+يلي|المبين|الموضح|الشكل\s+التالي|figure|image|diagram|chart|shown\s+below|following\s+figure)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ImageMatch:
    asset_id: str
    relation_type: str
    confidence: float
    evidence: dict


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[\w\u0621-\u064A]+", text)
        if len(token) >= 3
    }


def select_question_images(
    question_text: str,
    assets: Iterable[object],
    *,
    explicit_asset_ids: Iterable[str] = (),
) -> list[ImageMatch]:
    """Return only images defensibly associated with the question.

    The parser has page-level provenance but not reliable visual coordinates for
    every file format. Therefore a page image is *not* treated as a question
    image merely because it shares a page: an explicit reference, a parser media
    link, or strong vocabulary/OCR overlap is required.
    """
    explicit = {str(value) for value in explicit_asset_ids}
    question_tokens = _tokens(question_text)
    references_image = bool(_IMAGE_REFERENCE_RE.search(question_text))
    candidates = list(assets)
    matches: list[ImageMatch] = []
    for asset in candidates:
        asset_id = str(getattr(asset, "id", ""))
        if not asset_id:
            continue
        metadata = getattr(asset, "metadata_json", None) or {}
        visual_text = " ".join(
            str(part or "") for part in (
                getattr(asset, "caption", None),
                getattr(asset, "surrounding_text", None),
                metadata.get("ocr_text"),
                (metadata.get("vision_analysis") or {}).get("description"),
                " ".join((metadata.get("vision_analysis") or {}).get("entities") or []),
            )
        )
        overlap = question_tokens & _tokens(visual_text)
        if asset_id in explicit:
            matches.append(ImageMatch(asset_id, "explicit_reference", 1.0, {"method": "parser_media_id"}))
        elif references_image and len(candidates) == 1:
            matches.append(ImageMatch(asset_id, "visual_context", 0.84, {"method": "single_page_image_and_question_reference"}))
        elif references_image and len(overlap) >= 2:
            matches.append(ImageMatch(asset_id, "textual_match", 0.8, {"method": "question_image_reference_and_overlap", "matched_terms": sorted(overlap)}))
        elif len(overlap) >= 3:
            matches.append(ImageMatch(asset_id, "textual_match", 0.72, {"method": "strong_ocr_caption_overlap", "matched_terms": sorted(overlap)}))
    return sorted(matches, key=lambda item: (-item.confidence, item.asset_id))
