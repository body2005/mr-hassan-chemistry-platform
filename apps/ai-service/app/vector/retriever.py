import uuid
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from app.config import get_settings
from app.core.logging import logger
from app.schemas.tutor import CourseChunkInput, PassageCitation


class IndexedChunk:
    def __init__(
        self,
        chunk_id: str,
        course_id: str,
        lesson_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.chunk_id = chunk_id
        self.course_id = course_id
        self.lesson_id = lesson_id
        self.content = content
        self.embedding = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(self.embedding)
        if norm > 0:
            self.embedding = self.embedding / norm
        self.metadata = metadata or {}


class VectorRetriever:
    """
    Vector Retrieval Engine:
    - Stores and indexes course content chunks with dense vector embeddings.
    - Computes cosine similarity rankings.
    - Implements strict relevance gating: rejects passages below similarity_threshold.
    """

    def __init__(self):
        self.settings = get_settings()
        self._chunks_by_course: Dict[str, List[IndexedChunk]] = {}

    def index_chunks(
        self,
        course_id: str,
        chunks: List[CourseChunkInput],
        embeddings: List[List[float]]
    ) -> int:
        if course_id not in self._chunks_by_course:
            self._chunks_by_course[course_id] = []

        indexed_count = 0
        for chunk_input, emb in zip(chunks, embeddings):
            chunk_id = str(uuid.uuid4())
            indexed_chunk = IndexedChunk(
                chunk_id=chunk_id,
                course_id=course_id,
                lesson_id=chunk_input.lesson_id,
                content=chunk_input.content,
                embedding=emb,
                metadata=chunk_input.metadata
            )
            self._chunks_by_course[course_id].append(indexed_chunk)
            indexed_count += 1

        logger.info(f"Indexed {indexed_count} chunks for course '{course_id}'. Total course chunks: {len(self._chunks_by_course[course_id])}")
        return indexed_count

    def search_similar(
        self,
        course_id: str,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[Tuple[IndexedChunk, float]]:
        k = top_k or self.settings.TOP_K_CHUNKS
        threshold = similarity_threshold if similarity_threshold is not None else self.settings.VECTOR_SIMILARITY_THRESHOLD

        course_chunks = self._chunks_by_course.get(course_id, [])
        if not course_chunks:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        scored_chunks: List[Tuple[IndexedChunk, float]] = []
        for chunk in course_chunks:
            # Cosine similarity between normalized vectors
            sim = float(np.dot(q_vec, chunk.embedding))
            if sim >= threshold:
                scored_chunks.append((chunk, round(sim, 4)))

        # Sort descending by similarity
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:k]

    def clear(self, course_id: Optional[str] = None):
        if course_id:
            self._chunks_by_course.pop(course_id, None)
        else:
            self._chunks_by_course.clear()


vector_retriever = VectorRetriever()
