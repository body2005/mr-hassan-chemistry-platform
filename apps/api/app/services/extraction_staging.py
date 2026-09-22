"""Upload staging helpers for the local quiz/assignment extraction flow.

Split out of the removed Knowledge Center routes; pure file/stream utilities
plus tenant-scoped course/lesson resolution used by extraction endpoints.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course, CourseModule, Lesson
from app.models.user import User


def resolve_course_uuid(db: Session, user: User, course_id: str | None) -> uuid.UUID:
    if not course_id or not str(course_id).strip():
        raise HTTPException(status_code=422, detail="A valid course_id is required")
    try:
        course_uuid = uuid.UUID(str(course_id))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid course ID") from exc
    course = db.scalar(
        select(Course).where(Course.id == course_uuid, Course.institution_id == user.institution_id)
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if user.role != "platform_admin" and hasattr(user, "role") and str(user.role) not in {"teacher", "admin", "platform_admin"}:
        raise HTTPException(status_code=403, detail="Not allowed")
    return course_uuid


def resolve_lesson_uuid(db: Session, course_id: uuid.UUID, lesson_id: str | None) -> uuid.UUID:
    if not lesson_id or not str(lesson_id).strip():
        raise HTTPException(status_code=422, detail="A valid lesson_id is required")
    try:
        lesson_uuid = uuid.UUID(str(lesson_id))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid lesson ID") from exc
    lesson = db.scalar(
        select(Lesson)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .where(Lesson.id == lesson_uuid, CourseModule.course_id == course_id)
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found in this course")
    return lesson.id


def get_extraction_temp_dir() -> str:
    base = os.getenv("STORAGE_DIR", "storage")
    path = os.path.join(base, "extraction_tmp")
    os.makedirs(path, exist_ok=True)
    return path


async def stream_upload_to_file(
    uploaded: UploadFile,
    dest_path: str,
    max_file_bytes: int,
    current_batch_bytes: int = 0,
    max_batch_bytes: int | None = None,
) -> tuple[int, str]:
    """Stream an UploadFile to dest_path enforcing size caps; returns (size, sha256)."""
    import hashlib

    size = 0
    digest = hashlib.sha256()
    with open(dest_path, "wb") as out:
        while True:
            chunk = await uploaded.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_file_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File exceeds the maximum allowed size",
                )
            if max_batch_bytes is not None and current_batch_bytes + size > max_batch_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Batch exceeds the maximum allowed size",
                )
            digest.update(chunk)
            out.write(chunk)
    return size, digest.hexdigest()
