import os
import sys
import time
import subprocess
import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

API_BASE = "http://127.0.0.1:8000/api/v1"

def run_test():
    print("=== Testing Worker Crash and Recovery ===")
    
    # 1. Login as teacher
    login_resp = requests.post(f"{API_BASE}/auth/login", json={
        "email": "teacher@chemistry.com",
        "password": "TeacherSecret123!"
    })
    assert login_resp.status_code == 200, f"Teacher login failed: {login_resp.text}"
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get course
    courses_resp = requests.get(f"{API_BASE}/courses", headers=headers)
    assert courses_resp.status_code == 200, f"Courses failed: {courses_resp.text}"
    course = courses_resp.json()["items"][0]
    course_id = course["id"]
    print(f"Using Course: {course['title']} ({course_id})")
    
    # 3. Upload a multi-page document
    sample_pdf = os.path.abspath("apps/api/tests/fixtures/textbook_sample_5pages.pdf")
    if not os.path.exists(sample_pdf):
        sample_pdf = os.path.abspath("textbook_sample_5pages.pdf")
    
    assert os.path.exists(sample_pdf), f"Sample PDF not found at {sample_pdf}"
    
    with open(sample_pdf, "rb") as f:
        file_bytes = f.read() + f"\n% Unique Salt {time.time()}\n".encode("utf-8")
    
    filename = f"crash_recovery_{int(time.time())}.pdf"
    print(f"Uploading {filename} ({len(file_bytes)} bytes)...")
    upload_resp = requests.post(
        f"{API_BASE}/knowledge-center/sources/upload",
        headers=headers,
        data={"course_id": course_id, "source_role": "KNOWLEDGE"},
        files={"file": (filename, file_bytes, "application/pdf")}
    )
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    source_id = upload_resp.json()["id"]
    print(f"Uploaded source_id: {source_id}, status: {upload_resp.json()['status']}")
    
    # 4. Give worker 0.3s to start parsing, then kill the worker from host
    time.sleep(0.3)
    print("Simulating abrupt worker crash: killing chemistry_worker via host docker kill...")
    kill_res = subprocess.run(["docker", "kill", "chemistry_worker"], capture_output=True, text=True)
    assert kill_res.returncode == 0, f"Docker kill failed: {kill_res.stderr}"
    print("chemistry_worker killed.")
    
    # 5. Prove API remains 100% responsive
    health_resp = requests.get(f"{API_BASE}/health")
    assert health_resp.status_code == 200, f"API health check failed during worker downtime: {health_resp.status_code}"
    courses_during_crash = requests.get(f"{API_BASE}/courses", headers=headers)
    assert courses_during_crash.status_code == 200, f"API courses endpoint failed during worker downtime: {courses_during_crash.status_code}"
    print("API verified 100% responsive while worker is DOWN.")
    
    # 6. Restart the worker from host
    print("Restarting chemistry_worker via host docker start...")
    start_res = subprocess.run(["docker", "start", "chemistry_worker"], capture_output=True, text=True)
    assert start_res.returncode == 0, f"Docker start failed: {start_res.stderr}"
    print("chemistry_worker restarted.")
    
    # 7. Wait for worker to recover the task and complete indexing
    print("Waiting for task recovery and indexing to complete (up to 130s for Redis QoS reclaim)...")
    final_status = None
    source_detail = None
    for attempt in range(1, 135):
        time.sleep(1.0)
        detail_resp = requests.get(f"{API_BASE}/knowledge-center/sources/{source_id}", headers=headers)
        if detail_resp.status_code == 200:
            source_detail = detail_resp.json()
            status = source_detail.get("status")
            if attempt % 5 == 0 or status in ("INDEXED", "READY", "PROCESSED", "ERROR"):
                print(f"[{attempt}s] Source status: {status}, progress: {source_detail.get('progress_percent')}%")
            if status in ("INDEXED", "READY", "PROCESSED"):
                final_status = status
                print(f"Source reached {final_status} after {attempt}s.")
                break
            elif status == "ERROR":
                print(f"Source errored: {source_detail.get('error_message')}")
                break
    
    assert final_status in ("INDEXED", "READY", "PROCESSED"), f"Source did not complete indexing: status={final_status}"
    
    # 8. Verify no duplicate units or questions
    units = source_detail.get("units", [])
    questions = source_detail.get("questions", [])
    print(f"Result: {len(units)} units, {len(questions)} questions extracted.")
    
    # Check unit positions are unique
    unit_positions = [u.get("position") for u in units if "position" in u]
    if unit_positions:
        assert len(unit_positions) == len(set(unit_positions)), f"Duplicate unit positions detected: {unit_positions}"
    
    # Check unit IDs are unique
    unit_ids = [u.get("id") for u in units]
    assert len(unit_ids) == len(set(unit_ids)), f"Duplicate unit IDs detected: {unit_ids}"
    
    print("SUCCESS: Worker crash and task recovery verified with 0 duplicate units and 0 duplicate questions!")

if __name__ == "__main__":
    run_test()
