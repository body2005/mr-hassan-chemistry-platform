from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any

FFMPEG_CANDIDATES = [
    shutil.which("ffmpeg"),
    os.environ.get("FFMPEG_PATH"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe") if os.environ.get("LOCALAPPDATA") else None,
]

PYTHON_EXE = sys.executable


def get_ffmpeg_path() -> str | None:
    for candidate in FFMPEG_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def extract_audio(video_path: str, output_audio_path: str, max_duration_sec: int | None = None) -> bool:
    """Extract 16kHz mono audio from video file without arbitrary truncation."""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg or not os.path.exists(video_path):
        return False

    cmd = [ffmpeg, "-y"]
    if max_duration_sec is not None and max_duration_sec > 0:
        cmd.extend(["-t", str(max_duration_sec)])
    cmd.extend([
        "-i", video_path,
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "32k",
        output_audio_path,
    ])

    try:
        res = subprocess.run(cmd, capture_output=True, timeout=600, check=True)
        return os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 500
    except Exception as exc:
        print(f"Error extracting audio: {exc}")
        return False


def transcribe_video_file(video_path: str, language: str | None = None) -> str | None:
    """Transcribe spoken words from entire video file using Whisper."""
    if not os.path.exists(video_path):
        return None

    temp_audio = os.path.join(tempfile.gettempdir(), f"audio_{uuid.uuid4().hex[:8]}.mp3")
    try:
        success = extract_audio(video_path, temp_audio, max_duration_sec=None)
        if not success:
            return None

        lang_param = f"language='{language}', " if language else ""
        whisper_cmd = f"""
import sys, whisper, os
sys.stdout.reconfigure(encoding='utf-8')
model_name = os.getenv('WHISPER_MODEL', 'base')
model = whisper.load_model(model_name)
result = model.transcribe(
    r'{temp_audio}',
    {lang_param}initial_prompt='مراجعة وشرح تفصيلي باللغة العربية والإنجليزية لمفاهيم المنهج والدروس والامتحانات',
    fp16=False
)
print('---TRANSCRIPT_START---')
print(result['text'].strip())
print('---TRANSCRIPT_END---')
"""
        proc = subprocess.run(
            [PYTHON_EXE, "-c", whisper_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3600,
        )

        stdout = proc.stdout
        if "---TRANSCRIPT_START---" in stdout and "---TRANSCRIPT_END---" in stdout:
            start = stdout.find("---TRANSCRIPT_START---") + len("---TRANSCRIPT_START---")
            end = stdout.find("---TRANSCRIPT_END---")
            text = stdout[start:end].strip()
            return text if len(text) > 5 else None

        return None
    except Exception as exc:
        print(f"Transcription error: {exc}")
        return None
    finally:
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except OSError:
                pass
