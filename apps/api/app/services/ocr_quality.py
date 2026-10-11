"""Bounded raster OCR with conservative, geometry-aligned script recovery.

No dictionaries of questions/answers or fixture text. Scientific tokens and
numbers are never replaced. All consumers must still mark OCR for review.
"""
import re
import time
from collections import OrderedDict

import pytesseract
from app.services.extraction_limits import ExtractionLimitError, OCR_TIMEOUT_SECONDS


def tokens(data):
    return [{key: data[key][i] for key in ("text", "conf", "left", "top", "width", "height", "block_num", "par_num", "line_num")}
            for i, text in enumerate(data["text"]) if text.strip()]


def protected(text):
    return bool(re.search(r"[0-9٠-٩₀-₉⁰-⁹=+−/*^%Ω]", text)
                or re.fullmatch(r"(?:[A-Z][a-z]?)+|[A-Za-z]{1,2}", text))


def overlap(a, b):
    width = max(0, min(a["left"] + a["width"], b["left"] + b["width"]) - max(a["left"], b["left"]))
    height = max(0, min(a["top"] + a["height"], b["top"] + b["height"]) - max(a["top"], b["top"]))
    common = width * height
    return common / max(1, a["width"] * a["height"] + b["width"] * b["height"] - common)


def recover_scripts(base, alternative):
    for word in base:
        text = word["text"].strip("\u200e\u200f")
        if not re.fullmatch(r"[A-Za-z]{3,}", text) or protected(text) or float(word["conf"]) >= 80:
            continue
        matches = [other for other in alternative if re.fullmatch(r"[\u0621-\u064a\u064b-\u065f]+", other["text"])
                   and float(other["conf"]) >= 85 and float(other["conf"]) >= float(word["conf"]) + 10
                   and overlap(word, other) >= .7]
        if len(matches) == 1:
            word["text"] = matches[0]["text"]
    return base


def restore_placeholders(base, alternative):
    """Restore only dotted blanks actually recognized in the same image.

    Never substitute a word, value, formula, or answer. Dots with no matching
    word are retained and later attached to their physical text baseline.
    """
    for source in alternative:
        if not re.fullmatch(r'\.{3,}', source['text']):
            continue
        matches = [word for word in base if overlap(word, source) >= .4]
        if not matches:
            base.append(dict(source))
        elif len(matches) == 1:
            word = matches[0]
            if re.fullmatch(r'\.{3,}[\u0621-\u065f]?', word['text']) and float(word['conf']) < 40:
                word['text'] = source['text']
    return base


def assemble_lines(words):
    groups = OrderedDict()
    for word in words:
        key = (word['block_num'], word['par_num'], word['line_num'])
        groups.setdefault(key, []).append(word)
    # OCR may put a dotted answer space in a paragraph of its own. Attach
    # only pure dotted groups to one unambiguous overlapping Arabic baseline.
    for key, symbols in list(groups.items()):
        if not all(re.fullmatch(r'\.{3,}', word['text']) for word in symbols):
            continue
        top = min(word['top'] for word in symbols)
        bottom = max(word['top'] + word['height'] for word in symbols)
        candidates = []
        for other_key, line in groups.items():
            if key == other_key or not any(re.search(r'[\u0621-\u064a]', w['text']) for w in line):
                continue
            line_top = min(w['top'] for w in line)
            line_bottom = max(w['top'] + w['height'] for w in line)
            if min(bottom, line_bottom) - max(top, line_top) >= min(bottom-top, line_bottom-line_top) * .5:
                candidates.append(other_key)
        if len(candidates) == 1:
            target = groups[candidates[0]]
            for symbol in symbols:
                # Retain existing word ordering, including embedded science.
                position = next((i for i, word in enumerate(target) if word['left'] < symbol['left']), len(target))
                target.insert(position, symbol)
            del groups[key]
    return '\n'.join(' '.join(word['text'] for word in line) for line in groups.values())


def recognize(image, lang="ara+eng"):
    deadline = time.monotonic() + OCR_TIMEOUT_SECONDS
    data = pytesseract.image_to_data(image, lang=lang, config="--psm 3", timeout=OCR_TIMEOUT_SECONDS,
                                    output_type=pytesseract.Output.DICT)
    words = tokens(data)
    if len(words) > 5000:
        raise ExtractionLimitError("OCR word count exceeds bounded processing limits")
    all_text = " ".join(w["text"] for w in words)
    arabic = len(re.findall(r"[\u0621-\u064a]", all_text))
    latin = len(re.findall(r"[A-Za-z]", all_text))
    if "ara" in lang and "eng" in lang and arabic > latin * 2 and any(
        re.fullmatch(r"[A-Za-z]{3,}", w["text"].strip("\u200e\u200f"))
        and not protected(w["text"].strip("\u200e\u200f")) and float(w["conf"]) < 80 for w in words
    ):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ExtractionLimitError("OCR time budget exhausted")
        alternative = tokens(pytesseract.image_to_data(image, lang="ara", config="--psm 3", timeout=remaining,
                                                      output_type=pytesseract.Output.DICT))
        if len(alternative) > 5000:
            raise ExtractionLimitError("OCR word count exceeds bounded processing limits")
        words = recover_scripts(words, alternative)
    if 'ara' in lang and arabic > latin * 2:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ExtractionLimitError('OCR time budget exhausted')
        alternate = tokens(pytesseract.image_to_data(image, lang=lang, config='--psm 6', timeout=remaining,
                                                    output_type=pytesseract.Output.DICT))
        if len(alternate) > 5000:
            raise ExtractionLimitError('OCR word count exceeds bounded processing limits')
        words = restore_placeholders(words, alternate)
    return assemble_lines(words)
