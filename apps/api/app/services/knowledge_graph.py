"""Evidence-preserving PostgreSQL knowledge graph materialization."""
from __future__ import annotations

import re
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_center import (
    AssessmentQuestion,
    AssessmentSource,
    KnowledgeAsset,
    KnowledgeConcept,
    KnowledgeConceptLink,
    KnowledgeConceptRelation,
    KnowledgeQuestionRecord,
    KnowledgeUnitRecord,
)


def normalize_concept_label(value: str) -> str:
    value = re.sub(r"[\u064B-\u0652\u0640]", "", value.lower().strip())
    value = re.sub(r"[إأآا]", "ا", value)
    value = value.replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"\s+", " ", value)[:300]


def _get_or_create_concept(db: Session, course_id: uuid.UUID, label: str, description: str | None = None) -> KnowledgeConcept | None:
    label = label.strip()[:300]
    normalized = normalize_concept_label(label)
    if not normalized or len(normalized) < 2:
        return None
    concept = db.scalar(
        select(KnowledgeConcept).where(
            KnowledgeConcept.course_id == course_id,
            KnowledgeConcept.normalized_label == normalized,
        )
    )
    if concept:
        if description and not concept.description:
            concept.description = description[:4000]
        return concept
    concept = KnowledgeConcept(
        course_id=course_id,
        label=label,
        normalized_label=normalized,
        description=description[:4000] if description else None,
    )
    db.add(concept)
    db.flush()
    return concept


def _link(db: Session, concept: KnowledgeConcept, entity_type: str, entity_id: uuid.UUID, source_id: uuid.UUID | None, confidence: float = 1.0) -> None:
    existing = db.scalar(
        select(KnowledgeConceptLink).where(
            KnowledgeConceptLink.concept_id == concept.id,
            KnowledgeConceptLink.entity_type == entity_type,
            KnowledgeConceptLink.entity_id == entity_id,
        )
    )
    if not existing:
        db.add(KnowledgeConceptLink(
            concept_id=concept.id, entity_type=entity_type, entity_id=entity_id,
            source_id=source_id, confidence=confidence,
        ))
        concept.source_count += 1


def build_source_knowledge_graph(db: Session, source_id: uuid.UUID) -> None:
    """Build graph links from extracted source entities without adding unsupported facts."""
    units = db.scalars(select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source_id)).all()
    if not units:
        return
    course_id = units[0].course_id
    concepts_by_unit: dict[uuid.UUID, list[KnowledgeConcept]] = defaultdict(list)
    for unit in units:
        concept = _get_or_create_concept(db, course_id, unit.concept, unit.statement)
        if concept:
            _link(db, concept, "unit", unit.id, source_id, unit.semantic_confidence)
            concepts_by_unit[unit.id].append(concept)

    assets = db.scalars(select(KnowledgeAsset).where(KnowledgeAsset.source_id == source_id)).all()
    for asset in assets:
        analysis = (asset.metadata_json or {}).get("vision_analysis") or {}
        for label in analysis.get("entities", []) + analysis.get("formulas", []):
            concept = _get_or_create_concept(db, course_id, str(label))
            if concept:
                _link(db, concept, "asset", asset.id, source_id, float(analysis.get("confidence", 0.5)))

    # Questions embedded in textbook pages are first-class learning evidence,
    # even when the source is not an uploaded assessment bank.
    extracted_questions = db.scalars(
        select(KnowledgeQuestionRecord).where(KnowledgeQuestionRecord.source_id == source_id)
    ).all()
    for question in extracted_questions:
        hierarchy = (question.metadata_json or {}).get("hierarchy") or {}
        label = hierarchy.get("topic") or hierarchy.get("lesson") or question.question_text[:120]
        concept = _get_or_create_concept(db, course_id, str(label))
        if concept:
            _link(db, concept, "extracted_question", question.id, source_id, 0.85)

    questions = db.scalars(
        select(AssessmentQuestion)
        .join(AssessmentSource, AssessmentQuestion.assessment_source_id == AssessmentSource.id)
        .where(AssessmentSource.source_id == source_id)
    ).all()
    for question in questions:
        tokens = normalize_concept_label(question.topic_concept or question.question_text[:120])
        if tokens:
            concept = _get_or_create_concept(db, course_id, question.topic_concept or question.question_text[:120])
            if concept:
                _link(db, concept, "question", question.id, source_id, 0.8)

    # Same-unit mentions are explicit evidence of a relationship, rather than a
    # model guess. Relations are deduplicated by the database constraint.
    for unit in units:
        related_labels = unit.relationships_json or []
        source_concepts = concepts_by_unit.get(unit.id, [])
        if not source_concepts:
            continue
        for relation in related_labels:
            if isinstance(relation, dict):
                target_label = str(relation.get("target") or relation.get("concept") or "")
                relation_type = str(relation.get("type") or "related_to")[:50]
            else:
                target_label, relation_type = str(relation), "related_to"
            target = _get_or_create_concept(db, course_id, target_label)
            if not target:
                continue
            for source_concept in source_concepts:
                if source_concept.id == target.id:
                    continue
                existing = db.scalar(select(KnowledgeConceptRelation).where(
                    KnowledgeConceptRelation.from_concept_id == source_concept.id,
                    KnowledgeConceptRelation.to_concept_id == target.id,
                    KnowledgeConceptRelation.source_id == source_id,
                    KnowledgeConceptRelation.relation_type == relation_type,
                ))
                if not existing:
                    db.add(KnowledgeConceptRelation(
                        from_concept_id=source_concept.id,
                        to_concept_id=target.id,
                        source_id=source_id,
                        relation_type=relation_type,
                        confidence=unit.semantic_confidence,
                        evidence_unit_ids_json=[str(unit.id)],
                    ))
    db.flush()
