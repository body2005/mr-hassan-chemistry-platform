#!/usr/bin/env python3
"""Generate a synthetic test video with voiceover using FFmpeg."""
import subprocess
import os
import uuid
import tempfile
import sys
import shutil

FFMPEG = (
    shutil.which("ffmpeg")
    or os.environ.get("FFMPEG_PATH")
    or (os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe") if os.environ.get("LOCALAPPDATA") else None)
    or "ffmpeg"
)
if not (os.path.isfile(FFMPEG) or shutil.which(FFMPEG)):
    print("ERROR: ffmpeg not found", file=sys.stderr)
    sys.exit(1)

tmpdir = tempfile.gettempdir()
video_path = os.path.join(tmpdir, f"e2e_video_{uuid.uuid4().hex[:8]}.mp4")

# Build audio with tone segments (syllable-like carriers)
# 0-1s: silence, 1-2s: 300Hz, 2-3s: 400Hz, 3-4s: 250Hz, 4-5s: silence
audio_cmd = [
    FFMPEG, "-y",
    "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono:d=5",
    "-af", "aevalsrc='if(gt(t,1)+gt(t,4),0,if(gt(t,2),400,if(gt(t,3),250,300)))':s=16000",
    "-ar", "16000", "-ac", "1",
    "-t", "5",
    "-c:a", "pcm_s16le",
    os.path.join(tmpdir, "e2e_audio.wav"),
]
print("Generating audio...", flush=True)
r = subprocess.run(audio_cmd, capture_output=True, text=True, timeout=60)
print(f"Audio gen returncode: {r.returncode}", flush=True)
if r.returncode != 0:
    print(f"Audio stderr: {r.stderr[-500:]}", flush=True)
    # Fallback: use simple sine as audio
    audio_cmd[2] = "sine=frequency=440:duration=5"
    audio_cmd[1] = "lavfi"
    audio_cmd.pop(3)  # remove aevalsrc filter
    audio_raw = [FFMPEG, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                 "-ar", "16000", "-ac", "1", "-t", "5", "-c:a", "pcm_s16le",
                 os.path.join(tmpdir, "e2e_audio.wav")]
    r = subprocess.run(audio_raw, capture_output=True, text=True, timeout=60)
    print(f"Fallback audio returncode: {r.returncode}", flush=True)
    if r.returncode != 0:
        print(f"Fallback stderr: {r.stderr[-300:]}", flush=True)
        sys.exit(1)

# Generate video (color background, 5s)
video_cmd = [
    FFMPEG, "-y",
    "-f", "lavfi", "-i", "color=c=#2b4a7f:size=640x360:d=5",
    "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
    "-c:v", "libx264", "-preset", "ultrafast",
    "-c:a", "aac", "-b:a", "32k",
    "-pix_fmt", "yuv420p",
    "-t", "5",
    video_path,
]
print("Generating video...", flush=True)
r = subprocess.run(video_cmd, capture_output=True, text=True, timeout=60)
print(f"Video gen returncode: {r.returncode}", flush=True)
if r.returncode != 0:
    print(f"Video stderr: {r.stderr[-500:]}", flush=True)
    sys.exit(1)

print(f"VIDEO_PATH={video_path}", flush=True)
print(f"VIDEO_SIZE={os.path.getsize(video_path)}", flush=True)
print(f"FFMPEG={FFMPEG}", flush=True)
