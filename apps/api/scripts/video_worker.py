"""Separate worker polling a durable PostgreSQL queue, with crash recovery.

Session advisory locks serialize each job across workers without holding a
database transaction open during encoding. Unique attempt prefixes avoid mixing
partial generations. A crash releases the lock, allowing another worker to retry.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import hashlib
import mimetypes
import re
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from botocore.exceptions import ClientError
from sqlalchemy import select, text

from app.core.database import SessionLocal, engine
from app.core.config import get_settings
from app.core.storage import get_storage_provider
from app.models.course import Lesson
from app.models.video_upload import VideoUpload
from app.services.storage_cleanup import enqueue_cleanup
from app.services.video_processing import InvalidVideo, encode
from app.services.video_uploads import enqueue_source_cleanup, RETRYABLE_PROCESSING_ERRORS
from app.services.video_worker_status import WorkerHeartbeat

logger = logging.getLogger("video-worker")


def failure_diagnostic(error):
    """Finite error identifiers only: never log SDK URLs, SQL or parameters."""
    code = getattr(error, 'sqlstate', None)
    if isinstance(error, ClientError):
        code = error.response.get('Error', {}).get('Code')
    return type(error).__name__, code if isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', code) else 'unknown'


def process(identity, heartbeat=None):
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
                if job.lesson_id is None or (job.status in {"creating", "uploading", "completing", 'failed'} and job.expires_at <= datetime.now(timezone.utc)):
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
                retry_after = job.retry_after.replace(tzinfo=timezone.utc) if job.retry_after and job.retry_after.tzinfo is None else job.retry_after
                if job.status == 'queued' and retry_after and retry_after > datetime.now(timezone.utc):
                    return
                if job.attempts >= 3:
                    job.status, job.error_code = "failed", "VIDEO_WORKER_RETRY_EXHAUSTED"
                    # Keep completed source until the existing 48h expiry so
                    # an explicit retry need not upload the same bytes again.
                    for name in job.outputs:
                        enqueue_cleanup(db, name)
                    db.commit()
                    return
                job.status, job.attempts, job.retry_after = "processing", job.attempts + 1, None
                # Recovery retains the observed high-water mark. A retry must
                # finish the whole new generation before it can become ready.
                job.processing_percent, job.processing_stage = min(99, job.processing_percent or 0), "downloading"
                # Clean previous interrupted attempt through the durable outbox.
                for name in job.outputs:
                    enqueue_cleanup(db, name)
                job.outputs = []
                db.commit()
                logger.info("video_id=%s state=processing attempt=%s", job.id, job.attempts)
                if heartbeat:
                    heartbeat.update('processing', identity, job.processing_stage, job.processing_percent)
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
                        last_progress = [0.0]
                        def report(percent, stage):
                            if heartbeat:
                                heartbeat.update('processing', identity, stage, percent)
                            now = time.monotonic()
                            if stage == job.processing_stage and now - last_progress[0] < 10:
                                return
                            job.processing_percent = max(job.processing_percent or 0, min(99, percent))
                            job.processing_stage = stage
                            db.commit()
                            last_progress[0] = now
                        total = 0
                        digest = hashlib.sha256()
                        with source.open("wb") as stream:
                            for chunk in storage.open_stream(job.object_key):
                                total += len(chunk)
                                if total > job.size_bytes:
                                    raise InvalidVideo("VIDEO_SIZE_MISMATCH")
                                stream.write(chunk)
                                digest.update(chunk)
                                report(min(4, int(5 * total / job.size_bytes)), "downloading")
                        if total != job.size_bytes:
                            raise InvalidVideo("VIDEO_SIZE_MISMATCH")
                        if job.sha256 and job.sha256 != digest.hexdigest():
                            raise InvalidVideo('VIDEO_SOURCE_CHANGED')
                        job.sha256 = digest.hexdigest()
                        db.commit()
                        lesson_snapshot = db.get(Lesson, job.lesson_id)
                        use_drm = bool(get_settings().video_drm_packaging_enabled or
                            (lesson_snapshot and lesson_snapshot.video_drm_protected) or (job.drm or {}).get('requested'))
                        replaces = (job.drm or {}).get('replaces')
                        def encoding_progress(percent, stage):
                            report(min(75, int(percent * 75 / 85)) if use_drm else percent, stage)
                        info, files = encode(source, root / 'hls', progress=encoding_progress)
                        output_root, drm_metadata = root / 'hls', None
                        if use_drm:
                            from app.services.video_drm_packaging import package
                            output_root = root / 'encrypted'
                            files, drm_metadata = package(root / 'hls', output_root, info, progress=report)
                        prefix = f"video-assets/{identity}/{uuid.uuid4().hex}"
                        # Save cleanup intents BEFORE each object write so a crash
                        # between remote write and DB acknowledgement isn't an orphan.
                        job.outputs = [f"{prefix}/{name}" for name in files]
                        db.commit()
                        def save_output(name):
                            path = output_root / name
                            size = path.stat().st_size
                            media = ('application/vnd.apple.mpegurl' if name.endswith('.m3u8') else
                                'audio/mp4' if name.startswith('audio/') else 'video/mp4' if use_drm else 'video/mp2t')
                            storage.save_file(str(path), f"{prefix}/{name}", media)
                            if storage.get_size(f'{prefix}/{name}') != size:
                                raise RuntimeError('VIDEO_REMOTE_OUTPUT_INCOMPLETE')
                            return size
                        report(85, "uploading")
                        # Bounded network concurrency; only this thread touches DB.
                        total_output_bytes = sum((output_root / name).stat().st_size for name in files)
                        saved_bytes = 0
                        with ThreadPoolExecutor(max_workers=4) as uploads:
                            # Bound submitted work too; do not queue thousands of
                            # futures or allow upload threads to touch the DB.
                            remaining = iter(files)
                            pending = {uploads.submit(save_output, name) for name in [next(remaining, None) for _ in range(4)] if name is not None}
                            while pending:
                                completed = next(as_completed(pending))
                                pending.remove(completed)
                                saved_bytes += completed.result()
                                report(85 + int(14 * saved_bytes / total_output_bytes), "uploading")
                                name = next(remaining, None)
                                if name is not None:
                                    pending.add(uploads.submit(save_output, name))
                        # The completed source is already durable, private and
                        # SHA-256 verified above. Retain it in place instead of
                        # copying the full video again after encoding. A slow
                        # CopyObject response used to discard all renditions and
                        # restart the entire job near its completion milestone.
                        original = job.object_key
                        original_keys = {original, f's3://{storage.bucket_name}/{original}'}
                        report(99, 'finalizing')
                        if storage.get_size(original) != job.size_bytes:
                            raise RuntimeError('VIDEO_REMOTE_ORIGINAL_INCOMPLETE')
                        lesson = db.scalar(select(Lesson).where(Lesson.id == job.lesson_id).with_for_update().execution_options(populate_existing=True))
                        if lesson is None:
                            raise InvalidVideo("VIDEO_LESSON_REMOVED")
                        if replaces and lesson.video_asset_key != replaces:
                            raise InvalidVideo('VIDEO_DRM_SOURCE_CHANGED')
                        if lesson.video_drm_protected and not drm_metadata:
                            raise InvalidVideo('VIDEO_DRM_DOWNGRADE_FORBIDDEN')
                        old_key = lesson.video_asset_key
                        for previous in db.scalars(select(VideoUpload).where(VideoUpload.lesson_id == lesson.id, VideoUpload.id != job.id, VideoUpload.status == "ready")):
                            for name in previous.outputs:
                                # DRM/reprocessing can share this same private
                                # source. Retiring the old outputs must keep it.
                                if name not in original_keys:
                                    enqueue_cleanup(db, name)
                            previous.status = "superseded"
                        if old_key not in original_keys:
                            enqueue_cleanup(db, old_key)
                        job.object_key = original
                        # Add the source only in the ready transaction. Failed
                        # output cleanup must never retire a retry's source.
                        job.outputs = [*job.outputs, original]
                        job.sha256 = digest.hexdigest()
                        job.manifest_key = f"{prefix}/master.m3u8"
                        lesson.video_asset_key = f"s3://{storage.bucket_name}/{job.manifest_key}"
                        job.drm = drm_metadata
                        lesson.video_drm_protected = bool(lesson.video_drm_protected or drm_metadata)
                        job.duration_seconds = lesson.video_duration_seconds = int(info["duration"])
                        job.status, job.error_code = "ready", None
                        job.processing_percent, job.processing_stage = 100, "ready"
                        db.commit()
                        logger.info("video_id=%s state=ready renditions=%s", job.id, len([n for n in files if n.endswith('index.m3u8')]))
                except Exception as exc:
                    error_type, provider_code = failure_diagnostic(exc)
                    logger.warning('video_id=%s phase=%s error_type=%s provider_code=%s',
                                   identity, job.__dict__.get('processing_stage', 'unknown'), error_type, provider_code)
                    db.rollback()
                    job = db.get(VideoUpload, identity)
                    # Infrastructure errors retry, invalid media fails explicitly.
                    job.status = "failed" if isinstance(exc, InvalidVideo) else "queued"
                    job.error_code = str(exc) if isinstance(exc, InvalidVideo) else "VIDEO_PROCESSING_TEMPORARILY_UNAVAILABLE"
                    job.retry_after = (datetime.now(timezone.utc) + timedelta(seconds=min(300, 30 * 2 ** max(0, job.attempts - 1)))) if job.status == 'queued' else None
                    if job.status == "failed" and job.error_code not in RETRYABLE_PROCESSING_ERRORS:
                        enqueue_source_cleanup(db, job)
                    for name in job.outputs:
                        enqueue_cleanup(db, name)
                    job.outputs = []
                    db.commit()
                    logger.warning("video_id=%s state=%s error_code=%s", identity, job.status, job.error_code)
                    if heartbeat and not isinstance(exc, InvalidVideo):
                        heartbeat.update('waiting_dependencies', identity, job.error_code)
                        return 'waiting_dependencies'
        finally:
            guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})


def main():
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
    Path("/work").mkdir(exist_ok=True)
    heartbeat = WorkerHeartbeat()
    heartbeat.start()
    try:
        while True:
            try:
                with SessionLocal() as db:
                    jobs = db.scalars(select(VideoUpload.id).where(
                        ((VideoUpload.status == 'queued') & ((VideoUpload.retry_after.is_(None)) | (VideoUpload.retry_after <= datetime.now(timezone.utc)))) |
                        (VideoUpload.status == 'processing') |
                        ((VideoUpload.status.in_(["creating", "uploading", "completing", 'failed'])) & (VideoUpload.expires_at < datetime.now(timezone.utc))) |
                        ((VideoUpload.lesson_id.is_(None)) & (~VideoUpload.status.in_(["expired", "superseded", "cancelled"])))).order_by(VideoUpload.created_at).limit(20)).all()
                if not jobs:
                    heartbeat.update('idle')
                for identity in jobs:
                    outcome = process(identity, heartbeat)
                    if outcome != 'waiting_dependencies':
                        heartbeat.update('idle')
            except Exception:
                heartbeat.update('waiting_dependencies')
                logger.warning("Video worker dependency temporarily unavailable")
            time.sleep(5)
    finally:
        heartbeat.stop()


if __name__ == "__main__":
    main()
