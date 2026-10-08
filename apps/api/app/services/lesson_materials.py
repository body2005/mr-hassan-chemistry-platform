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
from sqlalchemy.orm import Session

from app.models.course import Course, CourseModule, Lesson
from app.models.extended import LessonAsset
from app.models.user import User
from app.services.extraction_staging import resolve_course_uuid, resolve_lesson_uuid  # re-export convenience
from app.services.storage_cleanup import compensate_upload, enqueue_cleanup

ALLOWED_MATERIAL_EXT = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".csv",
    ".png", ".jpg", ".jpeg", ".webp", ".zip",
}
from app.core.upload_limits import MAX_MATERIAL_BYTES, ensure_staging_capacity


def _matches_material_format(ext: str, header: bytes) -> bool:
    if not header:
        return False
    if ext == ".pdf":
        return header.startswith(b"%PDF-")
    if ext == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if ext == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if ext in {".docx", ".pptx", ".zip"}:
        return header.startswith((b"PK\x03\x04", b"PK\x05\x06"))
    if ext in {".doc", ".ppt"}:
        return header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    return b"\x00" not in header


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

    # Starlette's parsed file size excludes multipart envelope bytes. Reject
    # known overflow before making a second staging copy or contacting S3.
    # Unknown sizes still use the streaming byte counter below.
    if file.size is not None and file.size > MAX_MATERIAL_BYTES:
        raise HTTPException(status_code=413, detail=f"Material exceeds the {MAX_MATERIAL_BYTES}-byte limit (1 GiB)")

    filename = os.path.basename(file.filename or "material")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_MATERIAL_EXT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported material type: {ext or 'unknown'}",
        )
    header = await file.read(512)
    await file.seek(0)
    if not _matches_material_format(ext, header):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file does not match its material format",
        )

    from app.core.storage import generate_safe_object_key, get_storage_provider

    storage = get_storage_provider()
    object_key = generate_safe_object_key("lesson_materials", filename)
    size = 0
    import hashlib

    digest = hashlib.sha256()
    tmp_dir = os.path.join(os.getenv("STORAGE_DIR", "storage"), "extraction_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    ensure_staging_capacity(file.size or MAX_MATERIAL_BYTES, tmp_dir)
    staged = os.path.join(tmp_dir, f"mat_{uuid.uuid4().hex[:12]}_{filename}")
    storage_started = False
    try:
        with open(staged, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_MATERIAL_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Material exceeds the {MAX_MATERIAL_BYTES}-byte limit (1 GiB)",
                    )
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        storage_started = True
        storage.save_file(staged, object_key)
    except BaseException:
        db.rollback()
        if storage_started:
            compensate_upload(db, object_key)
        raise
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
    try:
        db.commit()
    except Exception:
        db.rollback()
        compensate_upload(db, object_key)
        raise
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
    enqueue_cleanup(db, asset.object_key)
    db.delete(asset)
    db.commit()


def open_material_stream(db: Session, user: User, lesson_id: uuid.UUID, asset_id: uuid.UUID, as_attachment: bool):
    """Authorise then stream a material from the storage provider."""
    lesson, course = _lesson_course(db, lesson_id)
    asset = _get_asset(db, lesson_id, asset_id)

    # Access is determined per lesson, including its payment entitlement.
    is_manager = False
    try:
        ensure_course_manager(user, course)
        is_manager = True
    except HTTPException:
        raise
    except PermissionError:
        is_manager = False
    if not is_manager:
        from app.services.payment_service import can_access_lesson_content

        if not can_access_lesson_content(db, user, lesson_id):
            raise HTTPException(status_code=403, detail="You do not have access to this material")

    if not asset.object_key:
        raise HTTPException(status_code=404, detail="Material file missing")
    from app.core.storage import get_storage_provider

    storage = get_storage_provider()
    if not storage.exists(asset.object_key):
        raise HTTPException(status_code=404, detail="Material file missing")
    media_type = asset.mime_type or "application/octet-stream"
    return storage.open_stream(asset.object_key), media_type, asset.filename
