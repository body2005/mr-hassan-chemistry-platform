import math
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course import Course, Enrollment, EnrollmentStatus
from app.models.teacher_tracking import TeacherTrackingColumn, TeacherTrackingValue
from app.models.user import User, UserRole
from app.schemas_tracking import TrackingColumnCreate

MAX_COLUMNS = 50


def eligible_students(user: User):
    return select(User.id).where(
        User.institution_id == user.institution_id,
        User.role == UserRole.STUDENT,
        User.deleted_at.is_(None),
        User.id.in_(
            select(Enrollment.student_id)
            .join(Course, Course.id == Enrollment.course_id)
            .where(
                Course.institution_id == user.institution_id,
                Course.teacher_id == user.id,
                Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
            )
        ),
    )


def owned_column(db: Session, user: User, column_id: uuid.UUID) -> TeacherTrackingColumn:
    column = db.scalar(
        select(TeacherTrackingColumn).where(
            TeacherTrackingColumn.id == column_id,
            TeacherTrackingColumn.institution_id == user.institution_id,
            TeacherTrackingColumn.teacher_id == user.id,
        )
    )
    if column is None:
        raise HTTPException(404, "Tracking column not found")
    return column


def snapshot(db: Session, user: User):
    columns = list(
        db.scalars(
            select(TeacherTrackingColumn)
            .where(
                TeacherTrackingColumn.institution_id == user.institution_id,
                TeacherTrackingColumn.teacher_id == user.id,
            )
            .order_by(TeacherTrackingColumn.created_at, TeacherTrackingColumn.id)
        )
    )
    rows = db.scalars(
        select(TeacherTrackingValue).where(
            TeacherTrackingValue.institution_id == user.institution_id,
            TeacherTrackingValue.teacher_id == user.id,
            TeacherTrackingValue.student_id.in_(eligible_students(user)),
        )
    )
    values: dict = {}
    for row in rows:
        values.setdefault(str(row.student_id), {})[str(row.column_id)] = row.value
    return {"columns": columns, "values": values}


def create_column(db: Session, user: User, payload: TrackingColumnCreate):
    # Serialize concurrent additions per teacher on PostgreSQL before the quota check.
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    count = db.scalar(
        select(func.count())
        .select_from(TeacherTrackingColumn)
        .where(
            TeacherTrackingColumn.institution_id == user.institution_id,
            TeacherTrackingColumn.teacher_id == user.id,
        )
    )
    if count >= MAX_COLUMNS:
        raise HTTPException(409, "Maximum tracking columns reached (50)")
    column = TeacherTrackingColumn(
        institution_id=user.institution_id, teacher_id=user.id, **payload.model_dump()
    )
    db.add(column)
    db.commit()
    db.refresh(column)
    return column


def delete_column(db: Session, user: User, column_id: uuid.UUID):
    column = owned_column(db, user, column_id)
    db.execute(
        delete(TeacherTrackingValue).where(
            TeacherTrackingValue.column_id == column.id,
            TeacherTrackingValue.institution_id == user.institution_id,
            TeacherTrackingValue.teacher_id == user.id,
        )
    )
    db.delete(column)
    db.commit()


def save_value(db: Session, user: User, column_id: uuid.UUID, student_id: uuid.UUID, value):
    column = owned_column(db, user, column_id)
    if db.scalar(eligible_students(user).where(User.id == student_id)) is None:
        raise HTTPException(404, "Student not found")
    valid = False
    if column.data_type == "text":
        valid = isinstance(value, str) and len(value) <= 2000
    elif column.data_type == "checkbox":
        valid = type(value) is bool
    elif type(value) in (float, int):
        valid = math.isfinite(value) and abs(value) <= 1_000_000_000
        if column.data_type == "percentage":
            valid = valid and 0 <= value <= 100
    if not valid:
        raise HTTPException(422, "Invalid value for tracking column type")
    filters = (
        TeacherTrackingValue.column_id == column_id,
        TeacherTrackingValue.student_id == student_id,
        TeacherTrackingValue.institution_id == user.institution_id,
        TeacherTrackingValue.teacher_id == user.id,
    )
    row = db.scalar(select(TeacherTrackingValue).where(*filters).with_for_update())
    if row is None:
        row = TeacherTrackingValue(
            column_id=column_id,
            student_id=student_id,
            institution_id=user.institution_id,
            teacher_id=user.id,
            value=value,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            # Concurrent first edits race on the primary key. Recheck ownership,
            # then update only that exact row; never resurrect a deleted column.
            db.rollback()
            owned_column(db, user, column_id)
            row = db.scalar(select(TeacherTrackingValue).where(*filters).with_for_update())
            if row is None:
                raise HTTPException(409, "Tracking changed; reload and retry") from None
            row.value = value
            db.commit()
    else:
        row.value = value
        db.commit()
    return {"value": value}
