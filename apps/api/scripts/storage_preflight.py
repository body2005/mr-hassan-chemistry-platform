"""Validate configured private object storage without printing credentials.

Run from apps/api: python -m scripts.storage_preflight
Writes, reads and removes a uniquely named readiness object only.
"""
import logging
import os
from urllib.parse import urlsplit


def main() -> int:
    required = ("S3_ENDPOINT_URL", "S3_BUCKET_NAME", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
    missing = [name for name in required if not os.getenv(name) or "CHANGE_ME" in os.getenv(name, "")]
    if missing:
        print("Missing environment keys: " + ", ".join(missing))
        return 1
    if os.getenv("STORAGE_BACKEND", "").lower() not in {"s3", "r2"}:
        print("Set STORAGE_BACKEND=s3 before checking production storage.")
        return 1
    endpoint = urlsplit(os.environ["S3_ENDPOINT_URL"])
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username
            or endpoint.password or endpoint.query or endpoint.fragment or endpoint.path not in {"", "/"}):
        print("Use the HTTPS S3 API origin without a bucket path or credentials.")
        return 1
    # Initialize only storage; no database access, migrations or session keys.
    logging.getLogger("botocore").setLevel(logging.CRITICAL)
    try:
        from app.core.storage import S3StorageProvider
        provider = S3StorageProvider(
            endpoint_url=os.environ["S3_ENDPOINT_URL"],
            bucket_name=os.environ["S3_BUCKET_NAME"],
            access_key_id=os.environ["S3_ACCESS_KEY_ID"],
            secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
            region_name=os.getenv("S3_REGION", "auto"),
        )
        if provider.check_readiness().get("status") != "ok":
            print("Storage check failed. Verify private bucket read/write/delete permissions and connectivity.")
            return 1
        print("Private object storage read/write/delete: OK")
        return 0
    except Exception:
        print("Storage check failed. No credential values have been printed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
