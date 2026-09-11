"""Optional cross-encoder reranking; ranking remains deterministic if unavailable."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def rerank(query: str, documents: list[str]) -> list[float] | None:
    endpoint = os.getenv("RERANKER_ENDPOINT", "").strip()
    if not endpoint or not documents:
        return None
    body = json.dumps({"query": query, "documents": documents}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key := os.getenv("RERANKER_API_KEY", "").strip():
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=float(os.getenv("RERANKER_TIMEOUT_SECONDS", "10"))) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        scores = payload.get("scores") or payload.get("results")
        if not isinstance(scores, list) or len(scores) != len(documents):
            return None
        return [float(item.get("score", item)) if isinstance(item, dict) else float(item) for item in scores]
    except (OSError, ValueError, json.JSONDecodeError):
        return None
