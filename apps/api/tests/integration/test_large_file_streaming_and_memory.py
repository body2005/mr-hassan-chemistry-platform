"""Current lesson uploads: 100 MiB limit, streaming client and Docker memory.
The removed /knowledge-center route and obsolete container names are not used.
"""
import hashlib
import json
import os
from pathlib import Path
import threading
from requests_toolbelt.multipart.encoder import MultipartEncoder
from .live_helpers import BASE, container, lesson, session


def test_large_file_streaming_and_memory(tmp_path):
    api = container("api")
    samples, stop = [], threading.Event()

    def sample():
        while not stop.is_set():
            samples.append(api.stats(stream=False)["memory_stats"]["usage"])
            stop.wait(0.5)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        with session() as teacher:
            _, material_lesson = lesson(teacher)
            path = Path(os.environ["QA_MEDIA_DIR"]) / "large.pdf"
            assert path.stat().st_size > 20 * 1024 * 1024
            with path.open("rb") as source:
                encoder = MultipartEncoder({"file": ("large.pdf", source, "application/pdf")})
                response = teacher.post(f"{BASE}/lessons/{material_lesson['id']}/materials", data=encoder,
                                        headers={"Content-Type": encoder.content_type}, timeout=90)
            assert response.status_code == 201, response.text
            material = response.json()
            with path.open("rb") as source:
                expected_sha = hashlib.file_digest(source, "sha256").hexdigest()
            with teacher.get(f"{BASE}/lessons/{material_lesson['id']}/materials/{material['id']}/download",
                             stream=True, timeout=30) as download:
                assert download.status_code == 200, download.text
                digest = hashlib.sha256()
                for chunk in download.iter_content(1024 * 1024):
                    digest.update(chunk)
                assert digest.hexdigest() == expected_sha
            oversized = tmp_path / "oversized.pdf"
            with oversized.open("wb") as target:
                target.write(b"%PDF-1.7\n")
                target.truncate(101 * 1024 * 1024)
            with oversized.open("rb") as source:
                encoder = MultipartEncoder({"file": ("oversized.pdf", source, "application/pdf")})
                response = teacher.post(f"{BASE}/lessons/{material_lesson['id']}/materials", data=encoder,
                                        headers={"Content-Type": encoder.content_type}, timeout=90)
            assert response.status_code == 413, response.text
    finally:
        stop.set()
        sampler.join(timeout=10)
    assert samples, "No real memory samples collected"
    limit = api.attrs["HostConfig"]["Memory"]
    assert limit > 0 and max(samples) < limit
    print(json.dumps({"memory_samples": len(samples), "api_peak_bytes": max(samples), "limit_bytes": limit}))
