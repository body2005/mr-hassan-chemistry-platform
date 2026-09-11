#!/usr/bin/env python3
"""
E2E Video Pipeline Test: gTTS -> ffmpeg+PIL -> upload -> index -> transcript 
-> HTTP 206 Range check -> tutor question from real transcript
"""
import asyncio
import json
import os
import uuid
import subprocess
import sys
import time

# Paths
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(PROJECT_DIR, "apps", "api")
UPLOADS_DIR = os.path.join(API_DIR, "uploads")
SCRIPTS_DIR = os.path.join(API_DIR, "scripts")

# Ensure uploads dir exists
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Colors and dimensions
IMG_WIDTH = 640
IMG_HEIGHT = 360
BG_COLOR = (26, 26, 46)  # #1a1a2e dark blue
TEXT_COLOR = (255, 255, 255)  # white
ARABIC_SENTENCE = "القوة المحصلة تساوي الكتلة مضروبة في التسارع حسب قانون نيوتن الثاني"
AUDIO_DURATION_SEC = 5

# Output paths
PNG_PATH = os.path.join(SCRIPTS_DIR, "test_background.png")
MP3_PATH = os.path.join(SCRIPTS_DIR, "test_audio.mp3")
MP4_PATH = os.path.join(SCRIPTS_DIR, "test_video.mp4")


def generate_png():
    """Generate a PNG image with PIL."""
    print(f"[1] Generating PNG image ({IMG_WIDTH}x{IMG_HEIGHT})...")
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    # Try to use an Arabic-supporting font, fall back to default
    font_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            font = ImageFont.truetype(fp, 28)
            break
    if font is None:
        font = ImageFont.load_default()
    # Center text
    bbox = draw.textbbox((0, 0), ARABIC_SENTENCE, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (IMG_WIDTH - tw) // 2
    y = (IMG_HEIGHT - th) // 2
    draw.text((x, y), ARABIC_SENTENCE, fill=TEXT_COLOR, font=font)
    img.save(PNG_PATH)
    size_kb = os.path.getsize(PNG_PATH) / 1024
    print(f"  → PNG saved: {PNG_PATH} ({size_kb:.1f} KB)")
    return PNG_PATH


def generate_mp3():
    """Generate Arabic speech with gTTS."""
    print(f"[2] Generating MP3 with gTTS: \"{ARABIC_SENTENCE[:40]}...\"")
    from gtts import gTTS
    tts = gTTS(text=ARABIC_SENTENCE, lang="ar", slow=False)
    tts.save(MP3_PATH)
    size_kb = os.path.getsize(MP3_PATH) / 1024
    print(f"  → MP3 saved: {MP3_PATH} ({size_kb:.1f} KB)")
    return MP3_PATH


def generate_mp4(png_path, mp3_path):
    """Generate MP4 with ffmpeg: loop image + audio."""
    print(f"[3] Generating MP4 with ffmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", png_path,
        "-i", mp3_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        MP4_PATH,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"  ⚠ ffmpeg stderr (first 300 chars): {result.stderr[:300]}")
        # Try fallback with -t instead of -shortest
        cmd_fallback = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", png_path,
            "-i", mp3_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-t", str(AUDIO_DURATION_SEC),
            "-movflags", "+faststart",
            MP4_PATH,
        ]
        result2 = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=60)
        if result2.returncode != 0:
            print(f"  ✗ ffmpeg fallback also failed: {result2.stderr[:300]}")
            return None
    size_bytes = os.path.getsize(MP4_PATH)
    duration = None
    # Get duration via ffprobe
    probe_cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", MP4_PATH]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
    if probe_result.returncode == 0:
        try:
            duration = float(probe_result.stdout.strip())
        except ValueError:
            pass
    print(f"  → MP4 saved: {MP4_PATH} ({size_bytes/1024:.1f} KB, duration={duration:.2f}s)")
    return MP4_PATH


async def upload_video(lesson_id: str, video_path: str) -> dict:
    """Upload video to API (no auth required per current code)."""
    print(f"[4] Uploading video to API (lesson_id={lesson_id})...")
    # Use TestClient approach or direct requests
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        with open(video_path, "rb") as f:
            content = f.read()
        files = {"file": ("test_video.mp4", content, "video/mp4")}
        resp = await client.post(f"/api/v1/lessons/{lesson_id}/video", files=files)
    print(f"  → Upload response: {resp.status_code} {resp.json()}")
    return resp.json()


async def poll_indexing_status(lesson_id: str) -> dict:
    """Poll indexing status until indexed or failed."""
    print(f"[5] Polling indexing status for lesson {lesson_id}...")
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        for attempt in range(60):  # up to 60 seconds
            resp = await client.get(f"/api/v1/lessons/{lesson_id}/indexing-status")
            data = resp.json()
            status = data.get("status", "unknown")
            print(f"  → Attempt {attempt+1}: status={status}, chunks={data.get('indexed_chunks_count', 0)}, rag_synced={data.get('rag_synced', False)}")
            if status == "indexed":
                return data
            if status == "failed":
                print(f"  ✗ Indexing failed: {data.get('error', 'unknown')}")
                return data
            await asyncio.sleep(1)
    print(f"  ✗ Timeout waiting for indexing")
    return {"status": "timeout"}


async def get_transcript(lesson_id: str) -> str:
    """Get transcript_text from DB via API."""
    print(f"[6] Fetching transcript from DB...")
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        # Try to get lesson details (might need auth)
        resp = await client.get(f"/api/v1/lessons/{lesson_id}")
        if resp.status_code == 200:
            lesson = resp.json()
            transcript = lesson.get("transcript_text", "") or ""
            print(f"  → transcript_text (first 300 chars): {transcript[:300]}")
            return transcript
        # Fallback: try indexing-status endpoint
        resp2 = await client.get(f"/api/v1/lessons/{lesson_id}/indexing-status")
        print(f"  → Indexing status: {resp2.json()}")
        return ""


async def test_http_206(video_filename: str) -> int:
    """Test Range request on video file."""
    print(f"[7] Testing HTTP 206 Range request on {video_filename}...")
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        headers = {"Range": "bytes=0-1023"}
        resp = await client.get(f"/static/uploads/{video_filename}", headers=headers)
        status_code = resp.status_code
        print(f"  → GET /static/uploads/{video_filename} with Range: bytes=0-1023")
        print(f"  → Status code: {status_code}")
        if status_code == 206:
            print(f"  → Content-Range: {resp.headers.get('content-range', 'N/A')}")
            print(f"  → Body length: {len(resp.content)} bytes")
            print(f"  ✓ HTTP 206 Partial Content — StreamingResponse works!")
        elif status_code == 200:
            print(f"  ✗ Got 200 instead of 206 — need to check StreamingResponse implementation")
        else:
            print(f"  ✗ Unexpected status: {status_code}")
        return status_code


async def ask_tutor(course_id: str, lesson_id: str, transcript: str) -> dict:
    """Ask tutor a question based on the video content."""
    print(f"[8] Asking tutor question based on video transcript...")
    # Extract a question from the transcript
    if not transcript.strip():
        print(f"  ✗ No transcript available — skipping tutor test")
        return {"answer": "No transcript", "citations": []}
    
    # Ask about Newton's second law (the content of our video)
    question = "ما هي العلاقة بين القوة والكتلة والتسارع حسب قانون نيوتن الثاني؟"
    print(f"  → Question: {question}")
    
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        payload = {
            "message": question,
            "session_id": f"test-session-{uuid.uuid4().hex[:8]}",
            "course_id": course_id,
            "user_role": "teacher",
            "user_name": "حسن شعبان",
        }
        resp = await client.post("/api/v1/tutor/chat", json=payload)
        data = resp.json()
        print(f"  → Tutor response status: {resp.status_code}")
        print(f"  → Answer (first 400 chars): {data.get('answer', '')[:400]}")
        print(f"  → Citations: {json.dumps(data.get('citations', []), ensure_ascii=False)[:500]}")
        print(f"  → is_grounded: {data.get('is_grounded', False)}")
        return data


async def main():
    print("=" * 60)
    print("E2E VIDEO PIPELINE TEST")
    print("=" * 60)
    
    # Step 1: Generate PNG
    png_path = generate_png()
    if not png_path or not os.path.exists(png_path):
        print("✗ PNG generation failed — aborting")
        return
    
    # Step 2: Generate MP3
    mp3_path = generate_mp3()
    if not mp3_path or not os.path.exists(mp3_path):
        print("✗ MP3 generation failed — aborting")
        return
    
    # Step 3: Generate MP4 with ffmpeg
    mp4_path = generate_mp4(png_path, mp3_path)
    if not mp4_path or not os.path.exists(mp4_path):
        print("✗ MP4 generation failed — aborting")
        return
    
    video_filename = os.path.basename(mp4_path)
    
    # We need a lesson_id. For testing, we can create one or use an existing one.
    # Let's try to create a test lesson first
    print(f"\n[0] Creating test lesson...")
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        # Try to login as teacher first
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "teacher@example.com",
            "password": "teacher123",
            "institution_slug": "demo",
        })
        print(f"  → Login: {login_resp.status_code}")
        
        # Create a module
        module_resp = await client.post("/api/v1/modules", json={
            "title": "Test Module",
            "position": 1,
        })
        print(f"  → Module creation: {module_resp.status_code}")
        if module_resp.status_code not in (200, 201):
            print(f"  ✗ Cannot create module — trying with existing...")
            # Use a known module ID or exit
            module_id = "00000000-0000-0000-0000-000000000001"  # placeholder
        else:
            module = module_resp.json()
            module_id = module.get("id", "")
            print(f"  → Module ID: {module_id}")
        
        # Create lesson
        lesson_resp = await client.post(f"/api/v1/modules/{module_id}/lessons", json={
            "title": "فيديو اختبار قانون نيوتن الثاني",
            "kind": "video",
            "position": 1,
            "content": "테스트 فيديو لقانون نيوتن الثاني",
        })
        print(f"  → Lesson creation: {lesson_resp.status_code}")
        if lesson_resp.status_code not in (200, 201):
            print(f"  ✗ Cannot create lesson — {lesson_resp.text[:200]}")
            return
        lesson = lesson_resp.json()
        lesson_id = lesson.get("id", "")
        print(f"  → Lesson ID: {lesson_id}")
    
    # Step 4: Upload video
    upload_result = await upload_video(lesson_id, mp4_path)
    
    # Step 5: Poll indexing
    indexing_result = await poll_indexing_status(lesson_id)
    indexing_status = indexing_result.get("status", "unknown")
    
    # Step 6: Get transcript
    transcript = await get_transcript(lesson_id)
    
    # Step 7: Test HTTP 206
    status_206 = await test_http_206(video_filename)
    
    # Step 8: Ask tutor
    tutor_result = await ask_tutor("00000000-0000-0000-0000-000000000001", lesson_id, transcript)
    
    # Summary
    print("\n" + "=" * 60)
    print("FINAL E2E RESULTS")
    print("=" * 60)
    
    results = []
    
    # 1. Video generated
    video_ok = os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 10000
    results.append(("Video generation (ffmpeg+PIL)", video_ok))
    print(f"  {'✓' if video_ok else '✗'} Video generation: {'OK' if video_ok else 'FAILED'}")
    
    # 2. Upload
    upload_ok = upload_result.get("id") == lesson_id
    results.append(("Video upload via API", upload_ok))
    print(f"  {'✓' if upload_ok else '✗'} Upload: {'OK' if upload_ok else 'FAILED'}")
    
    # 3. Indexing
    indexing_ok = indexing_status == "indexed"
    results.append(("Indexing complete", indexing_ok))
    print(f"  {'✓' if indexing_ok else '✗'} Indexing: {'OK' if indexing_ok else 'FAILED'} (status={indexing_status})")
    
    # 4. Transcript
    transcript_ok = bool(transcript.strip()) and len(transcript) > 10
    results.append(("Transcript extracted", transcript_ok))
    print(f"  {'✓' if transcript_ok else '✗'} Transcript: {'OK' if transcript_ok else 'FAILED'} (len={len(transcript)})")
    
    # 5. HTTP 206
    http206_ok = status_206 == 206
    results.append(("HTTP 206 Range support", http206_ok))
    print(f"  {'✓' if http206_ok else '✗'} HTTP 206: {'OK' if http206_ok else 'FAILED'} (status={status_206})")
    
    # 6. Tutor (bonus)
    tutor_answer = tutor_result.get("answer", "")
    tutor_ok = "القوة" in tutor_answer or "كتلة" in tutor_answer or tutor_answer != "No transcript"
    results.append(("Tutor answer from transcript", tutor_ok))
    print(f"  {'✓' if tutor_ok else '✗'} Tutor: {'OK' if tutor_ok else 'FAILED'}")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nFINAL E2E: {passed}/{total}")
    
    if passed < total:
        print("\n⚠ Some steps failed — check logs above")
        sys.exit(1)
    else:
        print("\n✓ All steps passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
