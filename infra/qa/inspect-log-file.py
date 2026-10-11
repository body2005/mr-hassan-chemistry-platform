"""Archive/inspect ONE explicitly mounted QA daemon log, without printing logs.

Stop the affected QA container first for a consistent forensic copy. Never
modify the daemon file; recreate the container only after retaining evidence.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

if os.getenv('QA_ISOLATED') != 'true' or os.getenv('QA_PROJECT') not in {'chemistryaudit2', 'chemistryprodlocal'}:
    raise SystemExit('Only explicitly isolated QA log archives are permitted')
parser = argparse.ArgumentParser(__doc__)
parser.add_argument('--service', choices=['api','web','proxy','worker','video-worker','s3','postgres','redis','upload-gateway','mailpit'], default='api')
parser.add_argument('--inspect-only', action='store_true')
args = parser.parse_args()
source = Path('/source-log')
folder = Path('/qa/log-evidence')
folder.mkdir(exist_ok=True)
name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
target = folder / f'{args.service}-{name}.jsonl'
if args.inspect_only:
    target = source
else:
    with source.open('rb') as reader, target.open('xb') as writer:
        shutil.copyfileobj(reader, writer, 1024 * 1024)
bad, count, offset, first, last = [], 0, 0, None, None
digest = hashlib.sha256()
with target.open('rb') as reader:
    for line in reader:
        digest.update(line)
        try:
            value = json.loads(line)
            first = first or value.get('time')
            last = value.get('time')
            count += 1
        except (ValueError, UnicodeDecodeError):
            bad.append({'offset': offset, 'bytes': len(line), 'null_bytes': line.count(b'\0'),
                        'sha256': hashlib.sha256(line).hexdigest()})
        offset += len(line)
report = {'service': args.service, 'archive': None if args.inspect_only else str(target), 'sha256': digest.hexdigest(), 'bytes': target.stat().st_size,
          'valid_records': count, 'bad_records': bad, 'bad_count': len(bad),
          'first_timestamp': first, 'last_timestamp': last}
if not args.inspect_only:
    (folder / f'{args.service}-{name}-inspection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
