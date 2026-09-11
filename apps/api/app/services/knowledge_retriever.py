"""
=============================================================================
AI TEACHING KNOWLEDGE CENTER — HYBRID RETRIEVAL & GROUNDED Q&A
=============================================================================
Hybrid retrieval (Semantic + Keyword + Metadata Filters) and Grounded Q&A engine.
Enforces strict cross-course isolation, grounded student answers, source citations,
and honest out-of-scope refusals.
=============================================================================
"""
from __future__ import annotations

import math
import os
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course, Lesson
from app.models.knowledge_center import (
    AssessmentQuestion,
    KnowledgeAsset,
    KnowledgeDocument,
    KnowledgeOutlineNode,
    KnowledgeQueryEvent,
    KnowledgeSource,
    KnowledgeUnitRecord,
)
from app.models.user import User
from app.services.document_parsers import clean_arabic_ocr_text
from app.services.chemistry_normalizer import (
    chemistry_aware_tokenize,
    expand_chemistry_synonyms,
    extract_chemical_formulas,
)
from app.services.grounded_answer import build_grounded_answer
from app.services.embedding_provider import cosine_similarity, get_embedding_provider
from app.services.reranker import rerank
from app.services.vector_store import query_knowledge_vectors
from app.services.grounded_cache import get_cached, put_cached
from app.services.book_outline import related_outline_node_ids


@dataclass
class KnowledgeSearchResult:
    """A retrieved knowledge item with full source citation metadata."""
    unit_id: str
    concept: str
    statement: str
    details: str | None
    knowledge_type: str
    relevance_score: float
    source_filename: str
    source_role: str
    page_number: int | None
    slide_number: int | None
    media_urls: list[str] = field(default_factory=list)
    citation_text: str = ""
    outline_node_id: str | None = None
    outline_title: str | None = None


ARABIC_SEARCH_STOPWORDS: set[str] = {
    "في", "من", "على", "عن", "إلى", "الى", "مع", "أو", "او", "ثم", "حيث", "أن", "ان",
    "هذا", "هذه", "ذلك", "تلك", "التي", "الذي", "الذين", "اللاتي", "ما", "ماذا", "لماذا",
    "كيف", "متى", "أين", "اين", "هل", "كل", "جميع", "بعض", "غير", "بين", "أمام", "خلف",
    "تحت", "فوق", "عند", "لدى", "مثل", "نحو", "قد", "لقد", "كان", "كانت", "يكون", "تكون",
    "هو", "هي", "هم", "هن", "نحن", "أنا", "انت", "أنت", "تعتبر", "يعد", "تعد",
    "وما", "فما", "بما", "وهو", "وهي", "فإن", "فان", "فإنه", "فانه", "فهو", "فهي",
    "به", "بها", "له", "لها", "منه", "منها", "عنه", "عنها", "فيه", "فيها", "عليه", "عليها",
    "كذلك", "أيضا", "ايضا", "حتى", "إذا", "اذا", "وهل", "فهل", "أنه", "انه", "أنها", "انها",
}


def _normalize_search_token(w: str) -> str:
    """Normalizes Arabic/English text for robust keyword matching."""
    w = re.sub(r"[^\w\u0621-\u064A]", "", w.lower())
    w = re.sub(r"[\u064B-\u0652\u0640]", "", w)
    w = re.sub(r"[إأآا]", "ا", w)
    w = re.sub(r"[ة]", "ه", w)
    w = re.sub(r"[ى]", "ي", w)
    return w


def _tokenize_for_search(text: str) -> list[str]:
    """Extracts normalized, non-stopword tokens from Arabic and alphanumeric text."""
    raw = re.findall(r"[\w\u0621-\u064A]+", text.lower())
    return [
        _normalize_search_token(w)
        for w in raw
        if len(_normalize_search_token(w)) >= 2 and _normalize_search_token(w) not in ARABIC_SEARCH_STOPWORDS
    ]


def _get_normalized_search_text(text: str) -> str:
    words = [_normalize_search_token(w) for w in re.findall(r"[\w\u0621-\u064A]+", text.lower())]
    return " ".join(w for w in words if w)


def _compute_relevance(query: str, target_text: str) -> float:
    """Computes keyword/token relevance ratio between query and target text (fallback)."""
    q_tokens = set(_tokenize_for_search(query))
    t_tokens = set(_tokenize_for_search(target_text))
    if not q_tokens or not t_tokens:
        return 0.0
    overlap = q_tokens.intersection(t_tokens)
    return len(overlap) / max(1, len(q_tokens))


def _conflicting_evidence(items: list[KnowledgeSearchResult]) -> list[KnowledgeSearchResult]:
    """Return explicit contradictions only; ambiguity never becomes a guessed answer."""
    by_concept: dict[str, list[KnowledgeSearchResult]] = {}
    for item in items:
        by_concept.setdefault(_get_normalized_search_text(item.concept), []).append(item)
    negation = re.compile(
        r"(?:"
        r"\b(?:not|never|without)\b"
        r"|ليس(?:ت|ا)?|غير|بدون|دون|بلا"
        r"|(?:^|\s)(?:لا|لم|لن)\s+\S"
        r")",
        re.IGNORECASE,
    )
    conflicting: list[KnowledgeSearchResult] = []
    for values in by_concept.values():
        for idx, left in enumerate(values):
            for right in values[idx + 1:]:
                left_negative = bool(negation.search(left.statement))
                right_negative = bool(negation.search(right.statement))
                if left_negative != right_negative:
                    conflicting.extend([left, right])
    return conflicting


def retrieve_lesson_knowledge(
    db: Session,
    course_id: uuid.UUID,
    lesson_id: uuid.UUID | None = None,
    query: str = "",
    limit: int = 6,
    source_id: uuid.UUID | None = None,
    outline_node_id: uuid.UUID | None = None,
    include_visual: bool = True,
    include_prerequisite_lessons: bool = False,
) -> list[KnowledgeSearchResult]:
    """
    Hybrid retrieval query for KnowledgeUnits with strict course isolation.
    Uses Okapi BM25 with IDF weighting, concept boosting, and phrase matching.
    """
    stmt = (
        select(
            KnowledgeUnitRecord.id,
            KnowledgeUnitRecord.concept,
            KnowledgeUnitRecord.statement,
            KnowledgeUnitRecord.details,
            KnowledgeUnitRecord.knowledge_type,
            KnowledgeUnitRecord.page_number,
            KnowledgeUnitRecord.slide_number,
            KnowledgeUnitRecord.source_media_ids_json,
            KnowledgeUnitRecord.embedding_json,
            KnowledgeUnitRecord.outline_node_id,
            KnowledgeSource.filename,
            KnowledgeSource.source_role,
        )
        .join(KnowledgeSource, KnowledgeUnitRecord.source_id == KnowledgeSource.id)
        .where(
            KnowledgeUnitRecord.course_id == course_id,
            KnowledgeSource.status == "INDEXED",
            KnowledgeSource.is_current == True,
            KnowledgeUnitRecord.source_type.in_(["document", "diagram"] if include_visual else ["document"]),
            KnowledgeUnitRecord.needs_review == False,
            KnowledgeUnitRecord.version == KnowledgeSource.version,
        )
    )

    if lesson_id:
        stmt = stmt.where(
            (KnowledgeUnitRecord.lesson_id == lesson_id) | (KnowledgeUnitRecord.lesson_id.is_(None))
        )
    if source_id:
        stmt = stmt.where(KnowledgeUnitRecord.source_id == source_id)
    if outline_node_id:
        outline_ids = related_outline_node_ids(db, outline_node_id) if include_prerequisite_lessons else {outline_node_id}
        stmt = stmt.where(KnowledgeUnitRecord.outline_node_id.in_(outline_ids))

    results = db.execute(stmt).all()
    if not results:
        return []

    # If no query provided, return unranked results with default score
    if not query or not query.strip():
        scored_items = []
        for r in results:
            citation_parts = [r.filename]
            if r.page_number:
                citation_parts.append(f"الصفحة {r.page_number}")
            elif r.slide_number:
                citation_parts.append(f"الشريحة {r.slide_number}")
            citation = f"{citation_parts[0]} — {citation_parts[1]}" if len(citation_parts) > 1 else citation_parts[0]
            scored_items.append(
                KnowledgeSearchResult(
                    unit_id=str(r.id),
                    concept=r.concept,
                    statement=r.statement,
                    details=r.details,
                    knowledge_type=r.knowledge_type,
                    relevance_score=0.5,
                    source_filename=r.filename,
                    source_role=r.source_role,
                    page_number=r.page_number,
                    slide_number=r.slide_number,
                    media_urls=[],
                    citation_text=citation,
                    outline_node_id=str(r.outline_node_id) if r.outline_node_id else None,
                )
            )
        return scored_items[:limit]

    # Pre-tokenize all documents once for fast BM25 scoring across aspects
    N = len(results)
    corpus_docs = []
    doc_map = {}
    for r in results:
        concept_tokens = _tokenize_for_search(r.concept or "")
        stmt_tokens = _tokenize_for_search(r.statement or "")
        details_tokens = _tokenize_for_search(r.details or "") if r.details else []
        raw_doc_tokens = concept_tokens + stmt_tokens + details_tokens

        # TF with concept weight boost (2x)
        tf = Counter(stmt_tokens + details_tokens)
        for ct in concept_tokens:
            tf[ct] += 2

        full_text_norm = " ".join(concept_tokens + stmt_tokens + details_tokens)

        doc_dict = {
            "r": r,
            "tf": tf,
            "len": len(raw_doc_tokens),
            "full_text_norm": full_text_norm,
        }
        corpus_docs.append(doc_dict)
        doc_map[str(r.id)] = doc_dict

    avgdl = sum(d["len"] for d in corpus_docs) / max(1, N)
    k1 = 1.5
    b = 0.75

    # Multi-Aspect Query Expansion
    clauses = [c.strip() for c in re.split(r"[،,;\n]+", query) if len(c.strip()) >= 4]
    aspect_queries = [query]
    for c in clauses:
        if c not in aspect_queries and len(c) < len(query):
            aspect_queries.append(c)

    # Key property noun-phrases
    for prop in ["مسحوق أسود", "أخضر فاتح", "أصفر باهت", "حمض مخفف", "حمض مركز"]:
        if prop in query and prop not in aspect_queries:
            aspect_queries.append(prop)

    # Optional remote vector score for full query
    try:
        query_embedding = get_embedding_provider().embed_texts([query])[0]
    except Exception:
        query_embedding = None
    remote_vector_scores = query_knowledge_vectors(query_embedding, limit=max(limit * 4, 20)) if query_embedding else {}

    # Score each aspect
    aspect_rankings: list[tuple[str, list[tuple[float, dict]]]] = []
    rrf_scores: Counter[str] = Counter()

    for asp in aspect_queries:
        asp_tokens = _tokenize_for_search(asp)
        if not asp_tokens:
            continue
        asp_tf = Counter(asp_tokens)
        asp_formulas = {f.normalized.lower() for f in extract_chemical_formulas(asp)}
        asp_synonyms = expand_chemistry_synonyms(asp)
        for syn in asp_synonyms:
            for st in _tokenize_for_search(syn):
                if st not in asp_tf:
                    asp_tf[st] = 1

        asp_terms_set = set(asp_tf.keys())
        raw_words = [_normalize_search_token(w) for w in re.findall(r"[\w\u0621-\u064A]+", asp.lower())]
        raw_words = [w for w in raw_words if w and w not in ARABIC_SEARCH_STOPWORDS]
        asp_bigrams = [f"{raw_words[i]} {raw_words[i+1]}" for i in range(len(raw_words) - 1)]

        asp_doc_freqs: Counter[str] = Counter()
        for doc in corpus_docs:
            for t in asp_terms_set.intersection(doc["tf"].keys()):
                asp_doc_freqs[t] += 1

        is_def_asp = bool(re.search(r"\b(ما هو|ما هي|ما المقصود|عرف|مفهوم)\b", asp))

        asp_scored = []
        for doc in corpus_docs:
            doc_len = doc["len"]
            doc_tf = doc["tf"]

            bm25_score = 0.0
            for q_term, q_count in asp_tf.items():
                if q_term not in doc_tf:
                    continue
                df = asp_doc_freqs.get(q_term, 0)
                idf = math.log(1.0 + (N - df + 0.5) / (df + 0.5))
                f = doc_tf[q_term]
                num = f * (k1 + 1.0)
                denom = f + k1 * (1.0 - b + b * (doc_len / avgdl))
                bm25_score += idf * (num / denom)

            if asp_formulas:
                norm_text = doc["full_text_norm"]
                matched_formulas = {f for f in asp_formulas if f in doc_tf or f" {f} " in f" {norm_text} "}
                if matched_formulas:
                    bm25_score += 3.5 * len(matched_formulas)

            for syn in asp_synonyms:
                if syn.lower() in doc["full_text_norm"]:
                    bm25_score += 2.0

            if bm25_score > 0.0:
                for bg in asp_bigrams:
                    if bg in doc["full_text_norm"]:
                        bm25_score += 2.5
                if is_def_asp and (doc["r"].knowledge_type == "definition" or "تعريف" in (doc["r"].concept or "")):
                    bm25_score += 3.0

            if bm25_score > 0.0:
                asp_scored.append((bm25_score, doc))

        asp_scored.sort(key=lambda x: x[0], reverse=True)
        aspect_rankings.append((asp, asp_scored[:30]))
        for rank, (score, doc) in enumerate(asp_scored[:30], 1):
            doc_id_str = str(doc["r"].id)
            rrf_scores[doc_id_str] += 1.0 / (60.0 + rank)

    # Diversity bonus: top 2 candidates from each distinct aspect receive guaranteed inclusion bonus
    for asp, top_candidates in aspect_rankings:
        for _, doc in top_candidates[:2]:
            doc_id_str = str(doc["r"].id)
            rrf_scores[doc_id_str] += 0.05

    # Merge BM25 + RRF + Vector scores
    scored_items: list[tuple[KnowledgeSearchResult, Any]] = []
    ranked_doc_ids = sorted(rrf_scores.keys(), key=lambda d: rrf_scores[d], reverse=True)
    candidate_doc_ids = ranked_doc_ids[:max(limit * 3, 30)]

    for doc_id in candidate_doc_ids:
        doc = doc_map[doc_id]
        r = doc["r"]
        rrf = rrf_scores[doc_id]
        semantic_score = remote_vector_scores.get(doc_id, 0.0) if remote_vector_scores else (
            cosine_similarity(query_embedding, r.embedding_json) if query_embedding else 0.0
        )
        combined_score = (rrf * 100.0) + max(0.0, semantic_score) * 4.0

        citation_parts = [r.filename]
        if r.page_number:
            citation_parts.append(f"الصفحة {r.page_number}")
        elif r.slide_number:
            citation_parts.append(f"الشريحة {r.slide_number}")
        citation = f"{citation_parts[0]} — {citation_parts[1]}" if len(citation_parts) > 1 else citation_parts[0]

        item = KnowledgeSearchResult(
            unit_id=str(r.id),
            concept=r.concept,
            statement=r.statement,
            details=r.details,
            knowledge_type=r.knowledge_type,
            relevance_score=round(combined_score, 4),
            source_filename=r.filename,
            source_role=r.source_role,
            page_number=r.page_number,
            slide_number=r.slide_number,
            media_urls=[],
            citation_text=citation,
            outline_node_id=str(r.outline_node_id) if r.outline_node_id else None,
            outline_title=None,
        )
        scored_items.append((item, r.source_media_ids_json))

    # Optional cross-encoder reranker
    candidates = sorted(scored_items, key=lambda x: x[0].relevance_score, reverse=True)
    rerank_count = min(len(candidates), int(os.getenv("RERANKER_CANDIDATES", "20")))
    rerank_scores = rerank(query, [
        f"{item.concept}\n{item.statement}\n{item.details or ''}"
        for item, _ in candidates[:rerank_count]
    ])
    if rerank_scores:
        for (item, _), score in zip(candidates[:rerank_count], rerank_scores, strict=True):
            item.relevance_score = round(item.relevance_score + max(0.0, score) * 3.0, 4)
        scored_items = candidates

    scored_items.sort(key=lambda x: x[0].relevance_score, reverse=True)
    top_entries = scored_items[:limit]

    # Resolve outline titles and media asset URLs only for top items
    final_items: list[KnowledgeSearchResult] = []
    outline_cache: dict[uuid.UUID, str] = {}
    for item, media_ids in top_entries:
        if item.outline_node_id:
            try:
                node_uuid = uuid.UUID(item.outline_node_id)
                if node_uuid not in outline_cache:
                    title_res = db.scalar(select(KnowledgeOutlineNode.title).where(KnowledgeOutlineNode.id == node_uuid))
                    outline_cache[node_uuid] = title_res or ""
                if outline_cache[node_uuid]:
                    item.outline_title = outline_cache[node_uuid]
                    item.citation_text += f" — {outline_cache[node_uuid]}"
            except Exception:
                pass

        if media_ids:
            for m_id in media_ids:
                try:
                    asset = db.scalar(select(KnowledgeAsset).where(KnowledgeAsset.id == uuid.UUID(m_id)))
                    if asset and asset.storage_path:
                        item.media_urls.append(f"/api/v1/knowledge-center/assets/{asset.id}/view")
                except Exception:
                    pass
        final_items.append(item)

    return final_items


def check_grounding_and_answer(
    db: Session,
    user: User,
    course_id: uuid.UUID,
    message: str,
    lesson_id: uuid.UUID | None = None,
) -> tuple[str, bool, bool, list[dict[str, Any]]]:
    """
    Grounded Student Q&A logic.
    Returns: (answer_text, is_grounded, is_refusal, citations)
    """
    clean_msg = message.strip()
    if not clean_msg:
        return ("يرجى إدخال السؤال المطلوب.", False, False, [])

    version_token = "|".join(
        f"{source.id}:{source.version}"
        for source in db.scalars(
            select(KnowledgeSource)
            .where(KnowledgeSource.course_id == course_id, KnowledgeSource.status == "INDEXED")
            .where(KnowledgeSource.is_current == True)
            .order_by(KnowledgeSource.id)
        ).all()
    )
    if cached := get_cached(course_id, version_token, clean_msg):
        return cached

    # Greetings check
    if any(w in clean_msg.lower() for w in ["مرحب", "اهلا", "أهلا", "سلام", "hello", "hi", "ازيك"]):
        return (
            f"أهلاً بك يا {user.display_name or user.username}.\n"
            "أنا المساعد التعليمي الذكي المصمم لمساعدتك في هذا المقرر.\n"
            "يمكنك سؤالي عن أي مفهوم، تعريف، أو مسألة مشروحة في مذكرات ومصادر الدرس وسأجيبك منها مباشرة مع ذكر المصدر والصفحة.",
            True,
            False,
            [],
        )

    # Retrieve matching Knowledge Units from teacher sources
    retrieved = retrieve_lesson_knowledge(db, course_id, lesson_id, clean_msg, limit=14)
    conflicts = _conflicting_evidence(retrieved)
    if conflicts:
        answer = (
            "توجد أدلة متعارضة في مصادر المقرر حول هذه المعلومة؛ لذلك لن أختار إجابة عشوائية. يرجى مراجعة المعلم أو تحديد الإصدار المقصود.",
            False,
            True,
            [
                {"unit_id": item.unit_id, "filename": item.source_filename, "page_number": item.page_number,
                 "slide_number": item.slide_number, "citation": item.citation_text, "snippet": item.statement}
                for item in conflicts
            ],
        )
    else:
        answer = build_grounded_answer(clean_msg, retrieved)
    if answer[1] and not answer[2] and len(answer[0]) > 80:
        put_cached(course_id, version_token, clean_msg, answer)
    db.add(KnowledgeQueryEvent(
        institution_id=getattr(user, "institution_id", None) if user else None,
        user_id=getattr(user, "id", None) if user else None,
        course_id=course_id,
        lesson_id=lesson_id,
        outline_node_id=(uuid.UUID(retrieved[0].outline_node_id) if retrieved and retrieved[0].outline_node_id else None),
        query_text=clean_msg[:20_000],
        outcome="supported" if answer[1] else ("not_found" if answer[2] else "partial"),
        result_count=len(retrieved),
        confidence=max((item.relevance_score for item in retrieved), default=0.0),
    ))
    db.flush()
    return answer


def search_knowledge_base(
    db: Session,
    course_id: uuid.UUID,
    query: str,
    limit: int = 10,
    include_assessment_answers: bool = False,
    source_id: uuid.UUID | None = None,
    outline_node_id: uuid.UUID | None = None,
    include_prerequisite_lessons: bool = False,
) -> dict[str, Any]:
    """Search knowledge units, documents, assets, and assessment questions across a course."""
    units = retrieve_lesson_knowledge(
        db, course_id, query=query, limit=limit,
        source_id=source_id, outline_node_id=outline_node_id,
        include_prerequisite_lessons=include_prerequisite_lessons,
    )
    
    # Search Assessment Questions
    questions_stmt = select(AssessmentQuestion).where(
        AssessmentQuestion.course_id == course_id,
        AssessmentQuestion.question_text.icontains(query),
    ).limit(5)
    matched_questions = db.scalars(questions_stmt).all()

    return {
        "query": query,
        "knowledge_units": [
            {
                "unit_id": u.unit_id,
                "concept": u.concept,
                "statement": u.statement,
                "citation": u.citation_text,
                "relevance": u.relevance_score,
                "outline_node_id": u.outline_node_id,
                "outline_title": u.outline_title,
            }
            for u in units
        ],
        "previous_questions": [
            {
                "id": str(q.id),
                "question_text": q.question_text,
                "question_type": q.question_type,
                "topic": q.topic_concept,
                "correct_answer": q.correct_answer if include_assessment_answers else None,
                "answer_status": q.answer_status,
                "review_status": q.review_status,
            }
            for q in matched_questions
        ],
    }
