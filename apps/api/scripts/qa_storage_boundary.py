"""Reproduce S3 save_file at the actual video limit in isolated QA only."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from app.core.storage import get_storage_provider
from app.core.upload_limits import MAX_VIDEO_BYTES


def main():
    if os.getenv('QA_ISOLATED') != 'true' or os.getenv('QA_PROJECT') != 'chemistryaudit2':
        raise SystemExit('Isolated local QA only')
    storage = get_storage_provider()
    key = f'qa-boundary/{uuid.uuid4().hex}.webm'
    with tempfile.TemporaryDirectory(prefix='qa-s3-boundary-') as folder:
        source = Path(folder)/'boundary.webm'
        shutil.copyfile(Path(os.environ['QA_MEDIA_DIR'])/'video.webm', source)
        remaining = MAX_VIDEO_BYTES-source.stat().st_size-9
        with source.open('ab') as stream:
            stream.write(b'\xec'+(remaining | (1 << 56)).to_bytes(8, 'big'))
            stream.truncate(MAX_VIDEO_BYTES)
        try:
            storage.save_file(str(source), key, 'video/webm')
            assert storage.get_size(key) == MAX_VIDEO_BYTES
            digest = hashlib.sha256()
            for chunk in storage.open_stream(key):
                digest.update(chunk)
            with source.open('rb') as stream:
                assert digest.hexdigest() == hashlib.file_digest(stream, 'sha256').hexdigest()
            print(json.dumps({'bytes': MAX_VIDEO_BYTES, 'saved_and_hash_verified': True}))
        except Exception as exc:
            # Never publish signed URLs/credentials or raw response bodies.
            diagnostic = re.sub(r'https?://\S+', '[redacted-url]', str(exc))
            print(json.dumps({'error_type': type(exc).__name__, 'diagnostic': diagnostic[:1000]}))
            raise SystemExit(1)
        finally:
            storage.delete(key)


if __name__ == '__main__':
    main()
