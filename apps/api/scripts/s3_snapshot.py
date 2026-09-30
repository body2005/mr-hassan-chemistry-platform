"""Provider-neutral private S3 snapshots. Quiesce writers for a consistent DB/S3 backup.

No secrets in manifests, no object keys used as filesystem paths, no destructive
restore or ACL copying. Restore refuses a nonempty destination. Supports MinIO
to SeaweedFS migration via S3, never by sharing their incompatible volumes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

import boto3
from botocore.config import Config

METADATA = ("ContentType", "ContentDisposition", "ContentEncoding", "CacheControl", "Metadata")


def client():
    return boto3.client(
        "s3", endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.getenv("S3_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      connect_timeout=3, read_timeout=30,
                      retries={"total_max_attempts": 3, "mode": "standard"}),
    )


def objects(s3, bucket):
    return {item["Key"]: item for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket)
            for item in page.get("Contents", [])}


def ensure_bucket(s3, bucket):
    from botocore.exceptions import ClientError
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        if str(exc.response["Error"]["Code"]) not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        s3.create_bucket(Bucket=bucket)


def consume(body, output=None):
    digest = hashlib.sha256()
    size = 0
    try:
        while chunk := body.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
            if output:
                output.write(chunk)
    finally:
        body.close()
    return size, digest.hexdigest()


def backup(s3, bucket, directory):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot = Path(directory) / f"{stamp}-{uuid.uuid4().hex[:8]}"
    (snapshot / "objects").mkdir(parents=True, exist_ok=False)
    initial = objects(s3, bucket)
    manifest = {"version": 1, "source_bucket": bucket, "created_utc": stamp,
                "policy": "private; provider IAM configuration must be restored separately", "objects": []}
    for key, listed in sorted(initial.items()):
        name = hashlib.sha256(key.encode()).hexdigest()
        response = s3.get_object(Bucket=bucket, Key=key)
        with (snapshot / "objects" / name).open("xb") as output:
            size, sha = consume(response["Body"], output)
        after = s3.head_object(Bucket=bucket, Key=key)
        if size != listed["Size"] or response["ETag"] != listed["ETag"] or after["ETag"] != response["ETag"]:
            raise RuntimeError("Source changed during snapshot; quiesce writers and retry")
        manifest["objects"].append({"key": key, "file": name, "size": size, "sha256": sha,
                                    "metadata": {field: response[field] for field in METADATA if field in response}})
    final = objects(s3, bucket)
    if {key: (v["Size"], v["ETag"]) for key, v in initial.items()} != {
            key: (v["Size"], v["ETag"]) for key, v in final.items()}:
        raise RuntimeError("Source listing changed; incomplete snapshot has no manifest")
    (snapshot / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"snapshot": str(snapshot), "objects": len(initial),
                      "bytes": sum(item["size"] for item in manifest["objects"])}))
    return snapshot


def read_manifest(snapshot):
    manifest = json.loads((Path(snapshot) / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        raise ValueError("Unsupported manifest version")
    keys = set()
    for item in manifest["objects"]:
        if item["key"] in keys or item["file"] != hashlib.sha256(item["key"].encode()).hexdigest():
            raise ValueError("Unsafe or duplicate manifest entry")
        keys.add(item["key"])
    return manifest


def verify(s3, bucket, snapshot):
    manifest = read_manifest(snapshot)
    expected = {item["key"] for item in manifest["objects"]}
    if set(objects(s3, bucket)) != expected:
        raise RuntimeError("Restored keys differ from manifest")
    for item in manifest["objects"]:
        response = s3.get_object(Bucket=bucket, Key=item["key"])
        if consume(response["Body"]) != (item["size"], item["sha256"]):
            raise RuntimeError("Restored content checksum mismatch")
        if any(response.get(k) != v for k, v in item["metadata"].items()):
            raise RuntimeError("Restored metadata differs")
    print(json.dumps({"verified_objects": len(expected), "sha256_mismatches": 0, "metadata_mismatches": 0}))


def restore(s3, bucket, snapshot):
    manifest = read_manifest(snapshot)
    ensure_bucket(s3, bucket)
    if objects(s3, bucket):
        raise RuntimeError("Restore requires an empty NEW destination; no existing objects overwritten")
    # Validate ALL local payloads before any remote write.
    for item in manifest["objects"]:
        with (Path(snapshot) / "objects" / item["file"]).open("rb") as body:
            if consume(body) != (item["size"], item["sha256"]):
                raise RuntimeError("Snapshot payload checksum mismatch")
    for item in manifest["objects"]:
        s3.upload_file(str(Path(snapshot) / "objects" / item["file"]), bucket, item["key"],
                       ExtraArgs=item["metadata"])
    verify(s3, bucket, snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "backup", "restore", "verify"))
    parser.add_argument("--directory", default="/backups/s3")
    parser.add_argument("--snapshot")
    args = parser.parse_args()
    s3, bucket = client(), os.environ["S3_BUCKET"]
    if args.action == "init":
        ensure_bucket(s3, bucket)
        print("Private bucket ready")
    elif args.action == "backup":
        backup(s3, bucket, args.directory)
    else:
        if not args.snapshot:
            parser.error("--snapshot is required")
        (restore if args.action == "restore" else verify)(s3, bucket, args.snapshot)


if __name__ == "__main__":
    main()
