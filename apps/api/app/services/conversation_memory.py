"""Small, course-scoped conversation layer used only to rewrite follow-up queries."""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_center import KnowledgeConversationTurn


_FOLLOW_UP_RE = re.compile(r"^(?:ليه|لماذا|ازاي|كيف|وماذا عن|وماذا|why|how|what about)\b", re.IGNORECASE)


def rewrite_followup_query(db: Session, user_id: uuid.UUID, course_id: uuid.UUID, session_id: str, message: str) -> str:
    """Add the immediately previous topic only for short, contextual follow-ups."""
    clean = message.strip()
    if len(clean.split()) > 8 or not _FOLLOW_UP_RE.search(clean):
        return clean
    previous = db.scalar(
        select(KnowledgeConversationTurn)
        .where(
            KnowledgeConversationTurn.user_id == user_id,
            KnowledgeConversationTurn.course_id == course_id,
            KnowledgeConversationTurn.session_id == session_id[:120],
        )
        .order_by(KnowledgeConversationTurn.created_at.desc())
        .limit(1)
    )
    if not previous:
        return clean
    return f"{previous.user_message}\nسؤال متابعة: {clean}"[:20_000]


def remember_turn(db: Session, user_id: uuid.UUID, course_id: uuid.UUID, session_id: str, message: str, outcome: str, citations: list[dict]) -> None:
    db.add(KnowledgeConversationTurn(
        user_id=user_id,
        course_id=course_id,
        session_id=session_id[:120],
        user_message=message[:20_000],
        retrieved_unit_ids_json=[citation.get("unit_id") for citation in citations if citation.get("unit_id")],
        outcome=outcome,
    ))
    db.flush()
