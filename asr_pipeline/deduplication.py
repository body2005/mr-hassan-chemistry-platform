"""Boundary Overlap Word Stitching and Repetition Deduplicator."""
from __future__ import annotations
import re
from typing import List, Dict, Any

def remove_consecutive_phrase_repetitions(text: str, max_ngram: int = 8, max_repeats: int = 2) -> str:
    """
    Detects and collapses unintended ASR hallucination loops (e.g. 5x identical sentences)
    while preserving natural teacher pedagogical emphasis (e.g. 'ركز معايا ركز معايا').
    """
    words = text.split()
    if len(words) < 6:
        return text

    cleaned = []
    i = 0
    n = len(words)

    while i < n:
        matched = False
        for k in range(max_ngram, 2, -1):
            if i + 2 * k <= n:
                phrase1 = words[i:i+k]
                phrase2 = words[i+k:i+2*k]
                if phrase1 == phrase2:
                    repeats = 2
                    pos = i + 2 * k
                    while pos + k <= n and words[pos:pos+k] == phrase1:
                        repeats += 1
                        pos += k
                    if repeats > max_repeats:
                        cleaned.extend(phrase1)
                        i = pos
                        matched = True
                        break
        if not matched:
            cleaned.append(words[i])
            i += 1

    return " ".join(cleaned)

def stitch_overlapping_transcripts(prev_text: str, next_text: str, overlap_window_words: int = 15) -> str:
    """
    Seamlessly merges two consecutive overlapping transcript segments.
    Finds the longest common word overlap between the end of prev_text and start of next_text.
    """
    if not prev_text.strip():
        return next_text.strip()
    if not next_text.strip():
        return prev_text.strip()

    prev_words = prev_text.strip().split()
    next_words = next_text.strip().split()

    search_tail = prev_words[-overlap_window_words:]
    search_head = next_words[:overlap_window_words]

    best_overlap_len = 0
    for k in range(min(len(search_tail), len(search_head)), 2, -1):
        if search_tail[-k:] == search_head[:k]:
            best_overlap_len = k
            break

    if best_overlap_len > 0:
        merged_words = prev_words + next_words[best_overlap_len:]
    else:
        merged_words = prev_words + next_words

    return " ".join(merged_words)
