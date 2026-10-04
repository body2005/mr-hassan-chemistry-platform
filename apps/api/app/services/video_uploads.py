"""S3 multipart control plane. File bytes never pass through the API.

Clients may upload only an exact-sized, numbered part in a private quarantine.
Completion uses storage's list-parts, NOT client-declared ETags/sizes. Queue state
commits in PostgreSQL, so broker outages cannot lose a processing job.
"""
import math
import re
import uuid
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage import S3StorageProvider, get_storage_provider
from app.core.upload_limits import MAX_VIDEO_BYTES
from app.models.course import Lesson
from app.models.user import User
from app.models.video_upload import VideoUpload
from app.services.storage_cleanup import enqueue_cleanup

PART_BYTES = 32 * 1024 * 1024
EXTENSIONS = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
ACTIVE_STATES = ("creating", "uploading", "completing", "queued", "processing")


def storage() -> S3StorageProvider:
    settings = get_settings()
    if not settings.video_direct_upload_enabled:
        raise HTTPException(503, "Direct video upload is not configured")
    if settings.video_drm_required:
        # The local FFmpeg encoder does NOT produce licensed DRM media.
        raise HTTPException(503, "A DRM packaging provider must be configured before uploading protected assets")
    provider = get_storage_provider()
    if not isinstance(provider, S3StorageProvider):
        raise HTTPException(503, "Object storage is required")
    return provider


def validate_upload(filename: str, size: int, content_type: str, fingerprint: str, request_key: str) -> None:
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in EXTENSIONS or content_type != EXTENSIONS[ext]:
        raise HTTPException(422, "Unsupported video format")
    if size < 1 or size > MAX_VIDEO_BYTES:
        raise HTTPException(413, "Video limit is 5 GiB")
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", request_key):
        raise HTTPException(422, "Invalid upload identity")


def owned(db: Session, upload_id: uuid.UUID, owner: User, *, lock=False) -> VideoUpload:
    query = select(VideoUpload).where(VideoUpload.id == upload_id, VideoUpload.owner_id == owner.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    upload = db.scalar(query)
    if upload is None or upload.lesson_id is None:
        raise HTTPException(404, "Upload not found")
    return upload


def create(db: Session, owner: User, lesson: Lesson, payload) -> VideoUpload:
    provider = storage()
    validate_upload(payload.filename, payload.size_bytes, payload.content_type, payload.fingerprint, payload.request_key)
    # Serialize quotas/idempotency across this owner, including different lessons.
    db.scalar(select(User).where(User.id == owner.id).with_for_update())
    previous = db.scalar(select(VideoUpload).where(VideoUpload.owner_id == owner.id,
        VideoUpload.lesson_id == lesson.id, VideoUpload.request_key == payload.request_key))
    if previous:
        if (previous.size_bytes, previous.fingerprint, previous.filename, previous.content_type) != (payload.size_bytes, payload.fingerprint, payload.filename, payload.content_type):
            raise HTTPException(409, "Retry identity belongs to a different file")
        return previous
    db.scalar(select(Lesson).where(Lesson.id == lesson.id).with_for_update())
    active = db.scalar(select(func.count()).select_from(VideoUpload).where(VideoUpload.owner_id == owner.id, VideoUpload.status.in_(ACTIVE_STATES)))
    pending = db.scalar(select(VideoUpload.id).where(VideoUpload.lesson_id == lesson.id, VideoUpload.status.in_(ACTIVE_STATES)).limit(1))
    if active >= 3 or pending:
        raise HTTPException(409, "An upload is already active; resume or cancel it first")
    identity = uuid.uuid4()
    upload = VideoUpload(id=identity, owner_id=owner.id, lesson_id=lesson.id,
        request_key=payload.request_key, filename=payload.filename, size_bytes=payload.size_bytes,
        fingerprint=payload.fingerprint, content_type=payload.content_type,
        object_key=f"video-staging/{identity}/source.{payload.filename.rsplit('.', 1)[-1].lower()}",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48), status="creating", outputs=[])
    db.add(upload)
    # Persist intent BEFORE storage allocation; retries resume 'creating'.
    db.commit()
    return upload


def initialize(db: Session, upload: VideoUpload) -> None:
    if upload.status != "creating":
        return
    provider = storage()
    # Recover a crash after allocation but before recording its UploadId. All
    # objects under this UUID prefix belong exclusively to this DB intent.
    matches = []
    for page in provider._get_client().get_paginator("list_multipart_uploads").paginate(Bucket=provider.bucket_name, Prefix=upload.object_key):
        matches.extend(p for p in page.get("Uploads", []) if p["Key"] == upload.object_key)
    if matches:
        upload.multipart_id = matches[0]["UploadId"]
        for extra in matches[1:]:
            provider._get_client().abort_multipart_upload(Bucket=provider.bucket_name, Key=upload.object_key, UploadId=extra["UploadId"])
        upload.status = "uploading"
        db.commit()
        return
    response = provider._get_client().create_multipart_upload(Bucket=provider.bucket_name,
        Key=upload.object_key, ContentType=upload.content_type,
        Metadata={"video-id": str(upload.id), "declared-size": str(upload.size_bytes)})
    upload.multipart_id = response["UploadId"]
    upload.status = "uploading"
    db.commit()


def list_parts(upload: VideoUpload) -> list[dict]:
    provider = storage()
    parts = []
    for page in provider._get_client().get_paginator("list_parts").paginate(
            Bucket=provider.bucket_name, Key=upload.object_key, UploadId=upload.multipart_id):
        parts.extend(page.get("Parts", []))
    return parts


def recover_parts(db: Session, upload: VideoUpload) -> list[dict]:
    """Object snapshots cannot restore incomplete S3 multipart sessions.

    Treat only the precise NoSuchUpload as terminal, not an outage/403. The
    caller holds the upload row lock so concurrent completion cannot be
    mislabeled as a lost session. A reselected file can start a new intent.
    """
    try:
        return list_parts(upload)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchUpload":
            raise
        upload.status = "expired"
        upload.error_code = "VIDEO_UPLOAD_STORAGE_SESSION_LOST"
        db.commit()
        return []


def part_size(upload: VideoUpload, number: int) -> int:
    if not 1 <= number <= math.ceil(upload.size_bytes / PART_BYTES):
        raise HTTPException(422, "Invalid part number")
    return min(PART_BYTES, upload.size_bytes - (number - 1) * PART_BYTES)


def sign_part(upload: VideoUpload, number: int) -> dict:
    if upload.status != "uploading" or upload.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(409, "Upload is not active")
    size = part_size(upload, number)
    provider = storage()
    import boto3
    from botocore.config import Config
    # Separate signer: signature uses the public gateway's Host, never private DNS.
    signer = boto3.client("s3", endpoint_url=get_settings().video_upload_public_endpoint,
        aws_access_key_id=provider.access_key_id, aws_secret_access_key=provider.secret_access_key,
        region_name=provider.region_name, config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))
    url = signer.generate_presigned_url("upload_part", Params={"Bucket": provider.bucket_name,
        "Key": upload.object_key, "UploadId": upload.multipart_id, "PartNumber": number, "ContentLength": size},
        ExpiresIn=300, HttpMethod="PUT")
    return {"url": url, "size_bytes": size, "expires_in": 300}


def complete(db: Session, upload: VideoUpload) -> None:
    provider = storage()
    if upload.status in {"queued", "processing", "ready"}:
        return  # Lost completion response may be retried safely.
    if upload.status not in {"uploading", "completing"}:
        raise HTTPException(409, "Upload is not active")
    if upload.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(409, "Upload has expired")
    if upload.status == "completing":
        try:
            head = provider._get_client().head_object(Bucket=provider.bucket_name, Key=upload.object_key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in {"404", "NoSuchKey", "NotFound"}:
                raise
        else:
            if head["ContentLength"] != upload.size_bytes or head.get("Metadata", {}).get("video-id") != str(upload.id):
                raise HTTPException(409, "Stored upload does not match its session")
            upload.status = "queued"
            db.commit()
            return
    parts = recover_parts(db, upload)
    if upload.status == "expired":
        raise HTTPException(409, "Storage upload session was lost; reselect the file to restart")
    expected = math.ceil(upload.size_bytes / PART_BYTES)
    if len(parts) != expected or any(p["PartNumber"] != i or p["Size"] != part_size(upload, i) for i, p in enumerate(parts, 1)):
        raise HTTPException(409, "Missing or incorrectly sized video parts")
    upload.status = "completing"
    db.commit()  # Durable recovery if object completion succeeds before DB update.
    provider._get_client().complete_multipart_upload(Bucket=provider.bucket_name, Key=upload.object_key,
        UploadId=upload.multipart_id, MultipartUpload={"Parts": [{"PartNumber": p["PartNumber"], "ETag": p["ETag"]} for p in parts]})
    upload.status = "queued"
    db.commit()


def abort(db: Session, upload: VideoUpload) -> None:
    if upload.status in {"ready", "processing"}:
        raise HTTPException(409, "An already-processing video cannot be cancelled")
    provider = storage()
    if upload.multipart_id:
        try:
            provider._get_client().abort_multipart_upload(Bucket=provider.bucket_name, Key=upload.object_key, UploadId=upload.multipart_id)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchUpload":
                raise
    enqueue_cleanup(db, upload.object_key)
    upload.status = "cancelled"
    db.commit()


def summary(upload: VideoUpload, parts: list[dict] | None = None) -> dict:
    return {"id": str(upload.id), "lesson_id": str(upload.lesson_id), "status": upload.status,
        "part_bytes": PART_BYTES, "size_bytes": upload.size_bytes, "fingerprint": upload.fingerprint,
        "uploaded_parts": [{"number": p["PartNumber"], "size_bytes": p["Size"]} for p in (parts or [])],
        "error_code": upload.error_code, "duration_seconds": upload.duration_seconds}
