"""Check an operator PC's worker dependencies without logging credentials."""

import logging
import os
import shutil
import subprocess
from urllib.parse import parse_qs, urlsplit


def main() -> int:
    # Never print URL/credential values or provider/SQL exception messages.
    required = (
        "DATABASE_URL",
        "S3_ENDPOINT_URL",
        "S3_BUCKET_NAME",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
        "SECRET_KEY",
        "PAYMENT_BANK_DETAILS",
    )
    missing = [key for key in required if not os.getenv(key) or "CHANGE_ME" in os.getenv(key, "")]
    if missing:
        print("Configure these local environment keys: " + ", ".join(missing))
        return 1
    database = urlsplit(os.environ["DATABASE_URL"])
    if database.scheme not in {"postgres", "postgresql", "postgresql+psycopg"} or parse_qs(
        database.query
    ).get("sslmode", [""])[0] not in {"require", "verify-ca", "verify-full"}:
        print("Use the external PostgreSQL URL with sslmode=require or verified TLS.")
        return 1
    endpoint = urlsplit(os.environ["S3_ENDPOINT_URL"])
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.query:
        print("Configure an HTTPS S3 endpoint reachable by this PC and Render.")
        return 1
    logging.getLogger("sqlalchemy.engine").setLevel(logging.CRITICAL)
    try:
        from sqlalchemy import select, text

        from app.core.database import engine
        from app.core.storage import get_storage_provider
        from app.models.video_upload import VideoUpload

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(select(VideoUpload.id).limit(0))
        print("PostgreSQL and video upload table: OK")
        if get_storage_provider().check_readiness().get("status") != "ok":
            print("Storage readiness failed; check the private bucket's read/write/delete access.")
            return 1
        print("Private storage read/write/delete: OK")
        for binary in ("ffmpeg", "ffprobe"):
            subprocess.run(
                [binary, "-version"],
                check=True,
                timeout=15,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if shutil.disk_usage("/work").free < 32 * 1024**3:
            print("Reserve at least 32 GiB free in Docker's /work volume before encoding.")
            return 1
        print("FFmpeg, FFprobe and scratch space: OK")
        return 0
    except Exception as exc:
        print(
            "Worker prerequisite failed ("
            + type(exc).__name__
            + "); inspect configuration without sharing secrets."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
