"""Encrypted, quiesced PostgreSQL + private S3 release snapshots.

Explicit operator command only. Does not prune archives or change bucket policy.
Restore requires a different, empty database and bucket. Keep the encryption
key separately from the archive. No backup/restore runs at import or startup.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import uuid

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.storage import S3StorageProvider, get_storage_provider
from scripts.s3_snapshot import backup as snapshot_objects, restore as restore_objects

MAGIC = b'KCPBK1'


def encryption_key():
    key = base64.b64decode(os.environ['BACKUP_ENCRYPTION_KEY'], validate=True)
    if len(key) != 32:
        raise ValueError('BACKUP_ENCRYPTION_KEY must encode 32 random bytes')
    return key


def db_tool(command, database_url, path):
    url = make_url(database_url)
    if not url.drivername.startswith('postgresql') or not url.database:
        raise ValueError('A PostgreSQL URL is required')
    # Do not pass S3/mail/session/archive encryption keys to PostgreSQL tools.
    env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'TZ', 'HOME',
        'TMPDIR', 'TMP', 'TEMP', 'SYSTEMROOT') if key in os.environ}
    env.update(PGHOST=url.host or '', PGPORT=str(url.port or 5432), PGUSER=url.username or '',
        PGPASSWORD=url.password or '', PGDATABASE=url.database,
        PGSSLMODE=str(url.query.get('sslmode', 'require')), PGCONNECT_TIMEOUT='5')
    args = (['pg_dump', '--format=custom', '--no-owner', '--no-privileges', f'--file={path}']
            if command == 'dump' else ['pg_restore', '--exit-on-error', '--no-owner', '--no-privileges',
                f'--dbname={url.database}', str(path)])
    subprocess.run(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=True, timeout=3600)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def encrypt_bundle(folder, target):
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(encryption_key()), modes.GCM(nonce)).encryptor()
    cipher.authenticate_additional_data(MAGIC)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(MAGIC + nonce)
        class Sink:
            def write(self, data):
                output.write(cipher.update(data))
                return len(data)
        with tarfile.open(fileobj=Sink(), mode='w|') as archive:
            archive.add(folder, arcname='snapshot', recursive=True)
        output.write(cipher.finalize())
        output.write(cipher.tag)
        output.flush()
        os.fsync(output.fileno())


def decrypt_bundle(source, folder):
    # Authenticate the ENTIRE archive before parsing/extracting anything.
    archive_path = folder / 'bundle.tar'
    with source.open('rb') as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise ValueError('Unsupported encrypted snapshot')
        nonce = stream.read(12)
        stream.seek(-16, os.SEEK_END)
        tag = stream.read(16)
        remaining = stream.tell() - 16 - len(MAGIC) - 12
        stream.seek(len(MAGIC) + 12)
        cipher = Cipher(algorithms.AES(encryption_key()), modes.GCM(nonce, tag)).decryptor()
        cipher.authenticate_additional_data(MAGIC)
        with archive_path.open('xb') as output:
            while remaining > 0:
                data = stream.read(min(1024 * 1024, remaining))
                if not data:
                    raise ValueError('Truncated snapshot')
                output.write(cipher.update(data))
                remaining -= len(data)
            output.write(cipher.finalize())
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        if len(members) > 250000:
            raise ValueError('Snapshot member budget exceeded')
        for member in members:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0] != 'snapshot'
                    or '\\' in member.name or not (member.isdir() or member.isfile())):
                raise ValueError('Unsafe snapshot member')
        archive.extractall(folder, members=members, filter='data')
    snapshot = folder / 'snapshot'
    release = json.loads((snapshot / 'release.json').read_text(encoding='utf-8'))
    if sha256(snapshot / 'database.dump') != release['database_sha256']:
        raise ValueError('Database archive checksum mismatch')
    from scripts.s3_snapshot import read_manifest, consume
    manifest = read_manifest(snapshot / 'objects')
    for item in manifest['objects']:
        with (snapshot / 'objects' / 'objects' / item['file']).open('rb') as stream:
            if consume(stream) != (item['size'], item['sha256']):
                raise ValueError('Object payload checksum mismatch')
    return snapshot, release


def create_backup(directory, source_sha, retention_days, writers_stopped):
    if not writers_stopped:
        raise ValueError('Quiesce ALL API/video/cleanup/mail/schedule writers before snapshotting')
    if len(source_sha) != 40 or any(char not in '0123456789abcdef' for char in source_sha):
        raise ValueError('An explicit immutable release SHA is required')
    encryption_key()  # Validate before allocating work or invoking providers.
    storage = get_storage_provider()
    if not isinstance(storage, S3StorageProvider):
        raise ValueError('This snapshot requires the current private object store')
    destination = Path(directory).resolve()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='private-snapshot-', dir=destination) as temporary:
        root = Path(temporary)
        db_tool('dump', get_settings().sqlalchemy_database_url, root / 'database.dump')
        database = create_engine(get_settings().sqlalchemy_database_url, connect_args={'connect_timeout': 5})
        try:
            with database.connect() as connection:
                revision = list(connection.scalars(text('SELECT version_num FROM alembic_version')))
        finally:
            database.dispose()
        object_snapshot = snapshot_objects(storage._get_client(), storage.bucket_name, root / 'object-staging')
        object_snapshot.rename(root / 'objects')
        release = {'version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
            'source_sha': source_sha, 'schema_revisions': revision, 'database_sha256': sha256(root / 'database.dump'),
            'source_bucket': storage.bucket_name, 'retention_days': retention_days,
            'consistency': 'operator-confirmed all-writer quiescence; pg_dump snapshot + verified object snapshot',
            'encryption': 'AES-256-GCM; key stored separately; no automatic pruning'}
        (root / 'release.json').write_text(json.dumps(release), encoding='utf-8')
        target = destination / f'{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}.enc'
        # Exclude the emptied staging directory; no source data is removed.
        encrypt_bundle(root, target)
    return {'archive': str(target), 'sha256': sha256(target), 'source_sha': source_sha}


def restore_backup(source, work_dir):
    source_url, target = make_url(get_settings().sqlalchemy_database_url), make_url(os.environ['RESTORE_DATABASE_URL'])
    if target.drivername in {'postgres', 'postgresql'}:
        target = target.set(drivername='postgresql+psycopg')
    target_url = target
    if (source_url.host, source_url.port or 5432, source_url.database) == (target.host, target.port or 5432, target.database):
        raise ValueError('Restore database must differ from the source')
    provider = S3StorageProvider(endpoint_url=os.environ['RESTORE_S3_ENDPOINT_URL'],
        bucket_name=os.environ['RESTORE_S3_BUCKET_NAME'], access_key_id=os.environ['RESTORE_S3_ACCESS_KEY_ID'],
        secret_access_key=os.environ['RESTORE_S3_SECRET_ACCESS_KEY'], region_name=os.getenv('RESTORE_S3_REGION', 'auto'))
    with tempfile.TemporaryDirectory(prefix='private-restore-', dir=work_dir) as temporary:
        snapshot, release = decrypt_bundle(Path(source), Path(temporary))
        if provider.bucket_name == release['source_bucket']:
            raise ValueError('Restore bucket must have a distinct name')
        # Require existing empty targets; this command never creates/deletes DBs
        # or changes bucket ACL/IAM. A failed restore leaves only NEW targets.
        provider._get_client().head_bucket(Bucket=provider.bucket_name)
        if provider._get_client().list_objects_v2(Bucket=provider.bucket_name, MaxKeys=1).get('KeyCount', 0):
            raise ValueError('Restore bucket is not empty')
        engine = create_engine(target_url, connect_args={'connect_timeout': 5})
        try:
            if inspect(engine).get_table_names():
                raise ValueError('Restore database is not empty')
            restore_objects(provider._get_client(), provider.bucket_name, snapshot / 'objects')
            db_tool('restore', target_url, snapshot / 'database.dump')
            # Only the NEW database is rewritten; keys relative to bucket
            # (HLS allowlists) remain identical. Never point restores at originals.
            from scripts.migrate_private_storage import FIELDS
            from app.models.storage_cleanup import StorageCleanup
            with engine.begin() as connection:
                inspector = inspect(connection)
                tables = set(inspector.get_table_names())
                for model, field in [*FIELDS, (StorageCleanup, 'object_key')]:
                    table = model.__tablename__
                    if field == 'outputs' or table not in tables or field not in {col['name'] for col in inspector.get_columns(table)}:
                        continue
                    old, new = f's3://{release["source_bucket"]}/', f's3://{provider.bucket_name}/'
                    connection.execute(text(f'UPDATE "{table}" SET "{field}" = :new || substr("{field}", :offset) '
                        f'WHERE "{field}" LIKE :prefix'), {'new': new, 'offset': len(old) + 1, 'prefix': old + '%'})
        finally:
            engine.dispose()
    return {'restored_source_sha': release['source_sha'], 'target': 'new isolated stores',
            'runtime_validation': 'required; not performed by restore'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'verify', 'restore'])
    parser.add_argument('--directory', required=True, help='Private encrypted volume outside Git with enough free disk')
    parser.add_argument('--source-sha')
    parser.add_argument('--archive')
    parser.add_argument('--writers-stopped', action='store_true')
    parser.add_argument('--retention-days', type=int, default=30, choices=range(1, 366))
    args = parser.parse_args()
    if args.action in {'verify', 'restore'} and not args.archive:
        parser.error('--archive is required for verification/restore')
    os.umask(0o077)
    try:
        if args.action == 'backup':
            result = create_backup(args.directory, args.source_sha or '', args.retention_days, args.writers_stopped)
        elif args.action == 'restore':
            result = restore_backup(args.archive, args.directory)
        else:
            with tempfile.TemporaryDirectory(prefix='private-verify-', dir=args.directory) as folder:
                _, release = decrypt_bundle(Path(args.archive), Path(folder))
                result = {'authenticated_snapshot': True, 'source_sha': release['source_sha'],
                          'runtime_restore_verified': False}
    except Exception as exc:
        raise SystemExit(f'Snapshot operation stopped ({type(exc).__name__}); no existing store removed') from None
    print(json.dumps(result))


if __name__ == '__main__':
    main()
