"""Copy current private file references to S3, verify bytes, then switch DB refs.

Default is a read-only plan. --apply requires all writers stopped. The private
journal is resumable; no original or unreferenced file is ever deleted. This
does not reinstate the removed Knowledge Center or create a public bucket.
"""
import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.storage import LocalStorageProvider, S3StorageProvider, get_storage_provider
from app.models.course import Lesson
from app.models.extended import LessonAsset, ReportJob
from app.models.payment import PaymentOrder
from app.models.platform import AssignmentSubmission
from app.models.transcript import TranscriptionJob
from app.models.video_upload import VideoUpload

FIELDS = [(Lesson, 'video_asset_key'), (LessonAsset, 'object_key'),
          (AssignmentSubmission, 'object_key'), (PaymentOrder, 'receipt_path'),
          (ReportJob, 'object_key'), (TranscriptionJob, 'storage_path'),
          (VideoUpload, 'object_key'), (VideoUpload, 'manifest_key'), (VideoUpload, 'outputs')]


def fingerprint(chunks):
    digest, size = hashlib.sha256(), 0
    for chunk in chunks:
        size += len(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def local_fingerprint(path):
    with path.open('rb') as stream:
        return fingerprint(iter(lambda: stream.read(1024 * 1024), b''))


def write_journal(path, state):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staged = path.with_suffix('.tmp')
    descriptor = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(staged, path)


def migrate(root, journal, *, apply=False, writers_stopped=False):
    root, journal = Path(root).resolve(), Path(journal).resolve()
    if not root.is_dir() or root == root.parent:
        raise ValueError('An existing, explicit local storage root is required')
    if apply and not writers_stopped:
        raise ValueError('Stop API, encoder, cleanup and all other writers before --apply')
    storage = get_storage_provider()
    if not isinstance(storage, S3StorageProvider):
        raise ValueError('Configure the private S3 destination before planning migration')
    state = json.loads(journal.read_text(encoding='utf-8')) if journal.exists() else {
        'version': 1, 'root': str(root), 'bucket': storage.bucket_name,
        'namespace': uuid.uuid4().hex, 'verified': {}, 'updated_references': 0}
    if state.get('version') != 1 or state.get('root') != str(root) or state.get('bucket') != storage.bucket_name:
        raise ValueError('Journal belongs to a different storage root/destination')
    local = LocalStorageProvider(str(root))
    plan, referenced = [], set()
    with SessionLocal() as db:
        if db.scalar(select(VideoUpload.id).where(VideoUpload.status.in_(
                ['creating', 'uploading', 'completing', 'queued', 'processing'])).limit(1)):
            raise ValueError('Finish/cancel active video jobs before migrating local storage')
        for model, field in FIELDS:
            for row in db.scalars(select(model).where(getattr(model, field).is_not(None))).yield_per(250):
                original = getattr(row, field)
                entries = original if field == 'outputs' else [original]
                changes = {}
                for value in entries:
                    if not value or value.startswith(('s3://', 'http://', 'https://', '/api/')):
                        continue
                    # Old static upload paths are admitted only under this
                    # explicit uploads root, never through arbitrary DB paths.
                    lookup = value.removeprefix('/static/uploads/') if value.startswith('/static/uploads/') else value
                    path = Path(local._full_path(lookup))
                    if not path.is_file():
                        raise ValueError(f'Missing local object for {model.__name__}:{row.id}')
                    relative = path.relative_to(root).as_posix()
                    referenced.add(relative)
                    kind = 'video' if path.suffix.lower() in {'.mp4', '.m4v', '.mov', '.webm', '.m3u8', '.ts', '.m4s', '.aac'} else 'files'
                    key = f'legacy-import/{state["namespace"]}/{kind}/{relative}'
                    size, sha = local_fingerprint(path)
                    changes[value] = {'key': key, 'path': path, 'relative': relative, 'size': size, 'sha256': sha}
                if changes:
                    plan.append((model, row.id, field, original, changes))
        if apply:
            # COPY/VERIFY phase completes for the entire set before DB changes.
            # One object at a time; relative HLS paths are kept unchanged.
            for _, _, _, _, changes in plan:
                for item in changes.values():
                    key, expected = item['key'], (item['size'], item['sha256'])
                    if storage.exists(key):
                        if fingerprint(storage.open_stream(key)) != expected:
                            raise ValueError('Destination conflict/checksum mismatch; nothing overwritten')
                    else:
                        storage.save_file(str(item['path']), key, mimetypes.guess_type(item['path'].name)[0])
                        if storage.get_size(key) != item['size'] or fingerprint(storage.open_stream(key)) != expected:
                            raise ValueError('Remote byte verification failed; DB reference unchanged')
                    if local_fingerprint(item['path']) != expected:
                        raise ValueError('Source changed while migrating; stop all writers')
                    state['verified'][item['relative']] = {'key': key, 'size': item['size'], 'sha256': item['sha256']}
                    write_journal(journal, state)
            # All references switch atomically. A crash before commit keeps
            # old refs; after commit a retry sees S3 refs and never uploads twice.
            locked = {}
            for model, identity, field, original, changes in plan:
                row_key = (model, identity)
                if row_key not in locked:
                    locked[row_key] = db.scalar(select(model).where(model.id == identity).with_for_update()
                        .execution_options(populate_existing=True))
                row = locked[row_key]
                if row is None or getattr(row, field) != original:
                    raise ValueError('Database reference changed during copy; aborting switch')
                def replacement(value):
                    if value not in changes:
                        return value
                    key = changes[value]['key']
                    return key if model is VideoUpload else f's3://{storage.bucket_name}/{key}'
                setattr(row, field, [replacement(value) for value in original] if field == 'outputs' else replacement(original))
            db.commit()
            state['updated_references'] += len(plan)
            write_journal(journal, state)
    # Inventory only. Unreferenced files remain intact for separate review.
    unreferenced = sum(1 for path in root.rglob('*') if path.is_file()
                       and path.relative_to(root).as_posix() not in referenced)
    return {'mode': 'applied' if apply else 'plan', 'local_references': len(plan),
            'referenced_files': len(referenced), 'unreferenced_files_preserved': unreferenced,
            'originals_deleted': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-root', required=True)
    parser.add_argument('--journal', required=True, help='Private path outside Git, e.g. backups/storage-migration.json')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--writers-stopped', action='store_true')
    args = parser.parse_args()
    try:
        result = migrate(args.local_root, args.journal, apply=args.apply, writers_stopped=args.writers_stopped)
    except Exception as exc:
        # No DSNs, credentials, object keys or file content on stdout/stderr.
        raise SystemExit(f'Migration stopped ({type(exc).__name__}); original files retained') from None
    print(json.dumps(result))


if __name__ == '__main__':
    main()
