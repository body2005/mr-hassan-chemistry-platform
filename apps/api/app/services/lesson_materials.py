"""Lesson materials: standalone upload/download/delete over LessonAsset.

Replaces the Knowledge-Source based materials flow. Files go straight to the
storage provider and are tracked by lesson_assets rows — no AI indexing,
no RAG, no knowledge tables.
"""
from __future__ import annotations

import mimetypes
import os
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course, CourseModule, Lesson
from app.models.extended import LessonAsset
from app.models.user import User
from app.services.extraction_staging import resolve_course_uuid, resolve_lesson_uuid  # re-export convenience

ALLOWED_MATERIAL_EXT = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".csv",
    ".png", ".jpg", ".jpeg", ".webp", ".zip",
}
MAX_MATERIAL_BYTES = 100 * 1024 * 1024  # 100MB per material file


def _lesson_course(db: Session, lesson_id: uuid.UUID) -> tuple[Lesson, Course]:
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    module = db.get(CourseModule, lesson.module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Lesson module not found")
    course = db.get(Course, module.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return lesson, course


def ensure_course_manager(user: User, course: Course) -> None:
    if getattr(user, "role", None) and getattr(user.role, "value", str(user.role)) == "platform_admin":
        return
    if str(getattr(user.role, "value", user.role)) in {"teacher", "institution_admin"}:
        if course.institution_id != user.institution_id:
            raise PermissionError("Course belongs to another institution")
        if str(getattr(user.role, "value", user.role)) == "teacher" and course.teacher_id != user.id:
            raise PermissionError("Only the course teacher can manage its materials")
        return
    raise PermissionError("Not allowed")


async def upload_material(
    db: Session,
    user: User,
    lesson_id: uuid.UUID,
    file: UploadFile,
) -> LessonAsset:
    lesson, course = _lesson_course(db, lesson_id)
    try:
        ensure_course_manager(user, course)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    filename = os.path.basename(file.filename or "material")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_MATERIAL_EXT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported material type: {ext or 'unknown'}",
        )

    from app.core.storage import generate_safe_object_key, get_storage_provider

    storage = get_storage_provider()
    object_key = generate_safe_object_key("lesson_materials", filename)
    size = 0
    import hashlib

    digest = hashlib.sha256()
    tmp_dir = os.path.join(os.getenv("STORAGE_DIR", "storage"), "extraction_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    staged = os.path.join(tmp_dir, f"mat_{uuid.uuid4().hex[:12]}_{filename}")
    try:
        with open(staged, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_MATERIAL_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Material exceeds the 100MB limit",
                    )
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        storage.save_file(staged, object_key)
    finally:
        if os.path.exists(staged):
            try:
                os.remove(staged)
            except OSError:
                pass

    asset = LessonAsset(
        lesson_id=lesson.id,
        institution_id=course.institution_id,
        asset_kind="pdf" if ext == ".pdf" else ("document" if ext in {".doc", ".docx", ".txt", ".csv", ".ppt", ".pptx"} else "attachment"),
        object_key=object_key,
        filename=filename,
        mime_type=file.content_type or mimetypes.guess_type(filename)[0],
        size_bytes=size,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _get_asset(db: Session, lesson_id: uuid.UUID, asset_id: uuid.UUID) -> LessonAsset:
    asset = db.get(LessonAsset, asset_id)
    if not asset or asset.lesson_id != lesson_id:
        raise HTTPException(status_code=404, detail="Material not found")
    return asset


def delete_material(db: Session, user: User, lesson_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    lesson, course = _lesson_course(db, lesson_id)
    try:
        ensure_course_manager(user, course)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    asset = _get_asset(db, lesson_id, asset_id)
    try:
        from app.core.storage import get_storage_provider

        if asset.object_key:
            storage = get_storage_provider()
            if storage.exists(asset.object_key):
                storage.delete(asset.object_key)
    except Exception:
        pass
    db.delete(asset)
    db.commit()


def open_material_stream(db: Session, user: User, lesson_id: uuid.UUID, asset_id: uuid.UUID, as_attachment: bool):
    """Authorise then stream a material from the storage provider."""
    lesson, course = _lesson_course(db, lesson_id)
    asset = _get_asset(db, lesson_id, asset_id)

    # Access: managers always; students need any access to the lesson's course.
    is_manager = False
    try:
        ensure_course_manager(user, course)
        is_manager = True
    except HTTPException:
        raise
    except PermissionError:
        is_manager = False
    if not is_manager:
        from app.models.course import Enrollment, EnrollmentStatus

        enrolled = db.scalar(
            select(Enrollment.id).where(
                Enrollment.course_id == course.id,
                Enrollment.student_id == user.id,
                Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
            )
        )
        if not enrolled and float(course.price_egp or 0) != 0:
            raise HTTPException(status_code=403, detail="You do not have access to this material")

    if not asset.object_key:
        raise HTTPException(status_code=404, detail="Material file missing")
    from app.core.storage import get_storage_provider

    storage = get_storage_provider()
    if not storage.exists(asset.object_key):
        raise HTTPException(status_code=404, detail="Material file missing")
    media_type = asset.mime_type or "application/octet-stream"
    return storage.open_stream(asset.object_key), media_type, asset.filename
