"""Bounded mixed local load, full-transfer timings and real Docker/PG samples.

Default: three 60-second stages (1/5/10 sessions). Never extrapolate to 1000.
One attempt per request; HTTP 429 is recorded with Retry-After, never retried.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import random
import threading
import time
from urllib.parse import urljoin

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
from sqlalchemy import text
from tests.integration.live_helpers import BASE, clear_auth, container, lesson, pg_engine, session


def percentile(values, q):
    import math
    return round(sorted(values)[max(0, math.ceil(len(values) * q) - 1)], 2) if values else None


def main():
    seconds = int(os.getenv("QA_LOAD_SECONDS", "60"))
    if seconds < 30 or seconds > 300:
        raise ValueError("Stage duration must be 30..300 seconds")
    media = Path(os.environ["QA_MEDIA_DIR"])
    clear_auth()
    teacher = session()
    course, video = lesson(teacher, "video")
    with (media / "video.webm").open("rb") as source:
        response = teacher.post(f"{BASE}/lessons/{video['id']}/video", files={"file": ("video.webm", source, "video/webm")}, timeout=120)
    assert response.status_code == 200, response.text
    students, urls = [], []
    for number in range(1, 11):
        clear_auth()
        student = session(f"student{number:02d}@demo.com", "qa-student-pass")
        assert student.post(f"{BASE}/courses/{course['id']}/enroll", timeout=15).status_code == 200
        response = student.post(f"{BASE}/lessons/{video['id']}/video-token", timeout=15)
        assert response.status_code == 200, response.text
        students.append(student)
        urls.append(urljoin(BASE.removesuffix("/api/v1") + "/", response.json()["stream_url"]))
    services = {name: container(name) for name in ("api", "worker", "s3", "postgres", "redis")}
    engine = pg_engine()
    samples, stop = [], threading.Event()

    def sample():
        while not stop.is_set():
            try:
                item = {"t": time.time(), "memory_bytes": {
                    name: service.stats(stream=False)["memory_stats"]["usage"] for name, service in services.items()}}
                with engine.connect() as connection:
                    item["postgres_connections"] = connection.scalar(text("SELECT count(*) FROM pg_stat_activity"))
                    item["postgres_active"] = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE state='active'"))
                samples.append(item)
            except Exception as exc:
                samples.append({"sampling_error": type(exc).__name__})
            stop.wait(2)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    results = []
    try:
        for concurrency in (1, 5, 10):
            records = []
            started = time.monotonic()
            deadline = started + seconds

            def record(kind, client, url, **kwargs):
                before = time.monotonic()
                try:
                    with client.request(kwargs.pop("method", "GET"), url, stream=True, timeout=(3, 45), **kwargs) as response:
                        size = sum(len(chunk) for chunk in response.iter_content(256 * 1024))
                        records.append({"kind": kind, "ms": (time.monotonic() - before) * 1000,
                                        "status": response.status_code, "bytes": size,
                                        "retry_after": response.headers.get("Retry-After")})
                except requests.RequestException as exc:
                    records.append({"kind": kind, "ms": (time.monotonic() - before) * 1000,
                                    "status": "network", "bytes": 0, "error": type(exc).__name__})

            def browse(index):
                rng = random.Random(index)
                count = 0
                while time.monotonic() < deadline:
                    endpoint = ("courses", "bootstrap", "notifications", "progress/me")[count % 4]
                    record("browse", students[index], f"{BASE}/{endpoint}")
                    # Substantial video chunks with changing offsets simulate playback/seek.
                    start = rng.randrange(max(1, (media / "video.webm").stat().st_size - 512 * 1024))
                    record("video", students[index], urls[index], headers={"Range": f"bytes={start}-{start + 512 * 1024 - 1}"})
                    count += 1
                    time.sleep(0.5)

            def upload(index):
                # Separate transport session; preserve real user limits, no fresh identity per upload.
                client = requests.Session()
                client.verify = teacher.verify
                client.headers.update(teacher.headers)
                client.cookies.update(teacher.cookies)
                try:
                    with (media / "large.pdf").open("rb") as source:
                        encoder = MultipartEncoder({"file": (f"load-{concurrency}-{index}.pdf", source, "application/pdf")})
                        record("upload", client, f"{BASE}/lessons/{video['id']}/materials", method="POST", data=encoder,
                               headers={"Content-Type": encoder.content_type})
                finally:
                    client.close()

            with ThreadPoolExecutor(max_workers=concurrency + min(concurrency, 3)) as pool:
                jobs = [pool.submit(browse, index) for index in range(concurrency)]
                jobs += [pool.submit(upload, index) for index in range(min(concurrency, 3))]
                for job in jobs:
                    job.result()
            elapsed = time.monotonic() - started
            groups = {}
            for kind in ("browse", "video", "upload"):
                subset = [r for r in records if r["kind"] == kind]
                groups[kind] = {"requests": len(subset), "p95_ms": percentile([r["ms"] for r in subset], .95),
                                "p99_ms": percentile([r["ms"] for r in subset], .99)}
            errors = [r for r in records if not isinstance(r["status"], int) or r["status"] >= 400]
            result = {"sessions": concurrency, "seconds": round(elapsed, 2), "requests": len(records),
                      "throughput_rps": round(len(records) / elapsed, 2), "errors": len(errors),
                      "error_rate": len(errors) / len(records), "p95_ms": percentile([r["ms"] for r in records], .95),
                      "p99_ms": percentile([r["ms"] for r in records], .99), "transferred_bytes": sum(r["bytes"] for r in records),
                      "groups": groups, "error_details": errors[:20]}
            results.append(result)
            print(json.dumps(result), flush=True)
    finally:
        stop.set()
        sampler.join(timeout=15)
        engine.dispose()
        teacher.close()
        for student in students:
            student.close()
    valid = [s for s in samples if "memory_bytes" in s]
    assert valid, "No resource samples collected"
    report = {"video_bytes": (media / "video.webm").stat().st_size, "pdf_bytes": (media / "large.pdf").stat().st_size,
              "results": results, "samples": samples,
              "peak_memory_bytes": {name: max(s["memory_bytes"][name] for s in valid) for name in services},
              "peak_pg_connections": max(s["postgres_connections"] for s in valid),
              "peak_pg_active": max(s["postgres_active"] for s in valid),
              "claim": "Local 1/5/10-session mixed load only; no 1000-user capacity claim"}
    Path("/qa/load.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("peak_memory_bytes", "peak_pg_connections", "peak_pg_active")}))
    if any(stage["errors"] for stage in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
