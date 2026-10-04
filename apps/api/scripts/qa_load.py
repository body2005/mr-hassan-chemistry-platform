"""Bounded mixed local load, full-transfer timings and real Docker/PG samples.

Default: three 180-second stages (1/5/10 sessions). Never extrapolate to 1000.
One attempt per request; HTTP 429 is recorded with Retry-After, never retried.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import os
from pathlib import Path
import random
import threading
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
from sqlalchemy import text
from tests.integration.live_helpers import BASE, clear_auth, container, lesson, pg_engine, session


def percentile(values, q):
    import math
    return round(sorted(values)[max(0, math.ceil(len(values) * q) - 1)], 2) if values else None


def seed_video(teacher, item, media, engine):
    """Seed the real pipeline; private S3 fixture upload is NOT gateway load."""
    capabilities = teacher.get(f"{BASE}/video-upload-capabilities", timeout=15)
    assert capabilities.status_code == 200
    if not capabilities.json()["direct_upload"]:
        with media.open("rb") as source:
            response = teacher.post(f"{BASE}/lessons/{item['id']}/video", files={"file": ("video.webm", source, "video/webm")}, timeout=120)
        assert response.status_code == 200
        return "progressive"
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models.video_upload import VideoUpload
    from scripts.s3_snapshot import client
    digest = hashlib.sha256()
    with media.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    response = teacher.post(f"{BASE}/lessons/{item['id']}/video-uploads", json={
        "filename": "load.webm", "content_type": "video/webm", "size_bytes": media.stat().st_size,
        "fingerprint": digest.hexdigest(), "request_key": uuid.uuid4().hex}, timeout=15)
    assert response.status_code == 201
    uploaded = response.json()
    with Session(engine) as db:
        job = db.scalar(select(VideoUpload).where(VideoUpload.id == uuid.UUID(uploaded['id'])))
        key, multipart_id = job.object_key, job.multipart_id
    store = client()
    with media.open("rb") as source:
        number = 1
        while part := source.read(uploaded['part_bytes']):
            store.upload_part(Bucket=os.environ['S3_BUCKET'], Key=key, UploadId=multipart_id, PartNumber=number, Body=part)
            number += 1
    assert teacher.post(f"{BASE}/video-uploads/{uploaded['id']}/complete", timeout=15).status_code == 202
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        current = teacher.get(f"{BASE}/video-uploads/{uploaded['id']}", timeout=15)
        assert current.status_code == 200
        state = current.json()['status']
        if state == 'ready': return 'hls'
        assert state not in {'failed', 'cancelled', 'expired'}
        time.sleep(5)
    raise AssertionError('Video pipeline did not finish before the fixture deadline')


def playback_targets(student, issued, original_size):
    """Real media segments, not manifest bytes mislabeled as video traffic."""
    origin = BASE.removesuffix('/api/v1') + '/'
    url = urljoin(origin, issued['stream_url'])
    if issued.get('format') != 'hls': return [(url, original_size)]
    master = student.get(url, timeout=15)
    assert master.status_code == 200
    child = next(line for line in master.text.splitlines() if line and not line.startswith('#'))
    playlist = student.get(urljoin(origin, child), timeout=15)
    assert playlist.status_code == 200
    targets = []
    for line in playlist.text.splitlines():
        if not line or line.startswith('#'): continue
        target = urljoin(origin, line)
        response = student.get(target, headers={'Range': 'bytes=0-0'}, timeout=15)
        assert response.status_code == 206 and len(response.content) == 1
        targets.append((target, int(response.headers['Content-Range'].rsplit('/', 1)[1])))
    assert targets
    return targets


def main():
    seconds = int(os.getenv("QA_LOAD_SECONDS", "180"))
    if seconds < 30 or seconds > 240:
        raise ValueError("Stage duration must be 30..240 seconds (below the playback token lifetime)")
    media = Path(os.environ["QA_MEDIA_DIR"])
    clear_auth()
    teacher = session()
    course, video = lesson(teacher, "video")
    engine = pg_engine()
    video_mode = seed_video(teacher, video, media / "video.webm", engine)
    students, urls = [], []
    for number in range(1, 11):
        clear_auth()
        student = session(f"student{number:02d}@demo.com", "qa-student-pass")
        assert student.post(f"{BASE}/courses/{course['id']}/enroll", timeout=15).status_code == 200
        response = student.post(f"{BASE}/lessons/{video['id']}/video-token", timeout=15)
        assert response.status_code == 200, response.text
        students.append(student)
        urls.append(playback_targets(student, response.json(), (media / "video.webm").stat().st_size))
    names = ["api", "worker", "s3", "postgres", "redis"]
    if video_mode == 'hls': names += ['video-worker', 'upload-gateway']
    services = {name: container(name) for name in names}
    samples, stop = [], threading.Event()
    previous_cpu = {}

    def sample():
        while not stop.is_set():
            try:
                item = {"t": time.time(), "memory_bytes": {}, "cpu_percent": {}}
                for name, service in services.items():
                    stats = service.stats(stream=False)
                    item["memory_bytes"][name] = stats["memory_stats"]["usage"]
                    cpu = stats["cpu_stats"]
                    last = previous_cpu.get(name, stats.get("precpu_stats", {}))
                    previous_cpu[name] = cpu
                    system_delta = cpu.get("system_cpu_usage", 0) - last.get("system_cpu_usage", 0)
                    used_delta = cpu["cpu_usage"]["total_usage"] - last.get("cpu_usage", {}).get("total_usage", 0)
                    item["cpu_percent"][name] = round(used_delta / system_delta * cpu.get("online_cpus", 1) * 100, 2) if system_delta > 0 and used_delta >= 0 else None
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
            # Renew existing sessions before each stage, not new device slots.
            for index in range(concurrency):
                response = students[index].post(f"{BASE}/lessons/{video['id']}/video-token", timeout=15)
                assert response.status_code == 200, response.text
                urls[index] = playback_targets(students[index], response.json(), (media / "video.webm").stat().st_size)
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
                    target, size = rng.choice(urls[index])
                    length = min(size, 512 * 1024)
                    start = rng.randrange(max(1, size - length + 1))
                    record("video", students[index], target, headers={"Range": f"bytes={start}-{start + length - 1}"})
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

            # Normal load stays within the configured two global upload slots.
            # Deliberate overload/admission rejection is covered separately.
            with ThreadPoolExecutor(max_workers=concurrency + min(concurrency, 2)) as pool:
                jobs = [pool.submit(browse, index) for index in range(concurrency)]
                jobs += [pool.submit(upload, index) for index in range(min(concurrency, 2))]
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
              "video_mode": video_mode, "fixture_upload": "private S3 fixture, not public gateway load" if video_mode == 'hls' else 'legacy API',
              "results": results, "samples": samples,
              "peak_memory_bytes": {name: max(s["memory_bytes"][name] for s in valid) for name in services},
              "peak_cpu_percent": {name: max((s["cpu_percent"][name] for s in valid if s["cpu_percent"][name] is not None), default=None) for name in services},
              "peak_pg_connections": max(s["postgres_connections"] for s in valid),
              "peak_pg_active": max(s["postgres_active"] for s in valid),
              "claim": "Local 1/5/10-session mixed load only; no 1000-user capacity claim"}
    output = json.dumps(report, indent=2)
    # Preserve every run's evidence instead of overwriting a previous result.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    Path(f"/qa/load-{stamp}.json").write_text(output, encoding="utf-8")
    Path("/qa/load.json").write_text(output, encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("peak_memory_bytes", "peak_pg_connections", "peak_pg_active")}))
    if any(stage["errors"] for stage in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
