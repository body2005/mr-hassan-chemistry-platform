#!/usr/bin/env python3
"""
E2E Pipeline Test: Video Upload -> Indexing -> Transcript -> Quiz + Tutor
Tests HTTP 206 (Range request), RAG indexing, and real pipeline.
Run from apps/api directory.
"""
import subprocess
import os
import uuid
import tempfile
import sys
import json
import time
import shutil

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.course import Course, CourseModule, CourseStatus, Lesson, LessonKind, IndexingStatus
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.models.platform import AIRefusalLog, Quiz

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"

def http_get(path, cookies=None, headers=None):
    cmd = ["curl", "-s", "-b", f"cookies={cookies}"] if cookies else ["curl", "-s"]
    if headers:
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])
    cmd.append(f"{BASE_URL}{path}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout, r.stderr

def http_post(path, data, cookies=None, headers=None):
    cmd = ["curl", "-s", "-X", "POST", "-b", f"cookies={cookies}"] if cookies else ["curl", "-s", "-X", "POST"]
    cmd.extend(["-H", "Content-Type: application/json"])
    if headers:
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])
    cmd.extend(["-d", json.dumps(data)])
    cmd.append(f"{BASE_URL}{path}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout, r.stderr

def main():
    print("=" * 70)
    print("E2E PIPELINE TEST: Video Upload -> Indexing -> Transcript -> Quiz+Tutor")
    print("=" * 70)
    
    # Step 1: Verify FFmpeg
    ffmpeg_path = (
        shutil.which("ffmpeg")
        or os.environ.get("FFMPEG_PATH")
        or (os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe") if os.environ.get("LOCALAPPDATA") else None)
        or "ffmpeg"
    )
    print(f"\n[F1] FFmpeg: {ffmpeg_path} (exists={os.path.isfile(ffmpeg_path)})")
    
    # Step 2: Generate test video with audio
    print("[F2] Generating test video...")
    tmpdir = tempfile.gettempdir()
    video_path = os.path.join(tmpdir, f"e2e_video_{uuid.uuid4().hex[:8]}.mp4")
    cmd = [ffmpeg_path, "-y",
           "-f", "lavfi", "-i", "color=c=#2b4a7f:size=640x360:d=5",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
           "-c:v", "libx264", "-preset", "ultrafast",
           "-c:a", "aac", "-b:a", "32k",
           "-pix_fmt", "yuv420p",
           "-t", "5", video_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"FAIL: Video generation failed: {r.stderr[-300:]}")
        sys.exit(1)
    video_size = os.path.getsize(video_path)
    print(f"OK: Video created: {video_path} ({video_size} bytes)")
    
    # Step 3: Setup DB - create institution, teacher, course, module, lesson
    print("[F3] Setting up DB fixtures...")
    db = SessionLocal()
    try:
        institution = Institution(name="E2E Test Academy", slug="e2e-test")
        db.add(institution)
        db.flush()
        print(f"  Institution: {institution.id} - {institution.slug}")
        
        teacher = User(
            institution_id=institution.id,
            username=f"teacher-{uuid.uuid4().hex[:8]}",
            email=f"teacher-{uuid.uuid4().hex[:10]}@e2e.test",
            display_name="E2E Test Teacher",
            password_hash=hash_password("testpassword"),
            role=UserRole.TEACHER,
        )
        db.add(teacher)
        db.flush()
        print(f"  Teacher: {teacher.id} - {teacher.email}")
        
        course = Course(
            institution_id=institution.id,
            teacher_id=teacher.id,
            code="E2E-101",
            title="E2E Physics Test",
            status=CourseStatus.PUBLISHED,
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        print(f"  Course: {course.id} - {course.title}")
        
        module = CourseModule(course_id=course.id, title="Module 1: Motion", position=1)
        db.add(module)
        db.flush()
        print(f"  Module: {module.id} - {module.title}")
        
        lesson = Lesson(
            module_id=module.id,
            title="Lesson 1: Newtons Laws",
            kind=LessonKind.VIDEO,
            position=1,
            content="Newtons laws of motion form the foundation of classical mechanics.",
            video_duration_seconds=300,
            indexing_status=IndexingStatus.NOT_INDEXED,
        )
        db.add(lesson)
        db.commit()
        db.refresh(lesson)
        print(f"  Lesson: {lesson.id} - {lesson.title}")
        lesson_id = lesson.id
        course_id = course.id
        inst_slug = institution.slug
        teacher_email = teacher.email
        teacher_password = "testpassword"
    finally:
        db.close()
    
    # Step 4: Upload video to lesson
    print(f"\n[F4] Uploading video to lesson {lesson_id}...")
    with open(video_path, "rb") as f:
        import requests
        login_resp = requests.post(f"{API_V1}/auth/login", json={
            "email": teacher_email,
            "password": teacher_password,
            "institution_slug": inst_slug,
        }, timeout=10)
        if login_resp.status_code != 200:
            print(f"FAIL: Login failed: {login_resp.status_code} {login_resp.text}")
            sys.exit(1)
        cookies = login_resp.cookies
        print(f"  Login OK")
        
        upload_resp = requests.post(
            f"{API_V1}/lessons/{lesson_id}/video",
            files={"file": ("test_video.mp4", f, "video/mp4")},
            cookies=cookies,
            timeout=30,
        )
        print(f"  Upload HTTP status: {upload_resp.status_code}")
        if upload_resp.status_code not in (200, 201, 202):
            print(f"FAIL: Upload failed: {upload_resp.text}")
            sys.exit(1)
        upload_data = upload_resp.json()
        print(f"  Upload response: {json.dumps(upload_data, indent=2)}")
    
    # Step 5: Poll indexing status
    print(f"\n[F5] Polling indexing status for lesson {lesson_id}...")
    max_polls = 30
    polling_interval = 2
    indexing_status = None
    for i in range(max_polls):
        time.sleep(polling_interval)
        status_resp = requests.get(
            f"{API_V1}/lessons/{lesson_id}/indexing-status",
            cookies=cookies,
            timeout=10,
        )
        if status_resp.status_code != 200:
            print(f"  Poll {i+1}: status check failed: {status_resp.status_code}")
            continue
        status_data = status_resp.json()
        print(f"  Poll {i+1}: status={status_data.get('status')}, chunks={status_data.get('indexed_chunks_count')}, rag_synced={status_data.get('rag_synced')}")
        indexing_status = status_data.get("status")
        if indexing_status == "indexed":
            break
        if indexing_status == "failed":
            print(f"  Indexing failed: {status_data.get('error')}")
            break
    
    if indexing_status != "indexed":
        print(f"  WARNING: Indexing did not complete (status={indexing_status}). Continuing anyway...")
    
    # Step 6: Read transcript from DB
    print(f"\n[F6] Reading transcript from DB...")
    db = SessionLocal()
    try:
        lesson = db.get(Lesson, lesson_id)
        transcript = (lesson.transcript_text or "").strip()
        content = (lesson.content or "").strip()
        print(f"  transcript_text (first 300 chars): {transcript[:300] if transcript else '(empty)'}")
        print(f"  content (first 300 chars): {content[:300] if content else '(empty)'}")
        print(f"  indexing_status: {lesson.indexing_status}")
        print(f"  rag_synced: {lesson.rag_synced}")
        print(f"  indexed_chunks_count: {lesson.indexed_chunks_count}")
        print(f"  video_asset_key: {lesson.video_asset_key}")
    finally:
        db.close()
    
    # Step 7: GET video with Range header -> must be 206
    print(f"\n[F7] Testing HTTP 206 Range request...")
    filename = f"{lesson_id}.mp4"
    video_url = f"/static/uploads/{filename}"
    r = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
         "-H", "Range: bytes=0-1023",
         f"{BASE_URL}{video_url}"],
        capture_output=True, text=True, timeout=10,
    )
    http_code = r.stdout.strip()
    print(f"  Range request to {video_url}: HTTP {http_code}")
    if http_code == "206":
        print("  OK: HTTP 206 Partial Content received")
        # Also get Content-Range header
        r2 = subprocess.run(
            ["curl", "-s", "-I",
             "-H", "Range: bytes=0-1023",
             f"{BASE_URL}{video_url}"],
            capture_output=True, text=True, timeout=10,
        )
        headers = r2.stdout
        cr_line = [l for l in headers.split("\n") if "Content-Range" in l]
        if cr_line:
            print(f"  Content-Range: {cr_line[0].strip()}")
    else:
        print(f"  WARNING: Expected 206, got {http_code}. Checking if video file exists...")
        video_disk = os.path.join(UPLOAD_DIR, filename)
        print(f"  Video on disk: {video_disk} (exists={os.path.isfile(video_disk)}, size={os.path.getsize(video_disk) if os.path.isfile(video_disk) else 0})")
    
    # Step 8: Generate quiz from transcript
    print(f"\n[F8] Generating quiz from transcript...")
    with open(video_path, "rb") as f:
        quiz_resp = requests.post(
            f"{API_V1}/quiz/draft",
            json={
                "course_id": str(course_id),
                "question_count": 3,
                "allowed_types": ["multiple_choice", "true_false", "essay"],
            },
            cookies=cookies,
            timeout=30,
        )
    print(f"  Quiz draft HTTP: {quiz_resp.status_code}")
    quiz_data = quiz_resp.json()
    print(f"  Quiz title: {quiz_data.get('title')}")
    print(f"  Total points: {quiz_data.get('total_points')}")
    print(f"  Questions: {len(quiz_data.get('questions', []))}")
    for q in quiz_data.get("questions", []):
        print(f"    Q{q['id']}: [{q['question_type']}] {q['question_text'][:100]}...")
    
    # Step 9: Ask tutor question from transcript
    print(f"\n[F9] Asking tutor question from transcript...")
    tutor_resp = requests.post(
        f"{API_V1}/tutor/chat",
        json={
            "message": "Explain Newtons first law of motion",
            "session_id": f"sess-{uuid.uuid4().hex[:8]}",
            "user_role": "teacher",
            "user_name": "E2E Test Teacher",
            "course_id": str(course_id),
        },
        cookies=cookies,
        timeout=30,
    )
    print(f"  Tutor HTTP: {tutor_resp.status_code}")
    tutor_data = tutor_resp.json()
    print(f"  Answer: {tutor_data.get('answer', '(empty)')[:300]}")
    print(f"  Is grounded: {tutor_data.get('is_grounded')}")
    print(f"  Citations: {len(tutor_data.get('citations', []))}")
    for c in tutor_data.get("citations", []):
        print(f"    - {c.get('lesson_title')}: {c.get('snippet', '(no snippet)')[:150]}")
    
    # Step 10: Test refusal case
    print(f"\n[F10] Testing tutor refusal for out-of-scope question...")
    tutor_resp2 = requests.post(
        f"{API_V1}/tutor/chat",
        json={
            "message": "Explain quantum entanglement",
            "session_id": f"sess-{uuid.uuid4().hex[:8]}",
            "user_role": "teacher",
            "user_name": "E2E Test Teacher",
            "course_id": str(course_id),
        },
        cookies=cookies,
        timeout=30,
    )
    print(f"  Tutor HTTP: {tutor_resp2.status_code}")
    tutor_data2 = tutor_resp2.json()
    print(f"  Answer: {tutor_data2.get('answer', '(empty)')[:300]}")
    print(f"  Is grounded: {tutor_data2.get('is_grounded')}")
    
    # Check refusal log in DB
    db = SessionLocal()
    try:
        from app.models.platform import AIRefusalLog
        refusal_logs = db.query(AIRefusalLog).filter(
            AIRefusalLog.institution_id == institution.id,
            AIRefusalLog.question_text.like("%quantum%"),
        ).all()
        print(f"  Refusal logs in DB: {len(refusal_logs)}")
        for rl in refusal_logs:
            print(f"    - id={rl.id}, question='{rl.question_text}', reason='{rl.reason}'")
    finally:
        db.close()
    
    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"  [F1] FFmpeg available: {os.path.isfile(ffmpeg_path)}")
    print(f"  [F2] Video generated: {video_path} ({video_size} bytes)")
    print(f"  [F3] DB fixtures: institution, teacher, course, module, lesson created")
    print(f"  [F4] Video uploaded: HTTP {'OK' if 200 <= upload_resp.status_code < 300 else 'FAIL'}")
    print(f"  [F5] Indexing: {indexing_status or 'not polled'}")
    print(f"  [F6] Transcript: {transcript[:100] if transcript else '(empty)'}")
    print(f"  [F7] HTTP 206 Range: {http_code == '206'} (got {http_code})")
    print(f"  [F8] Quiz draft: {len(quiz_data.get('questions', []))} questions")
    print(f"  [F9] Tutor grounded answer: {tutor_data.get('is_grounded')}")
    print(f"  [F10] Tutor refusal logged: {len(refusal_logs) if 'refusal_logs' in dir() else '?'}")
    print(f"\n{'=' * 70}")
    print("E2E Pipeline Test Complete")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    import shutil
    main()
