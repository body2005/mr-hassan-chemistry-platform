from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas_tracking import (
    TrackingColumnCreate,
    TrackingColumnRead,
    TrackingSnapshot,
    TrackingValueWrite,
)
from app.services import teacher_tracking_service as tracking

router = APIRouter(prefix="/teacher-tracking")
Teacher = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]
Db = Annotated[Session, Depends(get_db)]


@router.get("", response_model=TrackingSnapshot)
def read_tracking(user: Teacher, db: Db):
    return tracking.snapshot(db, user)


@router.post("/columns", response_model=TrackingColumnRead, status_code=201)
def create_tracking_column(payload: TrackingColumnCreate, user: Teacher, db: Db):
    return tracking.create_column(db, user, payload)


@router.delete("/columns/{column_id}", status_code=204)
def delete_tracking_column(column_id: UUID, user: Teacher, db: Db):
    tracking.delete_column(db, user, column_id)
    return Response(status_code=204)


@router.put("/columns/{column_id}/students/{student_id}")
def save_tracking_value(
    column_id: UUID, student_id: UUID, payload: TrackingValueWrite, user: Teacher, db: Db
):
    return tracking.save_value(db, user, column_id, student_id, payload.value)
