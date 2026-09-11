"""Optional Qdrant backend; local JSON embeddings remain a zero-config fallback."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Iterable


def _request(method: str, path: str, payload: dict | None = None) -> dict | None:
    base_url = os.getenv("QDRANT_URL", "").rstrip("/")
    if not base_url:
        return None
    headers = {"Content-Type": "application/json"}
    if api_key := os.getenv("QDRANT_API_KEY", ""):
        headers["api-key"] = api_key
    request = urllib.request.Request(
        f"{base_url}{path}", data=json.dumps(payload).encode() if payload else None,
        headers=headers, method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "10"))) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def upsert_knowledge_vectors(items: Iterable[tuple[str, list[float], dict]]) -> bool:
    points = [
        {"id": item_id, "vector": vector, "payload": payload}
        for item_id, vector, payload in items if vector
    ]
    if not points or not os.getenv("QDRANT_URL", ""):
        return False
    collection = os.getenv("QDRANT_COLLECTION", "knowledge_units")
    dimensions = len(points[0]["vector"])
    _request("PUT", f"/collections/{collection}", {"vectors": {"size": dimensions, "distance": "Cosine"}})
    return _request("PUT", f"/collections/{collection}/points?wait=true", {"points": points}) is not None


def query_knowledge_vectors(vector: list[float], limit: int = 20) -> dict[str, float]:
    if not vector or not os.getenv("QDRANT_URL", ""):
        return {}
    collection = os.getenv("QDRANT_COLLECTION", "knowledge_units")
    response = _request("POST", f"/collections/{collection}/points/query", {
        "query": vector, "limit": limit, "with_payload": False,
    }) or {}
    rows = response.get("result", {}).get("points", response.get("result", []))
    if not isinstance(rows, list):
        return {}
    return {str(row.get("id")): float(row.get("score", 0.0)) for row in rows if row.get("id") is not None}
