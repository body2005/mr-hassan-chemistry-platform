#!/bin/sh
set -eu

# Docker Compose mounts these files as read-only secrets. Keep credentials out
# of the compose file and URL-encode database credentials before psycopg sees
# them. The child process inherits only the values it needs.
: "${DB_PASSWORD_FILE:?}"
: "${SECRET_KEY_FILE:?}"
: "${S3_SECRET_KEY_FILE:?}"
: "${SMTP_PASSWORD_FILE:?}"
: "${POSTGRES_USER:?}"
: "${POSTGRES_DB:?}"

db_password="$(cat "$DB_PASSWORD_FILE")"
export SECRET_KEY="$(cat "$SECRET_KEY_FILE")"
export S3_SECRET_KEY="$(cat "$S3_SECRET_KEY_FILE")"
export SMTP_PASSWORD="$(cat "$SMTP_PASSWORD_FILE")"
export DATABASE_URL="$(DB_USER="$POSTGRES_USER" DB_NAME="$POSTGRES_DB" DB_PASSWORD="$db_password" python -c 'import os; from urllib.parse import quote; print("postgresql+psycopg://{}:{}@postgres:5432/{}".format(quote(os.environ["DB_USER"], safe=""), quote(os.environ["DB_PASSWORD"], safe=""), quote(os.environ["DB_NAME"], safe="")))')"
unset db_password

exec "$@"
