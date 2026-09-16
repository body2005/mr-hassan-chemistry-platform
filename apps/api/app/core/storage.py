"""
Storage Abstraction Layer.
Supports local filesystem storage (development & persistent disk) and
S3-compatible object storage (Cloudflare R2, AWS S3, MinIO) for production.
"""
from __future__ import annotations

import io
import logging
import os
import re
import shutil
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, BinaryIO, Generator

logger = logging.getLogger(__name__)


def generate_safe_object_key(prefix: str, original_filename: str) -> str:
    """Generates a non-conflicting, traversal-safe object key."""
    ext = os.path.splitext(original_filename)[1].lower()
    clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", os.path.basename(original_filename))
    uid = uuid.uuid4().hex[:12]
    clean_prefix = prefix.strip("/\\")
    return f"{clean_prefix}/{uid}_{clean_name}"


class BaseStorageProvider(ABC):
    @abstractmethod
    def save_file(self, local_source_path: str, storage_key: str, content_type: str | None = None) -> str:
        """Saves a file from a local path to storage. Returns the canonical storage path / key."""
        pass

    @abstractmethod
    def save_bytes(self, data: bytes, storage_key: str, content_type: str | None = None) -> str:
        """Saves raw bytes to storage. Returns the canonical storage path / key."""
        pass

    @abstractmethod
    def get_local_path(self, storage_key: str) -> str | None:
        """Returns a local filesystem path if available, or None if remote-only."""
        pass

    @abstractmethod
    def open_stream(self, storage_key: str, start: int = 0, length: int | None = None) -> Generator[bytes, None, None]:
        """Streams bytes for the given storage key supporting byte-range requests."""
        pass

    @abstractmethod
    def get_size(self, storage_key: str) -> int:
        """Returns the file size in bytes."""
        pass

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Checks if a file exists in storage."""
        pass

    @abstractmethod
    def delete(self, storage_key: str) -> bool:
        """Deletes a file from storage."""
        pass

    @abstractmethod
    def generate_presigned_url(self, storage_key: str, expires_in: int = 1800) -> str | None:
        """Generates a presigned download/view URL if supported by the provider."""
        pass

    @abstractmethod
    def check_readiness(self) -> dict[str, str | bool]:
        """Performs a lightweight health/readiness check without leaking secrets."""
        pass


class LocalStorageProvider(BaseStorageProvider):
    def __init__(self, base_dir: str | None = None):
        self.base_dir = os.path.abspath(base_dir or os.getenv("STORAGE_DIR", "storage"))
        os.makedirs(self.base_dir, exist_ok=True)
        self.is_production = os.getenv("APP_ENV", "").lower() == "production"
        self.is_persistent_mount = (
            self.base_dir.startswith("/var/data")
            or os.path.ismount(self.base_dir)
            or bool(os.getenv("RENDER_DISK_PATH"))
        )
        if self.is_production and not self.is_persistent_mount:
            logger.warning(
                "WARNING: Storage is using local directory '%s' in production without a verified "
                "persistent disk mount. Files may be lost across restarts or redeployments. "
                "Configure S3/R2 object storage or attach a Render Persistent Disk.",
                self.base_dir,
            )

    def _full_path(self, storage_key: str) -> str:
        if os.path.exists(storage_key):
            return os.path.abspath(storage_key)
        norm = os.path.normpath(storage_key).lstrip("/\\")
        base_name = os.path.basename(self.base_dir.rstrip("/\\"))
        parts = norm.split(os.sep)
        if parts and parts[0] == base_name:
            norm = os.sep.join(parts[1:])
        if ".." in norm.split(os.sep):
            raise ValueError(f"Invalid storage key with traversal: {storage_key}")
        return os.path.join(self.base_dir, norm)

    def save_file(self, local_source_path: str, storage_key: str, content_type: str | None = None) -> str:
        dest_path = self._full_path(storage_key)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        if os.path.abspath(local_source_path) != os.path.abspath(dest_path):
            shutil.copy2(local_source_path, dest_path)
        return dest_path

    def save_bytes(self, data: bytes, storage_key: str, content_type: str | None = None) -> str:
        dest_path = self._full_path(storage_key)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        return dest_path

    def get_local_path(self, storage_key: str) -> str | None:
        if os.path.exists(storage_key):
            return os.path.abspath(storage_key)
        path = self._full_path(storage_key)
        return path if os.path.exists(path) else None

    def open_stream(self, storage_key: str, start: int = 0, length: int | None = None) -> Generator[bytes, None, None]:
        path = self.get_local_path(storage_key) or self._full_path(storage_key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Storage file not found: {path}")
        chunk_size = 64 * 1024
        bytes_remaining = length
        with open(path, "rb") as f:
            if start > 0:
                f.seek(start)
            while True:
                if bytes_remaining is not None and bytes_remaining <= 0:
                    break
                read_len = chunk_size if bytes_remaining is None else min(chunk_size, bytes_remaining)
                chunk = f.read(read_len)
                if not chunk:
                    break
                if bytes_remaining is not None:
                    bytes_remaining -= len(chunk)
                yield chunk

    def get_size(self, storage_key: str) -> int:
        if os.path.exists(storage_key):
            return os.path.getsize(storage_key)
        path = self.get_local_path(storage_key) or self._full_path(storage_key)
        return os.path.getsize(path)

    def exists(self, storage_key: str) -> bool:
        if os.path.exists(storage_key):
            return True
        path = self.get_local_path(storage_key) or self._full_path(storage_key)
        return os.path.exists(path)

    def delete(self, storage_key: str) -> bool:
        if os.path.exists(storage_key):
            try:
                os.remove(storage_key)
                return True
            except OSError:
                return False
        path = self.get_local_path(storage_key) or self._full_path(storage_key)
        if os.path.exists(path):
            try:
                os.remove(path)
                return True
            except OSError:
                return False
        return False

    def generate_presigned_url(self, storage_key: str, expires_in: int = 300) -> str | None:
        return None

    def check_readiness(self) -> dict[str, str | bool]:
        now = time.time()
        if hasattr(self, "_probe_cache") and self._probe_cache and (now - self._probe_cache[0]) < 45.0:
            return self._probe_cache[1]

        test_file = os.path.join(self.base_dir, f".readiness_probe_{uuid.uuid4().hex[:6]}.tmp")
        try:
            with open(test_file, "w") as f:
                f.write("probe")
            with open(test_file, "r") as f:
                content = f.read()
            os.remove(test_file)
            is_ok = content == "probe"
        except Exception:
            is_ok = False

        status_str = "ok" if is_ok else "unavailable"
        if is_ok and self.is_production and not self.is_persistent_mount:
            status_str = "ephemeral_warning"

        res = {
            "provider": "local_filesystem",
            "status": status_str,
            "writable": is_ok,
            "persistent": self.is_persistent_mount,
        }
        self._probe_cache = (now, res)
        return res


class S3StorageProvider(BaseStorageProvider):
    def __init__(
        self,
        endpoint_url: str | None = None,
        bucket_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region_name: str = "auto",
    ):
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME", os.getenv("S3_BUCKET", "learning-website"))
        self.access_key_id = access_key_id or os.getenv("S3_ACCESS_KEY_ID", os.getenv("S3_ACCESS_KEY"))
        self.secret_access_key = secret_access_key or os.getenv("S3_SECRET_ACCESS_KEY", os.getenv("S3_SECRET_KEY"))
        self.region_name = region_name or os.getenv("S3_REGION", "auto")
        self._client = None
        self._probe_cache: tuple[float, dict[str, Any]] | None = None

    def _get_client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            is_path_style = bool(re.search(r"minio|localhost|127\.0\.0\.1|:\d+", self.endpoint_url or ""))
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region_name,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path" if is_path_style else "virtual"},
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )
        return self._client

    def save_file(self, local_source_path: str, storage_key: str, content_type: str | None = None) -> str:
        client = self._get_client()
        extra_args: dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type

        # Multipart threshold 8MB with bounded concurrency and auto abort on failure
        from boto3.s3.transfer import TransferConfig
        transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,
            max_concurrency=4,
            multipart_chunksize=8 * 1024 * 1024,
            use_threads=True,
        )
        client.upload_file(
            local_source_path,
            self.bucket_name,
            storage_key,
            ExtraArgs=extra_args,
            Config=transfer_config,
        )
        return f"s3://{self.bucket_name}/{storage_key}"

    def save_bytes(self, data: bytes, storage_key: str, content_type: str | None = None) -> str:
        client = self._get_client()
        extra_args: dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        client.put_object(Bucket=self.bucket_name, Key=storage_key, Body=data, **extra_args)
        return f"s3://{self.bucket_name}/{storage_key}"

    def get_local_path(self, storage_key: str) -> str | None:
        return None

    def open_stream(self, storage_key: str, start: int = 0, length: int | None = None) -> Generator[bytes, None, None]:
        client = self._get_client()
        key = storage_key.replace(f"s3://{self.bucket_name}/", "")
        range_header = f"bytes={start}-"
        if length is not None:
            range_header = f"bytes={start}-{start + length - 1}"
        response = client.get_object(Bucket=self.bucket_name, Key=key, Range=range_header)
        stream: BinaryIO = response["Body"]
        while chunk := stream.read(64 * 1024):
            yield chunk

    def get_size(self, storage_key: str) -> int:
        client = self._get_client()
        key = storage_key.replace(f"s3://{self.bucket_name}/", "")
        response = client.head_object(Bucket=self.bucket_name, Key=key)
        return response.get("ContentLength", 0)

    def exists(self, storage_key: str) -> bool:
        client = self._get_client()
        key = storage_key.replace(f"s3://{self.bucket_name}/", "")
        try:
            client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def delete(self, storage_key: str) -> bool:
        client = self._get_client()
        key = storage_key.replace(f"s3://{self.bucket_name}/", "")
        try:
            client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def generate_presigned_url(self, storage_key: str, expires_in: int = 300) -> str | None:
        """Generates a private, short-lived (default 5 minutes) signed URL for viewing/downloading."""
        client = self._get_client()
        key = storage_key.replace(f"s3://{self.bucket_name}/", "")
        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except Exception:
            logger.exception("Failed to generate presigned S3 URL")
            return None

    def check_readiness(self) -> dict[str, str | bool]:
        """
        Active probe performing write, read, and delete of a temporary test object.
        Result is cached for 45 seconds to avoid repeated external I/O on rapid readiness polls.
        """
        now = time.time()
        if self._probe_cache and (now - self._probe_cache[0]) < 45.0:
            return self._probe_cache[1]

        probe_key = f".probes/readiness_{uuid.uuid4().hex[:8]}.tmp"
        try:
            client = self._get_client()
            # 1. Write probe object
            client.put_object(Bucket=self.bucket_name, Key=probe_key, Body=b"storage_readiness_probe")
            # 2. Read probe object
            obj = client.get_object(Bucket=self.bucket_name, Key=probe_key)
            data = obj["Body"].read()
            if data != b"storage_readiness_probe":
                raise ValueError("Probe data mismatch")
            # 3. Clean up probe object
            client.delete_object(Bucket=self.bucket_name, Key=probe_key)

            res = {
                "provider": "s3_object_storage",
                "status": "ok",
                "writable": True,
                "persistent": True,
            }
            self._probe_cache = (now, res)
            return res
        except Exception as exc:
            try:
                # Cleanup attempt on error
                client.delete_object(Bucket=self.bucket_name, Key=probe_key)
            except Exception:
                pass
            res = {
                "provider": "s3_object_storage",
                "status": "unavailable",
                "error": str(exc).split(":")[0],
                "writable": False,
                "persistent": True,
            }
            self._probe_cache = (now, res)
            return res


_storage_instance: BaseStorageProvider | None = None


def get_storage_provider() -> BaseStorageProvider:
    global _storage_instance
    if _storage_instance is None:
        from app.core.config import get_settings
        settings = get_settings()
        backend = (settings.storage_backend or os.getenv("STORAGE_BACKEND", "")).lower()
        if backend == "local":
            _storage_instance = LocalStorageProvider()
            return _storage_instance

        use_s3 = (
            backend in {"s3", "r2", "minio"}
            or os.getenv("USE_S3_STORAGE", "").lower() in {"1", "true", "yes"}
            or bool(
                (settings.s3_endpoint_url or os.getenv("S3_ENDPOINT_URL"))
                and (
                    settings.s3_access_key
                    or os.getenv("S3_ACCESS_KEY_ID")
                    or os.getenv("S3_ACCESS_KEY")
                )
                and (
                    settings.s3_secret_key
                    or os.getenv("S3_SECRET_ACCESS_KEY")
                    or os.getenv("S3_SECRET_KEY")
                )
            )
        )
        if use_s3:
            try:
                _storage_instance = S3StorageProvider(
                    endpoint_url=settings.s3_endpoint_url,
                    bucket_name=settings.s3_bucket,
                    access_key_id=settings.s3_access_key,
                    secret_access_key=settings.s3_secret_key,
                )
            except Exception as e:
                logger.warning("Failed to initialize S3 storage provider (%s); falling back to local storage.", e)
                _storage_instance = LocalStorageProvider()
        else:
            _storage_instance = LocalStorageProvider()
    return _storage_instance


# Alias for backward compatibility
get_storage = get_storage_provider
