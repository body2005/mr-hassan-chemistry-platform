#!/bin/sh
set -eu
# One-shot metadata migration only. Never recurse into existing snapshots,
# follow a symlink, read secrets or grant the long-running API root access.
if [ ! -d /backups ] || [ -L /backups ] || [ "$(readlink -f /backups)" != /backups ]; then
    echo 'Backup root must be the explicit mounted directory' >&2
    exit 1
fi
if [ -L /backups/s3 ] || { [ -e /backups/s3 ] && [ ! -d /backups/s3 ]; }; then
    echo 'Refusing symlink or non-directory S3 backup target' >&2
    exit 1
fi
mkdir -p /backups/s3
[ "$(readlink -f /backups/s3)" = /backups/s3 ] || exit 1
chown 10001:10001 /backups /backups/s3
chmod 0750 /backups /backups/s3
echo 'Backup directories owned by UID 10001; existing snapshot contents untouched'
