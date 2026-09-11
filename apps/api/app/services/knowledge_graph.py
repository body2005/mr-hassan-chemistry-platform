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


def _link(
    db: Session,
    concept: KnowledgeConcept,
    entity_type: str,
    entity_id: uuid.UUID,
    source_id: uuid.UUID | None,
    confidence: float = 1.0,
    seen_links: set[tuple[uuid.UUID, str, uuid.UUID]] | None = None,
) -> None:
    key = (concept.id, entity_type, entity_id)
    if seen_links is not None:
        if key in seen_links:
            return
        seen_links.add(key)

    for pending in db.new:
        if isinstance(pending, KnowledgeConceptLink) and (pending.concept_id, pending.entity_type, pending.entity_id) == key:
            return

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
    """Build graph links from extracted source entities without adding unsupported facts.
    Optimized with in-memory sets and dictionaries to process thousands of units in seconds.
    """
    units = db.scalars(select(KnowledgeUnitRecord).where(KnowledgeUnitRecord.source_id == source_id)).all()
    if not units:
        return
    course_id = units[0].course_id

    # 1. Preload existing concepts for course into in-memory dictionary
    all_concepts = db.scalars(select(KnowledgeConcept).where(KnowledgeConcept.course_id == course_id)).all()
    concepts_map: dict[str, KnowledgeConcept] = {c.normalized_label: c for c in all_concepts}

    def get_or_create_fast(label: str, description: str | None = None) -> KnowledgeConcept | None:
        label = label.strip()[:300]
        normalized = normalize_concept_label(label)
        if not normalized or len(normalized) < 2:
            return None
        existing = concepts_map.get(normalized)
        if existing:
            if description and not existing.description:
                existing.description = description[:4000]
            return existing
        concept = KnowledgeConcept(
            course_id=course_id,
            label=label,
            normalized_label=normalized,
            description=description[:4000] if description else None,
        )
        db.add(concept)
        concepts_map[normalized] = concept
        return concept

    # 2. Preload existing links for this source
    existing_links_db = db.scalars(
        select(KnowledgeConceptLink).where(KnowledgeConceptLink.source_id == source_id)
    ).all()
    seen_links: set[tuple[uuid.UUID, str, uuid.UUID]] = {
        (l.concept_id, l.entity_type, l.entity_id) for l in existing_links_db
    }

    # Flush any new concepts so their IDs are generated
    db.flush()

    def link_fast(concept: KnowledgeConcept, entity_type: str, entity_id: uuid.UUID, confidence: float = 1.0) -> None:
        if not concept.id:
            db.flush()
        key = (concept.id, entity_type, entity_id)
        if key in seen_links:
            return
        seen_links.add(key)
        db.add(KnowledgeConceptLink(
            concept_id=concept.id,
            entity_type=entity_type,
            entity_id=entity_id,
            source_id=source_id,
            confidence=confidence,
        ))
        concept.source_count += 1

    concepts_by_unit: dict[uuid.UUID, list[KnowledgeConcept]] = defaultdict(list)
    for unit in units:
        concept = get_or_create_fast(unit.concept, unit.statement)
        if concept:
            link_fast(concept, "unit", unit.id, unit.semantic_confidence)
            concepts_by_unit[unit.id].append(concept)

    assets = db.scalars(select(KnowledgeAsset).where(KnowledgeAsset.source_id == source_id)).all()
    for asset in assets:
        analysis = (asset.metadata_json or {}).get("vision_analysis") or {}
        for label in analysis.get("entities", []) + analysis.get("formulas", []):
            concept = get_or_create_fast(str(label))
            if concept:
                link_fast(concept, "asset", asset.id, float(analysis.get("confidence", 0.5)))

    extracted_questions = db.scalars(
        select(KnowledgeQuestionRecord).where(KnowledgeQuestionRecord.source_id == source_id)
    ).all()
    for question in extracted_questions:
        hierarchy = (question.metadata_json or {}).get("hierarchy") or {}
        label = hierarchy.get("topic") or hierarchy.get("lesson") or question.question_text[:120]
        concept = get_or_create_fast(str(label))
        if concept:
            link_fast(concept, "extracted_question", question.id, 0.85)

    questions = db.scalars(
        select(AssessmentQuestion)
        .join(AssessmentSource, AssessmentQuestion.assessment_source_id == AssessmentSource.id)
        .where(AssessmentSource.source_id == source_id)
    ).all()
    for question in questions:
        tokens = normalize_concept_label(question.topic_concept or question.question_text[:120])
        if tokens:
            concept = get_or_create_fast(question.topic_concept or question.question_text[:120])
            if concept:
                link_fast(concept, "question", question.id, 0.8)

    # 3. Preload existing relations for this source
    existing_relations_db = db.scalars(
        select(KnowledgeConceptRelation).where(KnowledgeConceptRelation.source_id == source_id)
    ).all()
    seen_relations: set[tuple[uuid.UUID, uuid.UUID, str]] = {
        (r.from_concept_id, r.to_concept_id, r.relation_type) for r in existing_relations_db
    }

    # Ensure all newly added concepts have IDs before creating relations
    db.flush()

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
            target = get_or_create_fast(target_label)
            if not target or not target.id:
                continue
            for source_concept in source_concepts:
                if not source_concept.id or source_concept.id == target.id:
                    continue
                rel_key = (source_concept.id, target.id, relation_type)
                if rel_key in seen_relations:
                    continue
                seen_relations.add(rel_key)

                db.add(KnowledgeConceptRelation(
                    from_concept_id=source_concept.id,
                    to_concept_id=target.id,
                    source_id=source_id,
                    relation_type=relation_type,
                    confidence=unit.semantic_confidence,
                    evidence_unit_ids_json=[str(unit.id)],
                ))
    db.flush()
