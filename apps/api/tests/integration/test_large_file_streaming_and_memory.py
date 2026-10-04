"""Real byte-boundary uploads, streaming clients and Docker memory.
The removed /knowledge-center route and obsolete container names are not used.
"""
import hashlib
import json
import os
from pathlib import Path
import threading
import shutil
import zipfile
import pytest
from app.core.upload_limits import MAX_VIDEO_BYTES, MAX_MATERIAL_BYTES
from requests_toolbelt.multipart.encoder import MultipartEncoder
from .live_helpers import BASE, container, lesson, session


def memory_events(api):
    result = api.exec_run(['cat', '/sys/fs/cgroup/memory.events'])
    assert result.exit_code == 0, 'cgroup v2 memory.events evidence is required'
    return {key: int(value) for key, value in (line.split() for line in result.output.decode().splitlines())}


def recovered_memory(api, before_events):
    # memory.max may be transiently exceeded under cgroup v2 (documented by
    # the kernel). Retain raw peaks, require it to settle within the SAME cap,
    # and require no OOM/kill. Do not increase the container or buffer budget.
    # https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html
    from .live_helpers import wait_until
    limit = api.attrs['HostConfig']['Memory']
    wait_until(lambda: api.stats(stream=False)['memory_stats']['usage'] <= limit, 15)
    after = memory_events(api)
    for key in ('oom', 'oom_kill', 'oom_group_kill'):
        assert after.get(key, 0) == before_events.get(key, 0), f'New {key} event during upload'
    return {key: after.get(key, 0) - before_events.get(key, 0) for key in after}


def test_large_file_streaming_and_memory(tmp_path):
    api = container("api")
    before_events = memory_events(api)
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
                target.truncate(MAX_MATERIAL_BYTES + 1)
            with oversized.open("rb") as source:
                encoder = MultipartEncoder({"file": ("oversized.pdf", source, "application/pdf")})
                response = teacher.post(f"{BASE}/lessons/{material_lesson['id']}/materials", data=encoder,
                                        headers={"Content-Type": encoder.content_type}, timeout=(10, 1800))
            assert response.status_code == 413, response.text
    finally:
        stop.set()
        sampler.join(timeout=10)
    assert samples, "No real memory samples collected"
    limit = api.attrs["HostConfig"]["Memory"]
    assert limit > 0
    events = recovered_memory(api, before_events)
    print(json.dumps({"memory_samples": len(samples), "api_peak_bytes": max(samples), "limit_bytes": limit,
                      "memory_events_delta": events, "settled_within_same_cap": True}))


@pytest.mark.parametrize("kind,extra", [("material", 0), ("material", 1), ("video", 0), ("video", 1)])
def test_exact_upload_byte_boundaries(kind, extra, tmp_path):
    """Padding tests byte limits, NOT realistic content size or user capacity.

    The ZIP is valid, uncompressed; WebM preserves the playable clip and adds
    an EBML Void in its unknown-size Segment. No whole-file RAM buffer.
    """
    from .live_helpers import clear_auth, wait_until
    clear_auth()
    limit = MAX_VIDEO_BYTES if kind == "video" else MAX_MATERIAL_BYTES
    size = limit + extra
    path = tmp_path / ("boundary.webm" if kind == "video" else "boundary.zip")
    if kind == "video":
        source_path = Path(os.environ["QA_MEDIA_DIR"]) / "video.webm"
        with source_path.open("rb") as source:
            assert b"\x18\x53\x80\x67\x01\xff\xff\xff\xff\xff\xff\xff" in source.read(128)
        shutil.copyfile(source_path, path)
        remaining = size - path.stat().st_size - 9
        with path.open("ab") as target:
            target.write(b"\xec" + (remaining | (1 << 56)).to_bytes(8, "big"))
            target.truncate(size)
    else:
        # Local header (36), central record (52), end record (22): 110 bytes.
        remaining = size - 110
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            with archive.open("qa.bin", "w") as target:
                block = b"\0" * (1024 * 1024)
                while remaining:
                    chunk = block[:min(len(block), remaining)]
                    target.write(chunk)
                    remaining -= len(chunk)
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
    assert path.stat().st_size == size
    api = container("api")
    samples, stop = [], threading.Event()
    def sample():
        while not stop.is_set():
            memory = api.stats(stream=False)["memory_stats"]
            counters = memory["stats"]
            # cgroup usage includes reclaimable disk page cache. Anonymous
            # bytes measure file buffers; retain BOTH, not just a nicer gauge.
            anon = counters.get("anon", counters.get("rss"))
            assert anon is not None, "Missing real anonymous-memory counter"
            inactive = counters.get("inactive_file", counters.get("total_inactive_file", 0))
            samples.append({"total": memory["usage"], "anon": anon,
                            "file_cache": counters.get("file", counters.get("cache", 0)),
                            "working_set": memory["usage"] - inactive})
            stop.wait(.5)
    api.reload()
    prior_restarts = api.attrs["RestartCount"]
    before_events = memory_events(api)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        with session() as teacher:
            _, item = lesson(teacher, "video" if kind == "video" else "article")
            from scripts.s3_snapshot import client, objects
            store = client()
            before_keys = set(objects(store, os.environ['S3_BUCKET']))
            endpoint = f"{BASE}/lessons/{item['id']}/{'video' if kind == 'video' else 'materials'}"
            with path.open("rb") as source:
                encoder = MultipartEncoder({"file": (path.name, source, "video/webm" if kind == "video" else "application/zip")})
                response = teacher.post(endpoint, data=encoder, headers={"Content-Type": encoder.content_type}, timeout=(10, 1800))
            assert response.status_code == (413 if extra else 200 if kind == "video" else 201), response.text
            created_keys = set(objects(store, os.environ['S3_BUCKET'])) - before_keys
            assert len(created_keys) == (0 if extra else 1)
            if not extra:
                with path.open("rb") as source:
                    expected = hashlib.file_digest(source, "sha256").hexdigest()
                url = endpoint if kind == "video" else f"{endpoint}/{response.json()['id']}/download"
                with teacher.get(url, stream=True, timeout=(10, 1800)) as download:
                    assert download.status_code == 200
                    digest, total = hashlib.sha256(), 0
                    for chunk in download.iter_content(1024 * 1024):
                        digest.update(chunk); total += len(chunk)
                    assert total == size and digest.hexdigest() == expected
            # Retire only the synthetic lesson and its objects through the API.
            deleted = teacher.delete(f"{BASE}/modules/{item['module_id']}/lessons/{item['id']}", timeout=30)
            assert deleted.status_code == 204, deleted.text
            def cleaned():
                return not created_keys.intersection(objects(store, os.environ['S3_BUCKET']))
            wait_until(cleaned, 75)
    finally:
        stop.set(); sampler.join(timeout=10)
    assert samples, "No Docker memory evidence"
    api.reload()
    assert not api.attrs["State"]["OOMKilled"] and api.attrs["RestartCount"] == prior_restarts
    events = recovered_memory(api, before_events)
    # Always record raw total/cache peaks, even if a fixed-budget assertion
    # below fails. A transient kernel overshoot is not omitted or smoothed.
    print(json.dumps({"kind": kind, "file_bytes": size, "status": response.status_code,
                      "peak_total_bytes": max(s["total"] for s in samples),
                      "peak_working_set_bytes": max(s["working_set"] for s in samples),
                      "peak_anonymous_bytes": max(s["anon"] for s in samples),
                      "anonymous_delta_bytes": max(s["anon"] for s in samples) - min(s["anon"] for s in samples),
                      "peak_file_cache_bytes": max(s["file_cache"] for s in samples),
                      "memory_events_delta": events, "settled_within_same_cap": True,
                      "restart_count_unchanged": True, "oom_killed": False}))
    assert max(s["working_set"] for s in samples) < api.attrs["HostConfig"]["Memory"]
    assert max(s["anon"] for s in samples) < 512 * 1024**2, "Anonymous buffers exceeded the fixed RAM budget"
    assert max(s["anon"] for s in samples) - min(s["anon"] for s in samples) < 512 * 1024**2, "Anonymous upload memory grew with file size"
