"""Treat uploaded material as data, never as system instructions."""
from __future__ import annotations

import re


_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(ignore|disregard|forget)\b.{0,60}\b(previous|above|system|instructions?)\b",
        r"\b(system prompt|developer message|jailbreak|do not follow)\b",
        r"(?:تجاهل|انس|اهمل).{0,80}(?:التعليمات|الأوامر|السابقة|النظام)",
        r"(?:تعليمات النظام|رسالة المطور|اكسر الحماية)",
    )
]


def sanitize_retrieval_text(text: str) -> tuple[str, int]:
    """Remove instruction-like lines from indexed content while preserving raw source storage."""
    if not text:
        return "", 0
    kept: list[str] = []
    rejected = 0
    for line in text.splitlines() or [text]:
        if any(pattern.search(line) for pattern in _INJECTION_PATTERNS):
            rejected += 1
            continue
        kept.append(line)
    return "\n".join(kept).strip(), rejected
