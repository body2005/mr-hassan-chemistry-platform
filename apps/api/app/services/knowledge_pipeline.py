from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.course import Course, Lesson
from app.models.platform import AIRefusalLog
from app.models.transcript import KnowledgeChunk, Transcript, TranscriptSegment
from app.services.transcription_provider import TranscriptSegmentData


def normalize_transcript_text(text: str) -> str:
    """Normalize transcript text: whitespace, repetitive punctuation, preserving Arabic & English."""
    if not text:
        return ""
    # Normalize multiple whitespace / tabs / newlines to single space
    cleaned = re.sub(r"\s+", " ", text).strip()
    # Normalize excessive repetitive punctuation
    cleaned = re.sub(r"\.{2,}", "...", cleaned)
    cleaned = re.sub(r"\?{2,}", "?", cleaned)
    cleaned = re.sub(r"!{2,}", "!", cleaned)
    return cleaned


def create_semantic_chunks(
    segments: list[TranscriptSegmentData],
    max_words: int = 100,
    overlap_words: int = 15,
) -> list[dict[str, Any]]:
    """
    Split timestamped segments into semantic chunks respecting segment boundaries and timestamps.
    """
    if not segments:
        return []

    chunks: list[dict[str, Any]] = []
    current_words: list[str] = []
    current_start = segments[0].start_time
    current_end = segments[0].end_time
    seq = 1

    for seg in segments:
        seg_text = normalize_transcript_text(seg.text)
        if not seg_text:
            continue
        seg_words = seg_text.split()

        if len(current_words) + len(seg_words) > max_words and current_words:
            # Finalize current chunk
            chunk_text = " ".join(current_words)
            chunks.append({
                "sequence": seq,
                "start_time": current_start,
                "end_time": current_end,
                "text": chunk_text,
                "metadata_json": {
                    "word_count": len(current_words),
                    "time_range": f"[{int(current_start)//60:02d}:{int(current_start)%60:02d} - {int(current_end)//60:02d}:{int(current_end)%60:02d}]",
                },
            })
            seq += 1
            # Maintain overlap
            overlap = current_words[-overlap_words:] if len(current_words) > overlap_words else []
            current_words = list(overlap) + list(seg_words)
            current_start = seg.start_time
            current_end = seg.end_time
        else:
            if not current_words:
                current_start = seg.start_time
            current_words.extend(seg_words)
            current_end = seg.end_time

    if current_words:
        chunk_text = " ".join(current_words)
        chunks.append({
            "sequence": seq,
            "start_time": current_start,
            "end_time": current_end,
            "text": chunk_text,
            "metadata_json": {
                "word_count": len(current_words),
                "time_range": f"[{int(current_start)//60:02d}:{int(current_start)%60:02d} - {int(current_end)//60:02d}:{int(current_end)%60:02d}]",
            },
        })

    return chunks


def _normalize_ar_token(w: str) -> str:
    """Normalize Arabic orthographic and dialectical phonetic variations for robust ASR matching."""
    w = re.sub(r"[\u064B-\u0652\u0640]", "", w)
    w = re.sub(r"[إأآا]", "ا", w)
    w = re.sub(r"[ة]", "ه", w)
    w = re.sub(r"[ى]", "ي", w)
    w = re.sub(r"[ط]", "ت", w)
    if w.startswith("ال") and len(w) > 3:
        w = w[2:]
    return w


def retrieve_scoped_knowledge(
    db: Session,
    course_id: uuid.UUID,
    lesson_id: uuid.UUID | None = None,
    query: str = "",
    top_k: int = 5,
    min_score: float = 0.0,
    min_overlap: float = 0.0,
) -> list[KnowledgeChunk]:
    """
    Retrieve knowledge chunks strictly scoped by course_id and optional lesson_id.
    Zero cross-course leakage.
    """
    q = db.query(KnowledgeChunk).filter(KnowledgeChunk.course_id == course_id)
    if lesson_id:
        q = q.filter(KnowledgeChunk.lesson_id == lesson_id)

    all_chunks = q.order_by(KnowledgeChunk.sequence).all()
    if not all_chunks:
        return []

    if not query.strip():
        return all_chunks[:top_k]

    # Token-based relevance scoring with stopword awareness & Arabic normalization
    stopwords = {"ما", "هي", "هو", "في", "من", "على", "عن", "إلى", "الى", "الي", "أين", "اين", "كيف", "تم", "هذا", "هذه", "التي", "الذي", "مع", "أو", "او", "كل", "أن", "ان", "لا", "ماذا", "هل", "لأن", "لان", "و", "فيها", "مافيش", "فيش"}
    raw_query_tokens = [_normalize_ar_token(w) for w in re.findall(r"\w+", query.lower())]
    query_tokens = [w for w in raw_query_tokens if w not in stopwords and len(w) > 1]
    if not query_tokens:
        query_tokens = [w for w in raw_query_tokens if len(w) > 1]

    if not query_tokens:
        return all_chunks[:top_k] if min_score <= 0.0 else []

    query_token_set = set(query_tokens)
    scored_chunks: list[tuple[float, KnowledgeChunk]] = []

    for chunk in all_chunks:
        chunk_text_lower = chunk.text.lower()
        chunk_raw = [_normalize_ar_token(w) for w in re.findall(r"\w+", chunk_text_lower)]
        chunk_tokens = set(chunk_raw)
        common = query_token_set.intersection(chunk_tokens)
        if not common:
            continue
        overlap = len(common) / len(query_token_set)
        if overlap < min_overlap:
            continue
        exact_bonus = 2.0 if query.lower().strip() in chunk_text_lower else 0.0
        score = (len(common) / (math.sqrt(len(query_token_set)) + 0.1)) + exact_bonus
        if score > min_score:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [chunk for score, chunk in scored_chunks[:top_k]]


def generate_grounded_answer(
    db: Session,
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    student_id: uuid.UUID,
    question: str,
) -> dict[str, Any]:
    """
    Ground student question against lesson transcript chunks.
    Refuses honestly if question cannot be supported by the lesson content.
    """
    chunks = retrieve_scoped_knowledge(
        db, course_id=course_id, lesson_id=lesson_id, query=question, top_k=4, min_score=0.6, min_overlap=0.25
    )
    if not chunks:
        # Check if lesson has any transcript
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        reason = "لا يتوفر نص مفهرس لهذا الدرس حتى الآن." if not lesson or not lesson.transcript_text else "لم يتم العثور على تغطية لهذا السؤال في شرح الدرس."
        # Log refusal for quality audit
        refusal = AIRefusalLog(
            institution_id=None,
            user_id=student_id,
            course_id=course_id,
            question_text=question,
            reason="no_matching_coverage",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(refusal)
        db.commit()
        return {
            "answer": reason + " يُرجى توجيه السؤال حول المفاهيم المشروحة في هذا الفيديو.",
            "is_grounded": False,
            "citations": [],
        }

    from app.services.educational_normalizer import clean_spoken_noise, reconstruct_educational_statement

    # Synthesize grounded answer from the most relevant chunk(s)
    top_chunk = chunks[0]
    cleaned_chunk = clean_spoken_noise(top_chunk.text)
    concept, statement, _ = reconstruct_educational_statement(cleaned_chunk)

    citations = []
    for c in chunks:
        start_min = int(c.start_time) // 60
        start_sec = int(c.start_time) % 60
        end_min = int(c.end_time) // 60
        end_sec = int(c.end_time) % 60
        snippet_clean = clean_spoken_noise(c.text)
        citations.append({
            "chunk_id": str(c.id),
            "start_time": c.start_time,
            "end_time": c.end_time,
            "time_formatted": f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}",
            "text_snippet": snippet_clean[:120] + "...",
        })

    # Grounded response synthesis in formal, clear Arabic
    lead_time = citations[0]["time_formatted"]
    answer_text = (
        f"بناءً على ما ورد في شرح الدرس بالفيديو عند التوقيت [{lead_time}]:\n\n"
        f"{statement}\n\n"
        f"💡 يمكنك النقر على التوقيت أعلاه للانتقال مباشرة إلى المقطع المخصص في مشغل الفيديو."
    )

    return {
        "answer": answer_text,
        "is_grounded": True,
        "citations": citations,
    }


def generate_grounded_summary(
    db: Session,
    lesson_id: uuid.UUID,
) -> dict[str, Any]:
    """Generate a hierarchical structured summary of the lesson based on its knowledge chunks."""
    from app.services.educational_normalizer import clean_spoken_noise, reconstruct_educational_statement

    transcript = db.query(Transcript).filter(Transcript.lesson_id == lesson_id).first()
    if not transcript or not transcript.full_text:
        return {
            "summary": "لا يتوفر نص مفهرس لإنشاء ملخص لهذا الدرس.",
            "key_points": [],
            "sections": [],
        }

    chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.transcript_id == transcript.id).order_by(KnowledgeChunk.sequence).all()
    sections = []
    for c in chunks:
        start_min = int(c.start_time) // 60
        start_sec = int(c.start_time) % 60
        end_min = int(c.end_time) // 60
        end_sec = int(c.end_time) % 60
        cleaned = clean_spoken_noise(c.text)
        _, stmt, _ = reconstruct_educational_statement(cleaned)
        sections.append({
            "time_range": f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}",
            "start_time": c.start_time,
            "end_time": c.end_time,
            "summary_snippet": stmt[:150] + ("..." if len(stmt) > 150 else ""),
        })

    if chunks:
        beg_sample = clean_spoken_noise(chunks[0].text)[:120].strip()
        mid_idx = len(chunks) // 2
        mid_sample = clean_spoken_noise(chunks[mid_idx].text)[:120].strip()
        end_sample = clean_spoken_noise(chunks[-1].text)[:120].strip()
        full_overview = (
            f"ملخص شامل يغطي كامل محاور المحاضرة على مدار {int(transcript.duration_seconds//60)} دقيقة:\n"
            f"• مقدمة ومحاور البداية: {beg_sample}...\n"
            f"• منتصف الدرس والتطبيقات: {mid_sample}...\n"
            f"• ختام الدرس والمفاهيم النهائية: {end_sample}..."
        )
    else:
        full_overview = clean_spoken_noise(transcript.full_text)[:400]

    return {
        "title": "ملخص شرح الدرس والمفاهيم الجوهرية",
        "full_overview": full_overview,
        "total_duration_sec": transcript.duration_seconds,
        "language": transcript.language,
        "sections": sections,
    }
