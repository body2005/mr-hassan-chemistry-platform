"""Generic idempotency support for sensitive POST endpoints.

Usage inside a route:

    from app.core.idempotency import idempotent

    @router.post("/things", response_model=ThingResponse)
    def create_thing(payload: ThingCreate, db: Db, user: CurrentUser,
                     request: Request, response: Response,
                     idempotency_key: Annotated[str | None, Header()] = None):
        cached = idempotent_begin(db, user.id, "things:create",
                                  idempotency_key=idempotency_key,
                                  request_hash=payload.model_dump_json())
        if cached is not None:
            return cached  # replay of a previous identical call
        ...do work...
        idempotent_commit(db, key_row, status_code=201, response_json=result)
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.extended import IdempotencyKey

DEFAULT_TTL_HOURS = 24


def hash_request(payload: str | None) -> str:
    return hashlib.sha256((payload or "").encode("utf-8")).hexdigest()


def idempotent_begin(
    db: Session,
    user_id: uuid.UUID | None,
    endpoint: str,
    *,
    idempotency_key: str | None,
    request_hash: str | None = None,
    ttl_hours: int = DEFAULT_TTL_HOURS,
) -> tuple[IdempotencyKey | None, dict | list | None]:
    """Returns (key_row, cached_response). If cached_response is not None the
    caller must return it instead of performing the operation again.

    A missing Idempotency-Key disables dedup (returns (None, None)) — callers
    that REQUIRE idempotency should validate the header at the schema level.
    """
    if not idempotency_key:
        return None, None

    full_key = f"{endpoint}:{idempotency_key}"[:128]
    existing = db.query(IdempotencyKey).filter(IdempotencyKey.key == full_key).one_or_none()
    if existing is not None:
        if existing.request_hash and request_hash and existing.request_hash != request_hash:
            raise ValueError("IDEMPOTENCY_KEY_REUSED")  # caller maps to 409/422
        if existing.response_json is not None and (
            existing.expires_at is None or existing.expires_at > datetime.now(timezone.utc)
        ):
            return None, existing.response_json
        # Expired or incomplete: refresh and let the caller redo the work.
        db.delete(existing)
        db.flush()

    row = IdempotencyKey(
        key=full_key,
        user_id=user_id,
        endpoint=endpoint[:200],
        request_hash=request_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    )
    db.add(row)
    db.flush()
    return row, None


def idempotent_commit(
    db: Session,
    row: IdempotencyKey | None,
    *,
    status_code: int,
    response_json: dict | list,
) -> None:
    if row is None:
        return
    row.response_status = status_code
    row.response_json = json.loads(json.dumps(response_json, default=str))
    db.add(row)


def serialize_for_cache(schema_value) -> dict | list:
    """Pydantic v2 helper to store a response model as JSON-safe data."""
    data = schema_value.model_dump(mode="json")
    return data
