"""One complete-content policy for creation, merged revisions and publication.

This module deliberately has no database dependencies: callers validate before
adding a row or changing an existing mapped object.
"""
from __future__ import annotations

import math
import string


QUESTION_TYPES = {"mcq", "multiple_choice", "true_false", "essay", "short_answer",
                  "fill_in_blank", "ordering", "matching"}


def validate_question_content(question, points: float | None = None) -> None:
    prompt = question.prompt
    if (not isinstance(prompt, str) or not 2 <= len(prompt.strip()) <= 10_000
            or getattr(question, "learning_objective", None) == "محتوى غير مفهرس"):
        raise ValueError("Invalid question content")
    try:
        score = float(question.points if points is None else points)
    except (ValueError, TypeError):
        raise ValueError("Question points must be positive, finite and at most 1000") from None
    if not math.isfinite(score) or not 0 < score <= 1000:
        raise ValueError("Question points must be positive, finite and at most 1000")
    kind = question.question_type
    if not isinstance(kind, str) or kind.strip().lower() not in QUESTION_TYPES:
        raise ValueError("Unsupported question type; review the draft before publication")
    kind = kind.strip().lower()
    answer = question.correct_answer
    if kind not in {"essay", "short_answer"}:
        if (answer is None or (isinstance(answer, (list, dict)) and not answer)
                or (isinstance(answer, str) and not answer.strip())):
            raise ValueError("An automatically graded question requires a correct answer")
    if kind not in {"mcq", "multiple_choice"}:
        return
    options = question.options
    if isinstance(options, list) and len(options) > 26:
        raise ValueError("Multiple-choice questions support at most 26 options (A–Z)")
    if not isinstance(options, list) or not 2 <= len(options) <= 26:
        raise ValueError("Multiple-choice questions require 2–26 options (A–Z)")
    keys, accepted = [], []
    for index, option in enumerate(options):
        if isinstance(option, str) and option.strip():
            key, text = string.ascii_uppercase[index], option.strip()
        elif isinstance(option, dict) and isinstance(option.get("text"), str) and option["text"].strip():
            raw_key = option.get("key")
            key = raw_key.strip().upper() if isinstance(raw_key, str) else ""
            text = option["text"].strip()
            if len(key) != 1 or key not in string.ascii_uppercase:
                raise ValueError("Option keys must be letters A–Z")
        else:
            raise ValueError("Invalid question option")
        keys.append(key)
        accepted.extend([key.casefold(), text.casefold()])
    if len(keys) != len(set(keys)):
        raise ValueError("Option keys must be unique")
    if not isinstance(answer, str) or answer.strip().casefold() not in accepted:
        raise ValueError("Correct answer must identify an available option")
