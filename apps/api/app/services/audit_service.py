from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
UTC = timezone.utc
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.platform import AuditLog
from app.models.user import User

logger = logging.getLogger("matgar.audit")


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value, default=str)
        return value
    except (TypeError, ValueError):
        return {"value": str(value)}


def record_audit(
    db: Session,
    request: Request,
    *,
    action: str,
    resource_type: str,
    actor: User | None = None,
    resource_id: str | None = None,
    before: Any = None,
    after: Any = None,
) -> None:
    request_id = request.headers.get("X-Request-ID") or getattr(request.state, "request_id", None)
    entry = AuditLog(
        institution_id=actor.institution_id if actor else None,
        actor_id=actor.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_json=_safe_json(before),
        after_json=_safe_json(after),
        request_id=request_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        occurred_at=datetime.now(UTC),
    )
    db.add(entry)
    logger.info(
        "audit action=%s resource_type=%s resource_id=%s actor_id=%s request_id=%s",
        action,
        resource_type,
        resource_id,
        actor.id if actor else None,
        request_id,
    )


def commit_audit(db: Session) -> None:
    db.commit()
