"""
Safe, idempotent migration CLI for copying local knowledge files to Cloudflare R2 / S3 storage.
Default mode: Copy-only.
Verification: Computes SHA-256 and byte size before updating DB.
Original files are ONLY removed if --delete-source-after-verification is explicitly passed.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import uuid
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_storage")

# Ensure apps/api is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.storage import S3StorageProvider, generate_safe_object_key, get_storage_provider
from app.models.knowledge_center import KnowledgeSource


def compute_file_sha256(filepath: str) -> tuple[int, str]:
    hasher = hashlib.sha256()
    size = 0
    with open(filepath, "rb") as f:
        while chunk := f.read(64 * 1024):
            size += len(chunk)
            hasher.update(chunk)
    return size, hasher.hexdigest()


def migrate_sources_to_s3(delete_source_after_verification: bool = False, dry_run: bool = False) -> dict[str, Any]:
    storage = get_storage_provider()
    if not isinstance(storage, S3StorageProvider):
        logger.error("Storage backend is not S3/R2. Please configure STORAGE_BACKEND=s3 and S3 credentials before running migration.")
        return {"migrated": 0, "failed": 0, "skipped": 0, "error": "Storage backend is not S3"}

    stats = {"migrated": 0, "skipped": 0, "failed": 0, "deleted_locals": 0}

    with SessionLocal() as db:
        sources = db.scalars(select(KnowledgeSource)).all()
        logger.info("Found %d knowledge sources in database to evaluate for migration.", len(sources))

        for src in sources:
            current_path = src.storage_path
            # Check if already migrated to S3
            if current_path and current_path.startswith("s3://"):
                logger.info("Source %s (%s) already on S3: %s", src.id, src.filename, current_path)
                stats["skipped"] += 1
                continue

            # Determine local path
            if not current_path or not os.path.exists(current_path):
                logger.warning("Source %s (%s) local file missing at '%s'; skipping.", src.id, src.filename, current_path)
                stats["failed"] += 1
                continue

            local_size, local_hash = compute_file_sha256(current_path)
            prefix = f"knowledge_center/courses/{src.course_id}"
            object_key = generate_safe_object_key(prefix, src.filename)

            logger.info("Migrating source %s (%s) -> s3 key: %s (size: %d bytes)", src.id, src.filename, object_key, local_size)

            if dry_run:
                logger.info("[DRY RUN] Would upload %s and update DB.", current_path)
                stats["migrated"] += 1
                continue

            try:
                # 1. Upload to S3/R2
                s3_uri = storage.save_file(
                    local_source_path=current_path,
                    storage_key=object_key,
                    content_type=src.mime_type,
                )

                # 2. Verify on S3 (head_object / size check)
                s3_size = storage.get_size(s3_uri)
                if s3_size != local_size:
                    raise ValueError(f"Size mismatch after upload: local={local_size}, s3={s3_size}")

                # Verify byte stream SHA-256 from S3
                remote_hasher = hashlib.sha256()
                for chunk in storage.open_stream(s3_uri):
                    remote_hasher.update(chunk)
                remote_hash = remote_hasher.hexdigest()
                if remote_hash != local_hash:
                    raise ValueError(f"SHA-256 mismatch after upload: local={local_hash}, s3={remote_hash}")

                # 3. Update database record with verified S3 path
                src.storage_path = s3_uri
                src.size_bytes = local_size
                src.checksum = local_hash
                db.commit()
                stats["migrated"] += 1
                logger.info("Successfully migrated source %s to %s", src.id, s3_uri)

                # 4. Optional removal only if verified and explicitly requested
                if delete_source_after_verification:
                    os.remove(current_path)
                    stats["deleted_locals"] += 1
                    logger.info("Deleted local source file after successful verification: %s", current_path)

            except Exception as exc:
                logger.exception("Failed to migrate source %s (%s): %s", src.id, src.filename, exc)
                db.rollback()
                stats["failed"] += 1

    logger.info("Migration complete: %s", stats)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate local storage files to S3/R2")
    parser.add_argument(
        "--delete-source-after-verification",
        action="store_true",
        help="Delete original local files ONLY after successful upload, size check, and SHA-256 verification",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without uploading or modifying DB",
    )
    args = parser.parse_args()

    migrate_sources_to_s3(
        delete_source_after_verification=args.delete_source_after_verification,
        dry_run=args.dry_run,
    )
