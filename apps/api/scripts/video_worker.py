"""Separate worker polling a durable PostgreSQL queue, with crash recovery.

Session advisory locks serialize each job across workers without holding a
database transaction open during encoding. Unique attempt prefixes avoid mixing
partial generations. A crash releases the lock, allowing another worker to retry.
"""
import logging
import hashlib
import mimetypes
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from botocore.exceptions import ClientError
from sqlalchemy import select, text

from app.core.database import SessionLocal, engine
from app.core.storage import get_storage_provider
from app.models.course import Lesson
from app.models.video_upload import VideoUpload
from app.services.storage_cleanup import enqueue_cleanup
from app.services.video_processing import InvalidVideo, encode
from app.services.video_uploads import enqueue_source_cleanup

logger = logging.getLogger("video-worker")


def process(identity):
    storage = get_storage_provider()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as guard:
        key = int.from_bytes(identity.bytes[:8], "big", signed=True)
        if not guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}):
            return
        try:
            with SessionLocal() as db:
                job = db.get(VideoUpload, identity)
                if job is None:
                    return
                if job.lesson_id is None or (job.status in {"creating", "uploading", "completing"} and job.expires_at <= datetime.now(timezone.utc)):
                    allocations = [job.multipart_id] if job.multipart_id else []
                    if job.status == "creating":
                        for page in storage._get_client().get_paginator("list_multipart_uploads").paginate(Bucket=storage.bucket_name, Prefix=job.object_key):
                            allocations.extend(p["UploadId"] for p in page.get("Uploads", []) if p["Key"] == job.object_key)
                    for allocation in set(allocations):
                        try:
                            storage._get_client().abort_multipart_upload(Bucket=storage.bucket_name, Key=job.object_key, UploadId=allocation)
                        except ClientError as exc:
                            if exc.response["Error"]["Code"] != "NoSuchUpload":
                                raise
                    for name in job.outputs:
                        enqueue_cleanup(db, name)
                    enqueue_source_cleanup(db, job)
                    job.status = "expired"
                    db.commit()
                    return
                if job.status not in {"queued", "processing"}:
                    return
                if job.attempts >= 3:
                    job.status, job.error_code = "failed", "VIDEO_WORKER_RETRY_EXHAUSTED"
                    enqueue_source_cleanup(db, job)
                    for name in job.outputs:
                        enqueue_cleanup(db, name)
                    db.commit()
                    return
                job.status, job.attempts = "processing", job.attempts + 1
                # Clean previous interrupted attempt through the durable outbox.
                for name in job.outputs:
                    enqueue_cleanup(db, name)
                job.outputs = []
                db.commit()
                logger.info("video_id=%s state=processing attempt=%s", job.id, job.attempts)
                try:
                    # This UUID's previous scratch belongs only to interrupted
                    # attempts. The advisory lock proves no other worker uses it.
                    workspace = Path("/work").resolve()
                    for previous in workspace.glob(f"video-{identity}-*"):
                        if previous.is_dir() and not previous.is_symlink() and previous.resolve().parent == workspace:
                            shutil.rmtree(previous)
                    with tempfile.TemporaryDirectory(prefix=f"video-{identity}-", dir="/work") as folder:
                        root = Path(folder)
                        # Temporary scratch belongs to the worker, not API persistence.
                        if shutil.disk_usage(root).free < job.size_bytes + 26 * 1024**3:
                            raise RuntimeError("VIDEO_WORKSPACE_FULL")
                        source = root / "source"
                        total = 0
                        digest = hashlib.sha256()
                        with source.open("wb") as stream:
                            for chunk in storage.open_stream(job.object_key):
                                total += len(chunk)
                                if total > job.size_bytes:
                                    raise InvalidVideo("VIDEO_SIZE_MISMATCH")
                                stream.write(chunk)
                                digest.update(chunk)
                        if total != job.size_bytes:
                            raise InvalidVideo("VIDEO_SIZE_MISMATCH")
                        info, files = encode(source, root / "hls")
                        prefix = f"video-assets/{identity}/{uuid.uuid4().hex}"
                        # Save cleanup intents BEFORE each object write so a crash
                        # between remote write and DB acknowledgement isn't an orphan.
                        job.outputs = [f"{prefix}/{name}" for name in files]
                        db.commit()
                        for name in files:
                            path = root / "hls" / name
                            media = "application/vnd.apple.mpegurl" if name.endswith(".m3u8") else "video/mp2t"
                            storage.save_file(str(path), f"{prefix}/{name}", media)
                        original = f"video-originals/{identity}/{prefix.rsplit('/', 1)[-1]}/source.{job.filename.rsplit('.', 1)[-1].lower()}"
                        # Record a generation-unique original before remote copy.
                        # Previous-attempt cleanup must not delete a new attempt.
                        job.outputs = [*job.outputs, original]
                        db.commit()
                        storage._get_client().copy_object(Bucket=storage.bucket_name, Key=original,
                            CopySource={"Bucket": storage.bucket_name, "Key": job.object_key})
                        quarantine = job.object_key
                        lesson = db.scalar(select(Lesson).where(Lesson.id == job.lesson_id).with_for_update())
                        if lesson is None:
                            raise InvalidVideo("VIDEO_LESSON_REMOVED")
                        old_key = lesson.video_asset_key
                        for previous in db.scalars(select(VideoUpload).where(VideoUpload.lesson_id == lesson.id, VideoUpload.id != job.id, VideoUpload.status == "ready")):
                            for name in previous.outputs:
                                enqueue_cleanup(db, name)
                            previous.status = "superseded"
                        enqueue_cleanup(db, old_key)
                        job.object_key = original
                        job.sha256 = digest.hexdigest()
                        job.manifest_key = f"{prefix}/master.m3u8"
                        lesson.video_asset_key = f"s3://{storage.bucket_name}/{job.manifest_key}"
                        job.duration_seconds = lesson.video_duration_seconds = int(info["duration"])
                        job.status, job.error_code = "ready", None
                        enqueue_cleanup(db, quarantine)
                        db.commit()
                        logger.info("video_id=%s state=ready renditions=%s", job.id, len([n for n in files if n.endswith('index.m3u8')]))
                except Exception as exc:
                    db.rollback()
                    job = db.get(VideoUpload, identity)
                    # Infrastructure errors retry, invalid media fails explicitly.
                    job.status = "failed" if isinstance(exc, InvalidVideo) else "queued"
                    job.error_code = str(exc) if isinstance(exc, InvalidVideo) else "VIDEO_PROCESSING_TEMPORARILY_UNAVAILABLE"
                    if job.status == "failed":
                        enqueue_source_cleanup(db, job)
                    for name in job.outputs:
                        enqueue_cleanup(db, name)
                    job.outputs = []
                    db.commit()
                    logger.warning("video_id=%s state=%s error_code=%s", identity, job.status, job.error_code)
        finally:
            guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})


def main():
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
    Path("/work").mkdir(exist_ok=True)
    while True:
        try:
            with SessionLocal() as db:
                jobs = db.scalars(select(VideoUpload.id).where(
                    (VideoUpload.status.in_(["queued", "processing"])) |
                    ((VideoUpload.status.in_(["creating", "uploading", "completing"])) & (VideoUpload.expires_at < datetime.now(timezone.utc))) |
                    ((VideoUpload.lesson_id.is_(None)) & (~VideoUpload.status.in_(["expired", "superseded", "cancelled"])))).limit(20)).all()
            for identity in jobs:
                process(identity)
        except Exception:
            logger.warning("Video worker dependency temporarily unavailable")
        time.sleep(5)


if __name__ == "__main__":
    main()
