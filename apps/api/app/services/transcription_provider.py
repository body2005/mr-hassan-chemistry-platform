from __future__ import annotations

import abc
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any

from pydantic import BaseModel, Field

FFMPEG_CANDIDATES = [
    shutil.which("ffmpeg"),
    os.environ.get("FFMPEG_PATH"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe") if os.environ.get("LOCALAPPDATA") else None,
]
FFPROBE_CANDIDATES = [
    shutil.which("ffprobe"),
    os.environ.get("FFPROBE_PATH"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffprobe.exe") if os.environ.get("LOCALAPPDATA") else None,
]
PYTHON_EXE = sys.executable


class TranscriptSegmentData(BaseModel):
    sequence: int
    start_time: float
    end_time: float
    text: str


class TranscriptionResult(BaseModel):
    language: str = "ar"
    duration: float = 0.0
    full_text: str = ""
    segments: list[TranscriptSegmentData] = Field(default_factory=list)
    coverage_ratio: float = 1.0


def get_ffmpeg_path() -> str | None:
    for candidate in FFMPEG_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def get_ffprobe_path() -> str | None:
    for candidate in FFPROBE_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def get_media_duration_seconds(media_path: str) -> float | None:
    """Accurately probe the total duration of a media file using ffprobe."""
    ffprobe = get_ffprobe_path()
    if not ffprobe or not os.path.exists(media_path):
        return None
    try:
        cmd = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            media_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        dur_str = res.stdout.strip()
        return float(dur_str) if dur_str else None
    except Exception as exc:
        print(f"Error probing media duration for {media_path}: {exc}")
        return None


def extract_audio_track(
    video_path: str,
    output_audio_path: str,
    max_duration_sec: int | None = None,
) -> bool:
    """Extract 16kHz mono audio from entire video file without arbitrary limits."""
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
        print(f"Error extracting audio from {video_path}: {exc}")
        return False


class TranscriptionProvider(abc.ABC):
    @abc.abstractmethod
    async def transcribe(
        self,
        media_path: str,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe an audio or video file and return structured segments and metadata."""
        pass


class WhisperTranscriptionProvider(TranscriptionProvider):
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("WHISPER_MODEL", "small")

    async def transcribe(
        self,
        media_path: str,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptionResult:
        if not os.path.exists(media_path):
            raise FileNotFoundError(f"Media file not found: {media_path}")

        expected_duration = get_media_duration_seconds(media_path)

        # Check if media is video or audio
        is_audio = media_path.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))
        temp_audio = media_path if is_audio else os.path.join(
            tempfile.gettempdir(), f"audio_{uuid.uuid4().hex[:8]}.wav"
        )
        is_temp = not is_audio

        try:
            if not is_audio:
                # Extract FULL 16kHz mono audio
                success = extract_audio_track(media_path, temp_audio, max_duration_sec=None)
                if not success:
                    raise RuntimeError("Failed to extract full audio track from video file.")

            prompt_str = initial_prompt or (
                "شرح منهج الجيولوجيا والجيوفيزياء، التراكيب الجيولوجية الأولية والتكتونية، "
                "الطيات المحدبة والمقعرة، الفوالق والصدوع، الفالق العادي والمعكوس، "
                "الحائط العلوي والحائط السفلي، الصخور الرسوبية والمسامية، مصائد البترول والغاز الطبيعي والمياه الجوفية، "
                "أسطح عدم التوافق الزاوي والانقطاعي والمتباين، القشرة الأرضية والوشاح واللب."
            )
            lang = language or "ar"

            whisper_cmd = f"""
import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')

segments_out = []
full_text = ""
detected_lang = '{lang}'

try:
    from faster_whisper import WhisperModel
    model = WhisperModel('{self.model_name}', device='cpu', compute_type='int8', cpu_threads=8)
    segs, info = model.transcribe(
        r'{temp_audio}',
        language='{lang}',
        initial_prompt='''{prompt_str}''',
        beam_size=5,
        temperature=0.0
    )
    detected_lang = info.language or '{lang}'
    for s in segs:
        t_text = s.text.strip()
        if t_text:
            segments_out.append({{
                'sequence': len(segments_out) + 1,
                'start_time': float(s.start),
                'end_time': float(s.end),
                'text': t_text
            }})
    full_text = ' '.join(s['text'] for s in segments_out)
except Exception as fw_err:
    import whisper, torch
    torch.set_num_threads(8)
    model = whisper.load_model('{self.model_name}', device='cpu')
    res = model.transcribe(
        r'{temp_audio}',
        language='{lang}',
        initial_prompt='''{prompt_str}''',
        fp16=False
    )
    detected_lang = res.get('language', '{lang}')
    for s in res.get('segments', []):
        t_text = s.get('text', '').strip()
        if t_text:
            segments_out.append({{
                'sequence': len(segments_out) + 1,
                'start_time': float(s.get('start', 0.0)),
                'end_time': float(s.get('end', 0.0)),
                'text': t_text
            }})
    full_text = res.get('text', '').strip()

last_end = float(segments_out[-1]['end_time'] if segments_out else 0.0)
output = {{
    'language': detected_lang,
    'duration': last_end,
    'full_text': full_text,
    'segments': segments_out
}}
print('---STRUCTURED_OUTPUT_START---')
print(json.dumps(output, ensure_ascii=False))
print('---STRUCTURED_OUTPUT_END---')
"""
            python_bin = PYTHON_EXE if os.path.exists(PYTHON_EXE) else sys.executable
            timeout_sec = int(os.getenv("WHISPER_TIMEOUT", "14400"))
            proc = subprocess.run(
                [python_bin, "-c", whisper_cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout_sec,
            )

            stdout = proc.stdout
            if "---STRUCTURED_OUTPUT_START---" in stdout and "---STRUCTURED_OUTPUT_END---" in stdout:
                start = stdout.find("---STRUCTURED_OUTPUT_START---") + len("---STRUCTURED_OUTPUT_START---")
                end = stdout.find("---STRUCTURED_OUTPUT_END---")
                json_str = stdout[start:end].strip()
                data = json.loads(json_str)
                segments = [TranscriptSegmentData(**seg) for seg in data.get("segments", [])]
                
                final_dur = float(data.get("duration", 0.0))
                if expected_duration and expected_duration > final_dur:
                    coverage = final_dur / expected_duration
                else:
                    coverage = 1.0

                return TranscriptionResult(
                    language=data.get("language", "ar"),
                    duration=expected_duration if expected_duration else final_dur,
                    full_text=data.get("full_text", "").strip(),
                    segments=segments,
                    coverage_ratio=coverage,
                )

            err_msg = proc.stderr or proc.stdout or "Whisper process returned invalid output."
            raise RuntimeError(f"Transcription failed: {err_msg[:300]}")

        finally:
            if is_temp and os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except OSError:
                    pass


class RemoteKaggleTranscriptionProvider(TranscriptionProvider):
    """
    Remote ASR Worker Provider:
    Connects the LMS platform to a GPU worker running on Kaggle / Colab via Ngrok or Cloudflare Tunnel.
    Automatically falls back to local Whisper if the remote server is unreachable.
    """
    def __init__(self, endpoint_url: str | None = None, fallback_provider: TranscriptionProvider | None = None) -> None:
        self.endpoint_url = endpoint_url or os.getenv("KAGGLE_ASR_URL") or os.getenv("REMOTE_ASR_URL")
        self.fallback = fallback_provider or WhisperTranscriptionProvider()

    async def transcribe(
        self,
        media_path: str,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptionResult:
        if not self.endpoint_url:
            return await self.fallback.transcribe(media_path, language, initial_prompt)

        import httpx
        expected_duration = get_media_duration_seconds(media_path)
        is_audio = media_path.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))
        temp_audio = media_path if is_audio else os.path.join(
            tempfile.gettempdir(), f"audio_{uuid.uuid4().hex[:8]}.mp3"
        )
        is_temp = not is_audio

        try:
            if not is_audio:
                success = extract_audio_track(media_path, temp_audio, max_duration_sec=None)
                if not success:
                    raise RuntimeError("Failed to extract audio track")

            timeout = httpx.Timeout(1800.0, connect=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                with open(temp_audio, "rb") as f:
                    files = {"file": (os.path.basename(temp_audio), f, "audio/mpeg")}
                    data = {"language": language or "ar"}
                    url = self.endpoint_url.rstrip("/")
                    if not url.endswith("/transcribe"):
                        url = f"{url}/transcribe"
                    response = await client.post(url, files=files, data=data)

                if response.status_code == 200:
                    res_json = response.json()
                    segments = [TranscriptSegmentData(**s) for s in res_json.get("segments", [])]
                    final_dur = float(res_json.get("duration", expected_duration or 0.0))
                    return TranscriptionResult(
                        language=res_json.get("language", "ar"),
                        duration=expected_duration or final_dur,
                        full_text=res_json.get("full_text", "").strip(),
                        segments=segments,
                        coverage_ratio=1.0,
                    )
                else:
                    print(f"[RemoteKaggleTranscriptionProvider] Error {response.status_code}: {response.text[:200]}. Falling back to local Whisper.")
                    return await self.fallback.transcribe(media_path, language, initial_prompt)
        except Exception as exc:
            print(f"[RemoteKaggleTranscriptionProvider] Remote call failed: {exc}. Falling back to local Whisper.")
            return await self.fallback.transcribe(media_path, language, initial_prompt)
        finally:
            if is_temp and os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except OSError:
                    pass


class MockTranscriptionProvider(TranscriptionProvider):
    async def transcribe(
        self,
        media_path: str,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptionResult:
        expected_duration = get_media_duration_seconds(media_path) or 120.0
        segments = [
            TranscriptSegmentData(sequence=1, start_time=0.0, end_time=15.0, text="مرحباً بكم في شرح مفاهيم الدرس الأساسية."),
            TranscriptSegmentData(sequence=2, start_time=15.0, end_time=60.0, text="في هذا المقطع سنتعرف على القوانين والمبادئ العلمية وكيفية تطبيقها."),
            TranscriptSegmentData(sequence=3, start_time=60.0, end_time=expected_duration, text="نستنتج أن العلاقة طردية بين المتغيرات وفق الشروط الابتدائية المدروسة في ختام الدرس."),
        ]
        full_text = " ".join(s.text for s in segments)
        return TranscriptionResult(
            language=language or "ar",
            duration=expected_duration,
            full_text=full_text,
            segments=segments,
            coverage_ratio=1.0,
        )


def get_transcription_provider() -> TranscriptionProvider:
    provider_type = os.getenv("TRANSCRIPTION_PROVIDER", "auto").lower()
    if provider_type == "mock" or os.getenv("APP_ENV") == "test":
        return MockTranscriptionProvider()
    try:
        from app.core.config import get_settings
        settings_url = get_settings().kaggle_asr_url
    except Exception:
        settings_url = None
    remote_url = os.getenv("KAGGLE_ASR_URL") or os.getenv("REMOTE_ASR_URL") or settings_url
    if remote_url and remote_url.strip():
        return RemoteKaggleTranscriptionProvider(remote_url.strip())
    return WhisperTranscriptionProvider()
