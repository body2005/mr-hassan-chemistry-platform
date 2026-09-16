"""Book-outline materialization for source-scoped unit, lesson, and topic metadata."""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_center import KnowledgeLessonRelation, KnowledgeOutlineNode


_UNIT_RE = re.compile(r"\b(?:unit|chapter|part)\b|(?:الوحدة|الباب|الفصل)\b", re.IGNORECASE)
_LESSON_RE = re.compile(r"\b(?:lesson|section)\b|(?:الدرس)\b", re.IGNORECASE)
_TOPIC_RE = re.compile(r"\b(?:topic)\b|(?:الموضوع)\b", re.IGNORECASE)


def _node_kind(title: str, level: int, base_level: int) -> str:
    if _UNIT_RE.search(title):
        return "unit"
    if _LESSON_RE.search(title):
        return "lesson"
    if _TOPIC_RE.search(title):
        return "topic"
    if level <= base_level:
        return "unit"
    if level == base_level + 1:
        return "lesson"
    return "topic"


def _rank(kind: str) -> int:
    return {"book": 0, "unit": 1, "lesson": 2, "topic": 3}[kind]


def materialize_book_outline(
    db: Session,
    *,
    source_id: uuid.UUID,
    course_id: uuid.UUID | None,
    document_title: str,
    total_pages: int,
    hierarchy: list[dict[str, Any]] | None,
) -> list[KnowledgeOutlineNode]:
    """Persist a hierarchy without inventing educational facts from source text."""
    root = KnowledgeOutlineNode(
        source_id=source_id,
        course_id=course_id,
        parent_id=None,
        node_kind="book",
        title=document_title[:300],
        position=0,
        heading_level=0,
        start_page=1,
        end_page=max(1, total_pages),
        metadata_json={"generated_from": "document_title"},
    )
    db.add(root)
    db.flush()
    nodes = [root]

    entries = [item for item in (hierarchy or []) if str(item.get("title") or "").strip()]
    levels = [int(item.get("level") or 1) for item in entries]
    base_level = min(levels) if levels else 1
    current: dict[int, KnowledgeOutlineNode] = {0: root}

    for position, item in enumerate(entries, start=1):
        title = str(item["title"]).strip()
        level = max(1, int(item.get("level") or 1))
        kind = _node_kind(title, level, base_level)
        rank = _rank(kind)
        parent = next((current[r] for r in range(rank - 1, -1, -1) if r in current), root)
        page = item.get("page") or item.get("slide") or 1
        try:
            page_number = max(1, int(page))
        except (TypeError, ValueError):
            page_number = 1
        node = KnowledgeOutlineNode(
            source_id=source_id,
            course_id=course_id,
            parent_id=parent.id,
            node_kind=kind,
            title=title[:300],
            position=position,
            heading_level=level,
            start_page=page_number,
            end_page=max(1, total_pages),
            metadata_json={"source_heading": item},
        )
        db.add(node)
        db.flush()
        nodes.append(node)
        current[rank] = node
        for stale_rank in [r for r in current if r > rank]:
            del current[stale_rank]

    for node in nodes[1:]:
        next_peer = next(
            (
                other for other in nodes[node.position + 1 :]
                if _rank(other.node_kind) <= _rank(node.node_kind)
            ),
            None,
        )
        node.end_page = max(
            node.start_page or 1,
            (next_peer.start_page - 1) if next_peer and next_peer.start_page else total_pages,
        )
    db.flush()
    return nodes


def outline_node_for_page(
    nodes: list[KnowledgeOutlineNode], page_number: int | None
) -> KnowledgeOutlineNode | None:
    """Return the most specific outline node covering a document page or slide."""
    if not nodes:
        return None
    page = page_number or 1
    candidates = [
        node for node in nodes
        if node.node_kind != "book"
        and (node.start_page or 1) <= page <= (node.end_page or page)
    ]
    if not candidates:
        return nodes[0]
    return max(candidates, key=lambda node: (_rank(node.node_kind), node.position))


def materialize_lesson_relations(
    db: Session, *, source_id: uuid.UUID, course_id: uuid.UUID | None, nodes: list[KnowledgeOutlineNode]
) -> None:
    """Create only defensible lesson links from the book's stated sequence/titles."""
    lessons = sorted((node for node in nodes if node.node_kind == "lesson"), key=lambda node: node.position)
    for index, lesson in enumerate(lessons):
        if index:
            previous = lessons[index - 1]
            for relation_type, left, right in (
                ("previous", lesson, previous),
                ("next", previous, lesson),
            ):
                db.add(KnowledgeLessonRelation(
                    source_id=source_id, course_id=course_id,
                    from_outline_node_id=left.id, to_outline_node_id=right.id,
                    relation_type=relation_type, confidence=1.0,
                    evidence_json={"method": "document_order", "positions": [previous.position, lesson.position]},
                ))
            if re.search(r"(?:تابع|استكمال|مراجعة|تطبيق|امتداد|part\s*(?:2|ii)|continuation)", lesson.title, re.IGNORECASE):
                db.add(KnowledgeLessonRelation(
                    source_id=source_id, course_id=course_id,
                    from_outline_node_id=lesson.id, to_outline_node_id=previous.id,
                    relation_type="builds_on", confidence=0.85,
                    evidence_json={"method": "explicit_continuation_title", "previous_title": previous.title},
                ))

    # Same-topic is emitted only when headings have meaningful shared terms;
    # this avoids asserting a prerequisite from mere adjacency.
    def tokens(title: str) -> set[str]:
        return {word.lower() for word in re.findall(r"[\w\u0621-\u064A]+", title) if len(word) >= 4}

    for idx, left in enumerate(lessons):
        left_tokens = tokens(left.title)
        for right in lessons[idx + 1:]:
            shared = left_tokens & tokens(right.title)
            if not shared:
                continue
            db.add(KnowledgeLessonRelation(
                source_id=source_id, course_id=course_id,
                from_outline_node_id=left.id, to_outline_node_id=right.id,
                relation_type="same_topic", confidence=0.7,
                evidence_json={"method": "heading_token_overlap", "shared_terms": sorted(shared)},
            ))
            db.add(KnowledgeLessonRelation(
                source_id=source_id, course_id=course_id,
                from_outline_node_id=right.id, to_outline_node_id=left.id,
                relation_type="same_topic", confidence=0.7,
                evidence_json={"method": "heading_token_overlap", "shared_terms": sorted(shared)},
            ))
    db.flush()


def related_outline_node_ids(
    db: Session, outline_node_id: uuid.UUID, relation_types: tuple[str, ...] = ("previous", "prerequisite", "depends_on", "builds_on")
) -> set[uuid.UUID]:
    """Return the requested lesson and trusted prerequisite/previous relations."""
    rows = db.scalars(
        select(KnowledgeLessonRelation.to_outline_node_id).where(
            KnowledgeLessonRelation.from_outline_node_id == outline_node_id,
            KnowledgeLessonRelation.relation_type.in_(relation_types),
        )
    ).all()
    return {outline_node_id, *rows}
