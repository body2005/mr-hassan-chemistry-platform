from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_l = math.sqrt(sum(a * a for a in left))
    norm_r = math.sqrt(sum(b * b for b in right))
    if norm_l == 0.0 or norm_r == 0.0:
        return 0.0
    return dot / (norm_l * norm_r)


class EmbeddingProvider:
    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        raise NotImplementedError


@dataclass
class LocalHashEmbeddingProvider(EmbeddingProvider):
    dimensions: int = 384

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors


@dataclass
class HttpEmbeddingProvider(EmbeddingProvider):
    endpoint: str
    api_key: str | None = None
    timeout_seconds: float = 10.0
    retries: int = 2

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        payload = json.dumps({"input": list(texts)}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(
                    self.endpoint, data=payload, headers=headers, method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, dict) and "data" in data:
                    return [item["embedding"] for item in data["data"]]
                if isinstance(data, dict) and "embeddings" in data:
                    return data["embeddings"]
                raise ValueError("Embedding response must include data[].embedding or embeddings")
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.25 * (attempt + 1))
        raise RuntimeError(f"Embedding provider failed: {last_error}") from last_error


def get_embedding_provider() -> EmbeddingProvider:
    endpoint = os.getenv("EMBEDDING_ENDPOINT", "").strip()
    if endpoint:
        return HttpEmbeddingProvider(
            endpoint=endpoint,
            api_key=os.getenv("EMBEDDING_API_KEY") or None,
            timeout_seconds=float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "10")),
            retries=int(os.getenv("EMBEDDING_RETRIES", "2")),
        )
    return LocalHashEmbeddingProvider(
        dimensions=int(os.getenv("LOCAL_EMBEDDING_DIMENSIONS", "384"))
    )
