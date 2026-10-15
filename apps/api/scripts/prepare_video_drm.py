"""Prepare existing originals for encrypted replacement; no work by default.

Run only after provider/device validation in staging and an approved rollout.
This script was added as source, not executed. It never enables a setting.
"""
import argparse
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.storage import S3StorageProvider, get_storage_provider
from app.core.upload_limits import MAX_VIDEO_BYTES
from app.models.course import Course, Lesson, LessonKind
from app.models.video_upload import VideoUpload
from app.services.video_drm import communication_key, fairplay_certificate
from app.services.video_uploads import ACTIVE_STATES, EXTENSIONS


def main():
    parser = argparse.ArgumentParser(description='Plan or enqueue encrypted replacements from private originals')
    parser.add_argument('--lesson', action='append', type=uuid.UUID)
    parser.add_argument('--all', action='store_true', help='Include every native video lesson')
    parser.add_argument('--enqueue', action='store_true', help='Commit bounded queue intents; otherwise report IDs/status only')
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    if not args.lesson and not args.all:
        parser.error('Choose explicit --lesson IDs or --all')
    if not 1 <= args.limit <= 100:
        parser.error('limit must be between 1 and 100')
    provider = get_storage_provider()
    if not isinstance(provider, S3StorageProvider):
        parser.error('Private object storage is required')
    if args.enqueue:
        if not get_settings().video_processing_enabled:
            parser.error('A configured video worker is required')
        communication_key()
        fairplay_certificate()
    with SessionLocal() as db:
        query = select(Lesson).where(Lesson.kind == LessonKind.VIDEO).order_by(Lesson.id)
        if args.lesson:
            query = query.where(Lesson.id.in_(args.lesson))
        # Lock only when mutating. The lesson lock serializes queue planning;
        # every job records the exact source generation it may replace.
        if args.enqueue:
            query = query.with_for_update(skip_locked=True)
        planned = 0
        for lesson in db.scalars(query):
            if lesson.video_drm_protected:
                print(f'{lesson.id} already-protected')
                continue
            key = lesson.video_asset_key or ''
            if not key or key.startswith(('http://', 'https://')):
                print(f'{lesson.id} needs-private-original')
                continue
            if db.scalar(select(VideoUpload.id).where(VideoUpload.lesson_id == lesson.id, VideoUpload.status.in_(ACTIVE_STATES)).limit(1)):
                print(f'{lesson.id} preparation-active')
                continue
            ready = db.scalar(select(VideoUpload).where(VideoUpload.lesson_id == lesson.id,
                VideoUpload.status == 'ready').order_by(VideoUpload.created_at.desc()).limit(1))
            original = ready.object_key if ready and ready.manifest_key and key.endswith('/' + ready.manifest_key) else None
            bucket_prefix = f's3://{provider.bucket_name}/'
            if not original and key.startswith(bucket_prefix) and not key.endswith('.m3u8'):
                original = key[len(bucket_prefix):]
            if not original:
                print(f'{lesson.id} needs-private-original')
                continue
            filename = ready.filename if ready else original.rsplit('/', 1)[-1]
            extension = '.' + filename.rsplit('.', 1)[-1].lower()
            if extension not in EXTENSIONS:
                print(f'{lesson.id} unsupported-original')
                continue
            # Planning is read-only. Storage size/existence is checked before
            # enqueue; no source object is changed or made public.
            try:
                size = provider.get_size(original) if args.enqueue else (ready.size_bytes if ready else None)
            except FileNotFoundError:
                print(f'{lesson.id} needs-private-original')
                continue
            if args.enqueue and not 0 < size <= MAX_VIDEO_BYTES:
                print(f'{lesson.id} original-size-not-supported')
                continue
            if args.enqueue:
                identity = uuid.uuid4()
                course = db.get(Course, lesson.course_id)
                job = VideoUpload(id=identity, lesson_id=lesson.id, owner_id=ready.owner_id if ready else course.teacher_id,
                    request_key=identity.hex, filename=filename, content_type=EXTENSIONS[extension], size_bytes=size,
                    fingerprint=hashlib.sha256(original.encode()).hexdigest(), object_key=original,
                    status='queued', outputs=[], expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
                    drm={'requested': True, 'replaces': key})
                db.add(job)
                db.flush()
            print(f'{lesson.id} {"queued" if args.enqueue else "eligible"}')
            planned += 1
            if planned >= args.limit:
                break
        if args.enqueue:
            db.commit()


if __name__ == '__main__':
    main()
