import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

API_BASE = "http://127.0.0.1:8000/api/v1"

class MemorySampler:
    def __init__(self, container_names: list[str], interval_sec: float = 0.2):
        self.container_names = container_names
        self.interval_sec = interval_sec
        self.running = False
        self.thread = None
        self.samples = {name: [] for name in container_names}
        self.peak_mb = {name: 0.0 for name in container_names}

    def _parse_mem_mb(self, mem_str: str) -> float:
        # e.g. "125.4MiB / 1GiB" or "1.2GiB / 2GiB"
        match = re.search(r"([\d\.]+)\s*([A-Za-z]+)", mem_str)
        if not match:
            return 0.0
        val, unit = float(match.group(1)), match.group(2).lower()
        if "gib" in unit:
            return val * 1024.0
        elif "kib" in unit:
            return val / 1024.0
        return val  # mib

    def _sample_once(self):
        try:
            res = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.Name}}: {{.MemUsage}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                for line in res.stdout.strip().split("\n"):
                    for name in self.container_names:
                        if line.startswith(f"{name}:"):
                            mem_str = line.split(":", 1)[1].strip().split("/")[0].strip()
                            mb = self._parse_mem_mb(mem_str)
                            self.samples[name].append(mb)
                            if mb > self.peak_mb[name]:
                                self.peak_mb[name] = mb
        except Exception:
            pass

    def _run(self):
        while self.running:
            self._sample_once()
            time.sleep(self.interval_sec)

    def start(self):
        self._sample_once()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
        self._sample_once()


class ZeroStream(io.RawIOBase):
    def __init__(self, size: int):
        self.size = size
        self.pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        elif whence == 2:
            self.pos = self.size + offset
        return self.pos

    def tell(self) -> int:
        return self.pos

    def readinto(self, b) -> int:
        rem = self.size - self.pos
        if rem <= 0:
            return 0
        n = min(len(b), rem)
        b[:n] = b"\0" * n
        self.pos += n
        return n


def run_test():
    print("=== Testing Large Files, Boundaries, and Continuous Memory Sampling ===")
    
    # 1. Login as teacher
    login_resp = requests.post(f"{API_BASE}/auth/login", json={
        "email": "teacher@chemistry.com",
        "password": "TeacherSecret123!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get Course ID
    courses_resp = requests.get(f"{API_BASE}/courses", headers=headers)
    assert courses_resp.status_code == 200
    course_id = courses_resp.json()["items"][0]["id"]


    # 3. Test 501MB Rejection (HTTP 413)
    print("\n--- 1. Testing Rejection of 501MB (> 500MB limit) ---")
    size_501mb = 501 * 1024 * 1024
    
    resp_413 = requests.post(
        f"{API_BASE}/knowledge-center/sources/upload",
        headers=headers,
        data={"course_id": course_id, "source_role": "KNOWLEDGE"},
        files={"file": ("too_large_501mb.pdf", ZeroStream(size_501mb), "application/pdf")}
    )
    print(f"501MB Request response code: {resp_413.status_code}")
    assert resp_413.status_code == 413, f"Expected 413, got {resp_413.status_code}: {resp_413.text}"
    print("SUCCESS: 501MB correctly rejected with 413 Payload Too Large!")

    # 4. Continuous Memory Sampling during OCR and Indexing
    print("\n--- 2. Continuous Memory Sampling during Real OCR & Indexing ---")
    sample_pdf = os.path.abspath("apps/api/tests/fixtures/textbook_sample_5pages.pdf")
    with open(sample_pdf, "rb") as f:
        pdf_bytes = f.read() + f"\n% MemorySample {time.time()}\n".encode("utf-8")

    sampler = MemorySampler(["chemistry_worker", "chemistry_api"], interval_sec=0.25)
    sampler.start()
    
    print("Uploading sample document to trigger OCR & Celery indexing...")
    upload_resp = requests.post(
        f"{API_BASE}/knowledge-center/sources/upload",
        headers=headers,
        data={"course_id": course_id, "source_role": "KNOWLEDGE"},
        files={"file": (f"mem_sample_{int(time.time())}.pdf", pdf_bytes, "application/pdf")}
    )
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    source_id = upload_resp.json()["id"]

    # Poll until indexed
    completed = False
    for _ in range(40):
        time.sleep(0.5)
        detail = requests.get(f"{API_BASE}/knowledge-center/sources/{source_id}", headers=headers).json()
        if detail.get("status") in ("INDEXED", "READY"):
            completed = True
            break

    sampler.stop()
    assert completed, "Document failed to reach INDEXED status"

    print("\n=== CONTINUOUS MEMORY SAMPLING RESULTS ===")
    for container in ["chemistry_worker", "chemistry_api"]:
        samples = sampler.samples[container]
        initial_ram = samples[0] if samples else 0.0
        peak_ram = sampler.peak_mb[container]
        final_ram = samples[-1] if samples else 0.0
        print(f"Container: {container}")
        print(f"  Samples Count:  {len(samples)}")
        print(f"  Initial RAM:    {initial_ram:.1f} MB")
        print(f"  Peak RAM:       {peak_ram:.1f} MB")
        print(f"  Final RAM:      {final_ram:.1f} MB")
        
        if container == "chemistry_worker":
            assert peak_ram < 2048.0, f"Worker exceeded 2048 MB memory limit: {peak_ram} MB"
        if container == "chemistry_api":
            assert peak_ram < 1024.0, f"API exceeded 1024 MB memory limit: {peak_ram} MB"

    print("\nSUCCESS: All large file boundary checks and memory constraints passed!")

if __name__ == "__main__":
    run_test()
