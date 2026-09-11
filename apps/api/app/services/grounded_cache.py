"""Version-aware exact and semantic cache for grounded answers."""
from __future__ import annotations

import hashlib
import threading
import time
import uuid
from dataclasses import dataclass

from app.services.embedding_provider import cosine_similarity, get_embedding_provider


@dataclass
class _Entry:
    key: str
    course_id: uuid.UUID
    version_token: str
    vector: list[float]
    value: tuple[str, bool, bool, list[dict]]
    expires_at: float


_lock = threading.Lock()
_entries: list[_Entry] = []


def _key(course_id: uuid.UUID, version_token: str, query: str) -> str:
    normalized = " ".join(query.lower().split())
    return hashlib.sha256(f"{course_id}:{version_token}:{normalized}".encode()).hexdigest()


def get_cached(course_id: uuid.UUID, version_token: str, query: str) -> tuple[str, bool, bool, list[dict]] | None:
    key = _key(course_id, version_token, query)
    now = time.time()
    with _lock:
        _entries[:] = [entry for entry in _entries if entry.expires_at > now]
        for entry in _entries:
            if entry.key == key:
                return entry.value
        try:
            vector = get_embedding_provider().embed_texts([query])[0]
        except Exception:
            return None
        for entry in _entries:
            if entry.course_id == course_id and entry.version_token == version_token and cosine_similarity(vector, entry.vector) >= 0.96:
                return entry.value
    return None


def put_cached(course_id: uuid.UUID, version_token: str, query: str, value: tuple[str, bool, bool, list[dict]]) -> None:
    try:
        vector = get_embedding_provider().embed_texts([query])[0]
    except Exception:
        return
    ttl = float(__import__("os").getenv("GROUNDED_CACHE_TTL_SECONDS", "900"))
    with _lock:
        _entries.append(_Entry(_key(course_id, version_token, query), course_id, version_token, vector, value, time.time() + ttl))
        del _entries[:-500]


def clear_cache() -> None:
    with _lock:
        _entries.clear()
