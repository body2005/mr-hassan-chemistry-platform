"""Transaction-local identity for a separately reviewed, opt-in RLS rollout.

Only call after resolving and validating a server-side identity. Never accept
tenant/user/role from request headers or a background job's arbitrary payload.
This does not install or enable any PostgreSQL policy.
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.core.config import get_settings


@dataclass(frozen=True)
class DatabaseActor:
    institution_id: UUID
    user_id: UUID
    role: str


def _apply(connection, actor: DatabaseActor) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT set_config('app.institution_id', :tenant, true), "
                                "set_config('app.user_id', :actor, true), "
                                "set_config('app.role', :role, true)"),
                           {"tenant": str(actor.institution_id), "actor": str(actor.user_id), "role": actor.role})


@event.listens_for(Session, "after_begin")
def _new_transaction(session, transaction, connection):
    # SET LOCAL automatically expires on COMMIT/ROLLBACK, including pool return.
    # Reapply the immutable identity when a route commits then starts another tx.
    actor = session.info.get("verified_database_actor")
    if actor is not None and transaction.parent is None:
        _apply(connection, actor)


def bind_verified_actor(db: Session, user) -> None:
    if not get_settings().rls_context_enabled:
        return
    actor = DatabaseActor(UUID(str(user.institution_id)), UUID(str(user.id)), user.role.value)
    previous = db.info.get("verified_database_actor")
    if previous is not None and previous != actor:
        raise RuntimeError("Database identity cannot change within a session")
    db.info["verified_database_actor"] = actor
    # Authentication may already have started the transaction before binding.
    _apply(db.connection(), actor)
