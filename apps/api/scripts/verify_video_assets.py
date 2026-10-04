"""Read-only live QA verification of retained originals, hashes and privacy."""
import hashlib
import json
import os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

if os.getenv("QA_ISOLATED") != "true" or os.getenv("QA_PROJECT") not in {"chemistryaudit2", "chemistryprodlocal"}:
    raise SystemExit("Only an explicitly isolated QA project is allowed")
os.environ["STORAGE_BACKEND"] = "s3"

from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.storage import get_storage_provider
from app.models.video_upload import VideoUpload


def main():
    storage = get_storage_provider()
    verified = []
    with SessionLocal() as db:
        jobs = db.scalars(select(VideoUpload).where(VideoUpload.status == "ready", VideoUpload.sha256.is_not(None))
                         .order_by(VideoUpload.created_at.desc()).limit(5)).all()
        if not jobs:
            raise SystemExit("No current-pipeline videos with original hashes were found")
        for job in jobs:
            assert job.object_key.startswith("video-originals/")
            assert storage.get_size(job.object_key) == job.size_bytes
            digest = hashlib.sha256()
            for chunk in storage.open_stream(job.object_key):
                digest.update(chunk)
            assert digest.hexdigest() == job.sha256, f"Original hash mismatch: video_id={job.id}"
            for key in job.outputs:
                assert storage.exists(key), f"Missing output: video_id={job.id}"
            assert job.manifest_key in job.outputs
            # A read without any signature/credentials must fail at the real
            # SeaweedFS endpoint too, not only at the public upload gateway.
            anonymous_url = f"{storage.endpoint_url}/{storage.bucket_name}/{quote(job.object_key)}"
            try:
                with urlopen(anonymous_url, timeout=10) as response:
                    raise AssertionError(f"Anonymous object read succeeded: {response.status}")
            except HTTPError as error:
                assert error.code == 403, f"Unexpected anonymous-read status: {error.code}"
            verified.append({"video_id": str(job.id), "size_bytes": job.size_bytes,
                "sha256": job.sha256, "outputs": len(job.outputs), "anonymous_s3_get": 403})
    print(json.dumps({"verified": verified}, indent=2))


if __name__ == "__main__":
    main()
