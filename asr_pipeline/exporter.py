"""Transcript Exporter supporting TXT, SRT, VTT, and Structured JSON."""
from __future__ import annotations
import json, os
from typing import List, Dict, Any

def format_timestamp_srt(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def format_timestamp_vtt(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

def export_all_formats(
    segments: List[Dict[str, Any]],
    output_dir: str,
    base_filename: str = "transcript",
    metadata: Dict[str, Any] | None = None
) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    exported_files = {}

    # 1. TXT Export
    txt_path = os.path.join(output_dir, f"{base_filename}.txt")
    full_text = " ".join(s["text"].strip() for s in segments if s.get("text", "").strip())
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_text + "\n")
    exported_files["txt"] = txt_path

    # 2. SRT Export
    srt_path = os.path.join(output_dir, f"{base_filename}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, s in enumerate(segments, 1):
            t_start = format_timestamp_srt(s["start_time"])
            t_end = format_timestamp_srt(s["end_time"])
            text = s["text"].strip()
            f.write(f"{i}\n{t_start} --> {t_end}\n{text}\n\n")
    exported_files["srt"] = srt_path

    # 3. VTT Export
    vtt_path = os.path.join(output_dir, f"{base_filename}.vtt")
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for i, s in enumerate(segments, 1):
            t_start = format_timestamp_vtt(s["start_time"])
            t_end = format_timestamp_vtt(s["end_time"])
            text = s["text"].strip()
            f.write(f"{i}\n{t_start} --> {t_end}\n{text}\n\n")
    exported_files["vtt"] = vtt_path

    # 4. JSON Export
    json_path = os.path.join(output_dir, f"{base_filename}.json")
    payload = {
        "metadata": metadata or {},
        "total_segments": len(segments),
        "full_text": full_text,
        "segments": segments
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    exported_files["json"] = json_path

    return exported_files
