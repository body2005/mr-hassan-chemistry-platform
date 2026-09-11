#!/usr/bin/env bash
# Restore procedure — ALWAYS test against staging first.
# Usage: ./restore.sh backups/db-20260826T000000Z.sql.gz
set -euo pipefail

FILE="${1:?usage: ./restore.sh <dump.sql.gz>}"
echo "[restore] target: lms_postgres (${POSTGRES_DB:-lms})"
echo "[restore] WARNING: this drops and recreates the database. Ctrl+C to abort."
read -r -p "Type RESTORE to continue: " confirm
[ "$confirm" = "RESTORE" ] || { echo "aborted"; exit 1; }

docker exec -i lms_postgres psql -U "${POSTGRES_USER:-lms}" -d postgres \
  -c "DROP DATABASE IF EXISTS \"${POSTGRES_DB:-lms}\";" \
  -c "CREATE DATABASE \"${POSTGRES_DB:-lms}\";"

gunzip -c "$FILE" | docker exec -i lms_postgres psql -U "${POSTGRES_USER:-lms}" -d "${POSTGRES_DB:-lms}"

echo "[restore] verifying counts..."
docker exec lms_postgres psql -U "${POSTGRES_USER:-lms}" -d "${POSTGRES_DB:-lms}" \
  -c "SELECT count(*) AS users FROM users;" \
  -c "SELECT count(*) AS courses FROM courses;"
echo "[restore] done."
