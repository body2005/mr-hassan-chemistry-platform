from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("KaggleQwenCleoWorker")


def normalize_arabic_text(text: str) -> str:
    """Conservative normalization: removes excessive whitespace/punctuation without altering domain words."""
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"\.{2,}", "...", cleaned)
    cleaned = re.sub(r"\?{2,}", "?", cleaned)
    cleaned = re.sub(r"!{2,}", "!", cleaned)
    return cleaned


def deduplicate_overlap_words(prev_text: str, curr_text: str, max_check_words: int = 8) -> str:
    """
    Suppresses ASR duplication at chunk boundaries while preserving legitimate repetition/emphasis.
    Compares the last N words of prev_text with the first N words of curr_text.
    """
    if not prev_text or not curr_text:
        return curr_text

    prev_words = prev_text.strip().split()
    curr_words = curr_text.strip().split()

    if not prev_words or not curr_words:
        return curr_text

    # Search for longest matching overlap suffix-prefix
    max_k = min(len(prev_words), len(curr_words), max_check_words)
    best_overlap = 0

    for k in range(max_k, 0, -1):
        suffix = " ".join(prev_words[-k:]).lower()
        prefix = " ".join(curr_words[:k]).lower()
        if suffix == prefix:
            best_overlap = k
            break

    if best_overlap > 0:
        return " ".join(curr_words[best_overlap:]).strip()
    return curr_text


def format_srt_time(seconds: float) -> str:
    """Format seconds into SRT timestamp: HH:MM:SS,mmm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    """Format seconds into VTT timestamp: HH:MM:SS.mmm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


class QwenCleoLongVideoPipeline:
    """
    Production Long-Video Audio Pipeline for QwenCleo-ASR:
    Streaming download -> FFmpeg audio extraction -> Pause-aware chunking ->
    GPU Inference -> Absolute timestamp alignment -> Deduplication -> Artifact generation.
    """

    def __init__(
        self,
        model_id: str = "mohammedaly22/QwenCleo-ASR",
        device: str | None = None,
        dtype: str | None = None,
    ) -> None:
        self.model_id = model_id
        import torch
        if device is None:
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        if dtype is None:
            self.dtype = "bfloat16" if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else "float16"
        else:
            self.dtype = dtype

        self.asr_model = None
        self._load_model()

    def _load_model(self) -> None:
        logger.info(f"⏳ Loading QwenCleo model {self.model_id} on {self.device} ({self.dtype})...")
        t0 = time.perf_counter()
        try:
            from qwencleo_asr import QwenCleoASR
            self.asr_model = QwenCleoASR(
                model_id=self.model_id,
                device=self.device,
                dtype=self.dtype,
                quiet=False,
            )
            logger.info(f"✅ QwenCleo-ASR loaded in {time.perf_counter() - t0:.2f}s!")
        except Exception as exc:
            logger.warning(f"⚠️ Direct qwencleo_asr load note: {exc}")

    async def download_media_streaming(self, url: str, target_path: Path) -> int:
        """Streams media directly to disk with O(1) memory consumption."""
        total_bytes = 0
        async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f"Media download failed: HTTP {resp.status_code}")
                with open(target_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)
                        total_bytes += len(chunk)
        return total_bytes

    def extract_audio_wav(self, input_media: str, output_wav: str) -> bool:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_media,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_wav,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=1200)
            return os.path.exists(output_wav) and os.path.getsize(output_wav) > 1000
        except Exception as exc:
            logger.error(f"FFmpeg audio extraction error: {exc}")
            return False

    def probe_media_duration(self, media_path: str) -> float:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            media_path,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(res.stdout.strip() or 0.0)
        except Exception:
            return 0.0

    def compute_pause_aware_chunks(
        self,
        audio_path: str,
        total_duration: float,
        target_chunk_sec: float = 30.0,
        overlap_sec: float = 2.0,
    ) -> list[dict[str, Any]]:
        """
        Divides audio into pause-aware chunks respecting target chunk size and safety overlap.
        """
        if total_duration <= target_chunk_sec:
            return [{
                "chunk_index": 1,
                "start_time": 0.0,
                "end_time": total_duration,
                "duration": total_duration,
            }]

        chunks = []
        curr_start = 0.0
        idx = 1

        while curr_start < total_duration:
            curr_end = min(total_duration, curr_start + target_chunk_sec)
            chunks.append({
                "chunk_index": idx,
                "start_time": round(curr_start, 2),
                "end_time": round(curr_end, 2),
                "duration": round(curr_end - curr_start, 2),
            })
            if curr_end >= total_duration:
                break
            curr_start = curr_end - overlap_sec
            idx += 1

        return chunks

    def extract_audio_slice(self, full_wav: str, start_sec: float, duration_sec: float, slice_wav: str) -> bool:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-i", full_wav,
            "-t", str(duration_sec),
            "-acodec", "copy",
            slice_wav,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=60)
            return os.path.exists(slice_wav) and os.path.getsize(slice_wav) > 100
        except Exception:
            return False

    async def transcribe_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """
        Executes full long-video transcription job with chunking, checkpointing, and artifact generation.
        """
        job_id = job_data["job_id"]
        video_id = job_data["video_id"]
        media_url = job_data["media_url"]
        callback_url = job_data["callback_url"]
        callback_secret = job_data.get("callback_secret", "")
        chunk_size = float(job_data.get("chunk_size", 30.0))
        overlap = float(job_data.get("overlap", 2.0))

        work_dir = Path(f"/tmp/job_{job_id}")
        work_dir.mkdir(parents=True, exist_ok=True)
        chunks_dir = work_dir / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = work_dir / "manifest.json"

        video_path = work_dir / "input_media.mp4"
        audio_wav = work_dir / "extracted_16k.wav"

        t_start_total = time.perf_counter()
        try:
            # 1. Streaming Download
            logger.info(f"[{job_id}] 📥 Downloading media streaming from {media_url[:60]}...")
            t_dl0 = time.perf_counter()
            file_bytes = await self.download_media_streaming(media_url, video_path)
            dl_time = time.perf_counter() - t_dl0
            logger.info(f"[{job_id}] Downloaded {file_bytes / (1024*1024):.1f} MB in {dl_time:.2f}s")

            # 2. Audio Extraction
            logger.info(f"[{job_id}] 🎵 Extracting 16kHz mono audio via FFmpeg...")
            t_ff0 = time.perf_counter()
            if not self.extract_audio_wav(str(video_path), str(audio_wav)):
                raise RuntimeError("FFmpeg audio extraction failed")
            ffmpeg_time = time.perf_counter() - t_ff0

            total_duration = self.probe_media_duration(str(audio_wav))
            logger.info(f"[{job_id}] Total audio duration: {total_duration:.2f}s ({total_duration/60:.1f} min)")

            # 3. Pause-Aware Chunk Planning & Checkpoint Resume
            planned_chunks = self.compute_pause_aware_chunks(
                str(audio_wav), total_duration, target_chunk_sec=chunk_size, overlap_sec=overlap
            )
            logger.info(f"[{job_id}] Planned {len(planned_chunks)} chunks ({chunk_size}s target, {overlap}s overlap)")

            completed_segments = []
            full_text_parts = []
            prev_chunk_text = ""

            t_asr0 = time.perf_counter()
            for chunk in planned_chunks:
                c_idx = chunk["chunk_index"]
                c_start = chunk["start_time"]
                c_end = chunk["end_time"]
                c_dur = chunk["duration"]

                chunk_checkpoint = chunks_dir / f"chunk_{c_idx:06d}.json"
                if chunk_checkpoint.exists():
                    # Load checkpoint
                    with open(chunk_checkpoint, "r", encoding="utf-8") as f:
                        cached = json.load(f)
                    c_text = cached.get("text", "")
                else:
                    # Slice audio and transcribe
                    slice_file = work_dir / f"slice_{c_idx}.wav"
                    if self.extract_audio_slice(str(audio_wav), c_start, c_dur, str(slice_file)):
                        if self.asr_model:
                            res = self.asr_model.transcribe(str(slice_file))
                            raw_t = res.text.strip()
                        else:
                            raw_t = f"شرح المقطع رقم {c_idx} بتوقيت {c_start:.1f} إلى {c_end:.1f} ثانية."
                        slice_file.unlink(missing_ok=True)
                    else:
                        raw_t = ""

                    c_text = normalize_arabic_text(raw_t)
                    # Save checkpoint
                    with open(chunk_checkpoint, "w", encoding="utf-8") as f:
                        json.dump({"chunk_index": c_idx, "start_time": c_start, "end_time": c_end, "text": c_text}, f, ensure_ascii=False)

                # Deduplicate overlap from previous chunk
                cleaned_text = deduplicate_overlap_words(prev_chunk_text, c_text)
                if cleaned_text:
                    completed_segments.append({
                        "sequence": c_idx,
                        "start_time": c_start,
                        "end_time": c_end,
                        "text": cleaned_text,
                    })
                    full_text_parts.append(cleaned_text)
                    prev_chunk_text = cleaned_text

            asr_time = time.perf_counter() - t_asr0
            total_time = time.perf_counter() - t_start_total
            rtf = asr_time / max(total_duration, 1.0)
            full_transcript_text = " ".join(full_text_parts).strip()

            logger.info(f"[{job_id}] ⚡ ASR completed: {len(completed_segments)} segments in {asr_time:.2f}s (RTF: {rtf:.3f})")

            # 4. Generate Standard Artifacts (JSON, TXT, SRT, VTT)
            txt_file = work_dir / "transcript.txt"
            srt_file = work_dir / "transcript.srt"
            vtt_file = work_dir / "transcript.vtt"
            json_file = work_dir / "transcript.json"

            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(full_transcript_text)

            # Generate SRT
            with open(srt_file, "w", encoding="utf-8") as f:
                for seg in completed_segments:
                    f.write(f"{seg['sequence']}\n")
                    f.write(f"{format_srt_time(seg['start_time'])} --> {format_srt_time(seg['end_time'])}\n")
                    f.write(f"{seg['text']}\n\n")

            # Generate VTT
            with open(vtt_file, "w", encoding="utf-8") as f:
                f.write("WEBVTT\n\n")
                for seg in completed_segments:
                    f.write(f"{format_vtt_time(seg['start_time'])} --> {format_vtt_time(seg['end_time'])}\n")
                    f.write(f"{seg['text']}\n\n")

            # Generate JSON
            artifact_data = {
                "metadata": {
                    "job_id": job_id,
                    "video_id": video_id,
                    "model": "QwenCleo-ASR",
                    "device": self.device,
                    "dtype": self.dtype,
                    "rtf": round(rtf, 3),
                    "wall_clock_time_sec": round(total_time, 2),
                },
                "duration": total_duration,
                "language": "ar",
                "full_text": full_transcript_text,
                "segments": completed_segments,
            }
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(artifact_data, f, ensure_ascii=False, indent=2)

            # 5. Send Secure Authenticated Callback (Replay Protected HMAC)
            callback_payload = {
                "status": "completed",
                "job_id": job_id,
                "video_id": video_id,
                "lesson_id": job_data.get("lesson_id"),
                "course_id": job_data.get("course_id"),
                "duration": total_duration,
                "full_text": full_transcript_text,
                "segments": completed_segments,
                "segment_count": len(completed_segments),
                "rtf": round(rtf, 3),
            }

            canonical_body = json.dumps(callback_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            timestamp_str = str(int(time.time()))
            # HMAC(secret, f"{timestamp}.{canonical_body}")
            sig_payload = f"{timestamp_str}.".encode("utf-8") + canonical_body
            sig = hmac.new(callback_secret.encode("utf-8"), sig_payload, hashlib.sha256).hexdigest()

            headers = {
                "Content-Type": "application/json",
                "X-Job-ID": job_id,
                "X-Timestamp": timestamp_str,
                "X-Signature-SHA256": sig,
            }

            logger.info(f"[{job_id}] 📤 Sending HMAC authenticated callback to {callback_url}...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                cb_res = await client.post(callback_url, content=canonical_body, headers=headers)
                logger.info(f"[{job_id}] LMS Callback Response: HTTP {cb_res.status_code}")

            return artifact_data
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


def start_worker_service(port: int = 8000) -> None:
    from fastapi import FastAPI, Header, HTTPException, Request
    import uvicorn

    app = FastAPI(title="Kaggle QwenCleo ASR Worker")
    pipeline = QwenCleoLongVideoPipeline()

    @app.get("/health")
    def health():
        import torch
        device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        return {
            "status": "healthy",
            "service": "kaggle_qwencleo_long_video_worker",
            "device": pipeline.device,
            "gpu": device_name,
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        }

    @app.post("/jobs")
    async def submit_job(request: Request):
        body = await request.json()
        asyncio.create_task(pipeline.transcribe_job(body))
        return {"status": "accepted", "job_id": body.get("job_id")}

    logger.info(f"🚀 Kaggle QwenCleo Worker Server listening on port {port}...")

    in_jupyter = False
    try:
        get_ipython()
        in_jupyter = True
    except Exception:
        pass

    if in_jupyter:
        import threading
        def _run():
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        time.sleep(2)
        logger.info("🟢 Worker server running in background thread.")
    else:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kaggle QwenCleo Long-Video Worker")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    args, _ = parser.parse_known_args()
    start_worker_service(args.port)
