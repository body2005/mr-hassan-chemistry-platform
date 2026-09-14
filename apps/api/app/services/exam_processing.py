from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.knowledge_center import (
    AssessmentQuestion,
    AssessmentSource,
    KnowledgeQuestionRecord,
    KnowledgeSource,
    SourceRole,
)
from app.services.knowledge_retriever import retrieve_lesson_knowledge

QUESTION_BOUNDARY_RE = re.compile(
    r"(?m)(?=^\s*(?:س(?:ؤال)?\s*)?(?:Q(?:uestion)?\s*)?\(?\d{1,3}\)?\s*[\.\-\)](?!\d)|\n\s*(?:Section|القسم|الجزء)\s+[A-Zأ-ي]|(?:^\s*(?:(?:\)?درجات?\s*\d+\(?\s*:\s*)?(?:السؤال|سؤال)\s+(?:الأول|الاول|الثاني|الثانى|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر))))",
    re.IGNORECASE,
)

ARABIC_ORDINAL_MAP = {
    "الأول": "1", "الاول": "1",
    "الثاني": "2", "الثانى": "2",
    "الثالث": "3",
    "الرابع": "4",
    "الخامس": "5",
    "السادس": "6",
    "السابع": "7",
    "الثامن": "8",
    "التاسع": "9",
    "العاشر": "10",
}


@dataclass
class AnswerResolution:
    answer: str | None
    source: str | None
    status: str
    provenance: dict[str, Any]


def split_assessment_question_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n")
    starts = [m.start() for m in QUESTION_BOUNDARY_RE.finditer(normalized)]
    if not starts:
        return [normalized.strip()] if normalized.strip() else []
    blocks: list[str] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(normalized)
        block = normalized[start:end].strip()
        if block:
            blocks.append(block)
    return blocks


def _extract_question_number(text: str) -> str | None:
    normalized = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    match = re.search(
        r"(?:^|\n)\s*(?:س(?:ؤال)?\s*)?(?:Q(?:uestion)?\s*)?\(?(\d{1,3})\)?[\.\-\:\)]?(?!\d)",
        normalized,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    ordinal_match = re.search(
        r"(?:السؤال|سؤال)\s+(الأول|الاول|الثاني|الثانى|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر)\b",
        text,
    )
    if ordinal_match:
        return ARABIC_ORDINAL_MAP.get(ordinal_match.group(1))
    return None


def _answer_key_for_source(db: Session, answer_key_source_id: uuid.UUID | None) -> dict[str, str]:
    if not answer_key_source_id:
        return {}
    source = db.get(KnowledgeSource, answer_key_source_id)
    if not source or source.source_role != SourceRole.ANSWER_KEY:
        return {}
    records = db.scalars(
        select(KnowledgeQuestionRecord).where(
            KnowledgeQuestionRecord.source_id == answer_key_source_id
        )
    ).all()
    answers: dict[str, str] = {}
    for record in records:
        qn = _extract_question_number(record.raw_text or record.question_text or "")
        if qn and record.correct_answer:
            answers[qn] = record.correct_answer
    if answers:
        return answers
    if not source.storage_path:
        return {}
    try:
        with open(source.storage_path, "rb") as handle:
            text = handle.read().decode("utf-8", errors="ignore")
    except Exception:
        return {}
    answer_pair_re = r"(?:س|q|question)?\s*\(?(\d{1,3})\)?\s*[\:\.\-\)]\s*([^\n\r;،,]{1,200})"
    for qn, answer in re.findall(answer_pair_re, text, re.IGNORECASE):
        answer = answer.strip(" ()[].:-")
        if answer:
            answers[qn] = answer
    return answers


def _resolve_answer(
    db: Session,
    question: KnowledgeQuestionRecord,
    answer_keys: dict[str, str],
) -> AnswerResolution:
    if question.correct_answer:
        qn = _extract_question_number(question.raw_text or question.question_text)
        key_answer = answer_keys.get(qn or "")
        if key_answer and key_answer.strip().lower() != question.correct_answer.strip().lower():
            return AnswerResolution(
                question.correct_answer,
                "conflicting_sources",
                "needs_review",
                {
                    "explicit": question.correct_answer,
                    "answer_key": key_answer,
                    "question_number": qn,
                },
            )
        return AnswerResolution(
            question.correct_answer,
            "explicit_in_assessment",
            "resolved",
            {"source_question_record_id": str(question.id), "page_number": question.page_number},
        )

    qn = _extract_question_number(question.raw_text or question.question_text)
    if qn and qn in answer_keys:
        return AnswerResolution(
            answer_keys[qn],
            "answer_key",
            "needs_review",
            {"question_number": qn},
        )

    retrieved = retrieve_lesson_knowledge(
        db,
        course_id=question.course_id,
        lesson_id=question.lesson_id,
        query=question.question_text,
        limit=3,
    )
    if retrieved:
        top = retrieved[0]
        return AnswerResolution(
            top.statement,
            "knowledge_center",
            "needs_review",
            {
                "retrieved_unit_id": top.unit_id,
                "citation": top.citation_text,
                "relevance_score": top.relevance_score,
            },
        )
    return AnswerResolution(None, None, "unresolved", {})


def materialize_assessment_questions(
    db: Session,
    source: KnowledgeSource,
    assessment_type: str = "exam",
    answer_key_source_id: uuid.UUID | None = None,
) -> AssessmentSource:
    existing = db.scalar(select(AssessmentSource).where(AssessmentSource.source_id == source.id))
    if existing:
        db.execute(
            delete(AssessmentQuestion).where(AssessmentQuestion.assessment_source_id == existing.id)
        )
        db.delete(existing)
        db.flush()

    assessment = AssessmentSource(
        source_id=source.id,
        assessment_type=assessment_type,
        title=source.filename.rsplit(".", 1)[0],
        total_questions=0,
        answer_key_source_id=answer_key_source_id,
        processing_status="resolving",
        review_status="needs_review",
    )
    db.add(assessment)
    db.flush()

    answer_keys = _answer_key_for_source(db, answer_key_source_id)
    records = db.scalars(
        select(KnowledgeQuestionRecord)
        .where(KnowledgeQuestionRecord.source_id == source.id)
        .order_by(
            KnowledgeQuestionRecord.page_number.asc().nullslast(),
            KnowledgeQuestionRecord.question_order.asc(),
            KnowledgeQuestionRecord.created_at.asc(),
        )
    ).all()

    if not records and source.storage_path:
        import os
        from app.core.storage import get_storage_provider
        storage = get_storage_provider()
        local_path = storage.get_local_path(source.storage_path) if hasattr(storage, "get_local_path") else None
        effective_path = local_path or source.storage_path
        raw_text = ""
        try:
            if os.path.exists(effective_path):
                with open(effective_path, "rb") as fh:
                    raw_text = fh.read().decode("utf-8", errors="ignore")
            else:
                raw_text = b"".join(storage.open_stream(source.storage_path)).decode("utf-8", errors="ignore")
        except Exception:
            raw_text = ""

        blocks = split_assessment_question_blocks(raw_text) if raw_text else []
        for idx, block in enumerate(blocks, 1):
            lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
            if not lines:
                continue
            stem = lines[0]
            raw_options = lines[1:] if len(lines) > 1 else []
            options = []
            for opt in raw_options:
                opt_clean = re.sub(r"^[A-Da-dأ-د\d][\.\-\)]\s*", "", opt).strip()
                options.append({"text": opt_clean or opt})
            q_type = "multiple_choice" if len(options) >= 2 else "essay"
            norm = re.sub(r"\s+", "", stem.lower())
            norm_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
            fingerprint = hashlib.md5(norm.encode("utf-8")).hexdigest()
            db.add(
                AssessmentQuestion(
                    assessment_source_id=assessment.id,
                    course_id=source.course_id,
                    lesson_id=source.lesson_id,
                    outline_node_id=None,
                    question_text=stem,
                    question_type=q_type,
                    difficulty="medium",
                    learning_objective="understanding",
                    topic_concept="assessment",
                    points=1.0,
                    source_kind="extracted_question",
                    correct_answer=None,
                    answer_source=None,
                    answer_status="needs_review",
                    answer_provenance_json={},
                    options_json=options or None,
                    explanation=None,
                    source_pages_json=[1],
                    media_ids_json=[],
                    review_status="needs_review",
                    normalized_hash=norm_hash,
                    semantic_fingerprint=fingerprint,
                    metadata_json={"question_order": idx},
                )
            )
        assessment.total_questions = len(blocks)
        assessment.processing_status = "resolved"
        assessment.review_status = "needs_review"
        db.flush()
        return assessment

    for record in records:
        resolution = _resolve_answer(db, record, answer_keys)
        hierarchy = (record.metadata_json or {}).get("hierarchy") or {}
        topic_concept = hierarchy.get("topic") or hierarchy.get("lesson") or hierarchy.get("unit") or record.question_text[:80] or "assessment"
        norm = re.sub(r"\s+", "", record.question_text.lower())
        norm_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        fingerprint_seed = f"{norm}_{record.correct_answer or ''}".encode()
        fingerprint = hashlib.md5(fingerprint_seed).hexdigest()
        db.add(
            AssessmentQuestion(
                assessment_source_id=assessment.id,
                course_id=record.course_id,
                lesson_id=record.lesson_id,
                outline_node_id=record.outline_node_id,
                question_text=record.question_text,
                question_type=record.question_type,
                difficulty="medium",
                learning_objective="understanding",
                topic_concept=topic_concept[:255],
                points=1.0,
                source_kind="extracted_question",
                correct_answer=resolution.answer,
                answer_source=resolution.source,
                answer_status=resolution.status,
                answer_provenance_json=resolution.provenance,
                options_json=record.options_json,
                explanation=record.explanation,
                source_pages_json=[record.page_number] if record.page_number else [],
                media_ids_json=record.image_asset_ids_json,
                review_status=(
                    "approved"
                    if resolution.status == "resolved" and not record.needs_answer_review
                    else "needs_review"
                ),
                normalized_hash=norm_hash,
                semantic_fingerprint=fingerprint,
                metadata_json={
                    "source_question_record_id": str(record.id),
                    "question_order": record.question_order,
                    "hierarchy": hierarchy,
                    "verified_image_count": len(record.image_asset_ids_json or []),
                },
            )
        )

    assessment.total_questions = len(records)
    assessment.processing_status = "resolved"
    assessment.review_status = (
        "approved"
        if records and all(not r.needs_answer_review and r.correct_answer for r in records)
        else "needs_review"
    )
    db.flush()
    return assessment


def relink_answer_key(
    db: Session, assessment: AssessmentSource, answer_key_source_id: uuid.UUID | None
) -> AssessmentSource:
    source = db.get(KnowledgeSource, assessment.source_id)
    if not source:
        raise LookupError("Assessment source not found")
    assessment_type = assessment.assessment_type
    db.execute(
        delete(AssessmentQuestion).where(AssessmentQuestion.assessment_source_id == assessment.id)
    )
    db.delete(assessment)
    db.flush()
    return materialize_assessment_questions(db, source, assessment_type, answer_key_source_id)


def validate_assessment_question(question: AssessmentQuestion) -> list[str]:
    errors: list[str] = []
    if len(question.question_text.strip()) < 5:
        errors.append("Question text is too short")
    if question.question_type == "multiple_choice" and len(question.options_json or []) < 2:
        errors.append("Multiple choice questions require at least two options")
    if not question.correct_answer:
        errors.append("Correct answer is missing")
    return errors
