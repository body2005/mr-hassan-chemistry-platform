"""Audio extraction and duration validation using FFmpeg."""
from __future__ import annotations
import os, shutil, subprocess
from typing import Optional

FFMPEG_CANDIDATES = [
    shutil.which("ffmpeg"),
    os.environ.get("FFMPEG_PATH"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe") if os.environ.get("LOCALAPPDATA") else None,
    "ffmpeg",
]
FFPROBE_CANDIDATES = [
    shutil.which("ffprobe"),
    os.environ.get("FFPROBE_PATH"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffprobe.exe") if os.environ.get("LOCALAPPDATA") else None,
    "ffprobe",
]

def get_ffmpeg_bin() -> str:
    for c in FFMPEG_CANDIDATES:
        if c and (os.path.isfile(c) or shutil.which(c)):
            return c
    return "ffmpeg"

def get_ffprobe_bin() -> str:
    for c in FFPROBE_CANDIDATES:
        if c and (os.path.isfile(c) or shutil.which(c)):
            return c
    return "ffprobe"

def get_audio_duration_seconds(file_path: str) -> float:
    ffprobe = get_ffprobe_bin()
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
        return float(res.stdout.strip())
    except Exception:
        import soundfile as sf
        return float(sf.info(file_path).duration)

def extract_16k_mono_audio(
    media_path: str,
    output_wav_path: str,
    start_sec: Optional[float] = None,
    duration_sec: Optional[float] = None
) -> str:
    ffmpeg = get_ffmpeg_bin()
    if not os.path.exists(media_path):
        raise FileNotFoundError(f"Media file not found: {media_path}")
    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
    cmd = [ffmpeg, "-y"]
    if start_sec is not None and start_sec > 0:
        cmd.extend(["-ss", f"{start_sec:.3f}"])
    cmd.extend(["-i", str(media_path)])
    if duration_sec is not None and duration_sec > 0:
        cmd.extend(["-t", f"{duration_sec:.3f}"])
    cmd.extend(["-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(output_wav_path)])
    proc = subprocess.run(cmd, capture_output=True, timeout=600)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"FFmpeg failed: {err}")
    return output_wav_path
