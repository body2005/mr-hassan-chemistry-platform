#!/usr/bin/env bash
# PostgreSQL + object-storage backup script.
# Usage: ./backup.sh  (cron recommended: daily off-hours)
set -euo pipefail

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
mkdir -p "$BACKUP_ROOT"

echo "[backup] dumping PostgreSQL..."
docker exec lms_postgres pg_dump -U "${POSTGRES_USER:-lms}" "${POSTGRES_DB:-lms}" \
  | gzip > "$BACKUP_ROOT/db-$STAMP.sql.gz"

echo "[backup] archiving MinIO buckets..."
docker run --rm --network infra_default \
  -v "$BACKUP_ROOT:/backup" \
  -e MC_HOST_local="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@minio:9000" \
  minio/mc mirror local "/backup/storage-$STAMP" >/dev/null

echo "[backup] pruning archives older than 30 days..."
find "$BACKUP_ROOT" -name "*.gz" -mtime +30 -delete

echo "[backup] done: $BACKUP_ROOT"
