"""Bounded local HLS encoder. This is adaptive streaming, NOT licensed DRM.

Run only in the separate video-worker image. No HTTP/remote input protocols,
no shell evaluation, no filenames supplied by the client, no stderr URLs in logs.
"""
import json
import math
import os
import subprocess
import shutil
import time
from pathlib import Path

LADDER = ((360, 800_000), (480, 1_400_000), (720, 2_800_000), (1080, 5_000_000), (2160, 14_000_000))


class InvalidVideo(ValueError):
    pass


def _run(argv: list[str], timeout: int, capture=False, workspace: Path | None = None):
    # Linux only, launched in a memory/CPU/pids-limited container. Output has
    # fixed size via RLIMIT_FSIZE; JSON probe selects only bounded stream fields.
    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
    try:
        if workspace is not None:
            with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "OMP_THREAD_LIMIT": "2"},
                    preexec_fn=limits if os.name == "posix" else None) as process:
                deadline = time.monotonic() + timeout
                try:
                    while process.poll() is None:
                        if time.monotonic() > deadline:
                            raise InvalidVideo("VIDEO_ENCODING_TIMEOUT")
                        used = sum(path.stat().st_size for path in workspace.rglob("*") if path.is_file())
                        if used > 24 * 1024**3 or shutil.disk_usage(workspace).free < 1024**3:
                            raise InvalidVideo("VIDEO_OUTPUT_LIMIT_EXCEEDED")
                        time.sleep(1)
                    if process.returncode != 0:
                        raise InvalidVideo("VIDEO_DECODE_FAILED")
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            return None
        return subprocess.run(argv, check=True, timeout=timeout, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "OMP_THREAD_LIMIT": "2"},
            preexec_fn=limits if os.name == "posix" else None)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        raise InvalidVideo("VIDEO_DECODE_FAILED") from exc


def probe(source: Path) -> dict:
    data = _run(["ffprobe", "-v", "error", "-protocol_whitelist", "file", "-format_whitelist", "mov,matroska,webm",
        "-select_streams", "v:0", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "json", str(source)], 30, True)
    info = json.loads(data.stdout)
    videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    try:
        raw_duration = info.get("format", {}).get("duration")
        duration = float(raw_duration) if raw_duration is not None else None
        video = videos[0]
        width, height = int(video["width"]), int(video["height"])
        numerator, denominator = map(int, video["r_frame_rate"].split("/"))
        fps = numerator / denominator
    except (ValueError, KeyError, IndexError, ZeroDivisionError) as exc:
        raise InvalidVideo("VIDEO_INVALID_METADATA") from exc
    if (duration is not None and (not math.isfinite(duration) or not 0 < duration <= 4 * 3600)) or not 2 <= width <= 7680 or not 2 <= height <= 4320 or width * height > 33_177_600 or not 0 < fps <= 120:
        raise InvalidVideo("VIDEO_LIMIT_EXCEEDED")
    return {"duration": duration, "width": width, "height": height}


def renditions(height: int) -> list[tuple[int, int]]:
    selected = [r for r in LADDER if r[0] <= height]
    return selected or [(height - height % 2, 500_000)]  # Never invent/upscale 4K.


def encode(source: Path, output: Path) -> tuple[dict, list[str]]:
    info = probe(source)
    master = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-INDEPENDENT-SEGMENTS"]
    for height, bitrate in renditions(info["height"]):
        directory = output / f"{height}p"
        directory.mkdir(parents=True)
        args = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-xerror", "-err_detect", "explode", "-protocol_whitelist", "file", "-format_whitelist", "mov,matroska,webm",
            "-i", str(source), "-t", "14401", "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn", "-map_metadata", "-1",
            "-vf", f"scale=-2:{height},setsar=1", "-c:v", "libx264", "-threads", "2", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-r", "30", "-b:v", str(bitrate), "-maxrate", str(bitrate), "-bufsize", str(bitrate * 2),
            "-g", "180", "-keyint_min", "180", "-sc_threshold", "0", "-force_key_frames", "expr:gte(t,n_forced*6)",
            "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-f", "hls", "-hls_time", "6", "-hls_playlist_type", "vod",
            "-hls_flags", "independent_segments", "-hls_segment_filename", str(directory / "segment_%06d.ts"), str(directory / "index.m3u8")]
        _run(args, 3600, workspace=output)
        # WebM produced by MediaRecorder can legitimately omit Duration.
        # Validate the duration actually decoded, rather than rejecting it or
        # trusting a client hint. Do not silently truncate an overlong source.
        playlist = (directory / "index.m3u8").read_text(encoding="utf-8")
        decoded_duration = sum(float(line.split(":", 1)[1].rstrip(",")) for line in playlist.splitlines() if line.startswith("#EXTINF:"))
        if not 0 < decoded_duration <= 14400:
            raise InvalidVideo("VIDEO_DURATION_LIMIT_EXCEEDED")
        info["duration"] = decoded_duration
        width = round(info["width"] * height / info["height"] / 2) * 2
        master += [f"#EXT-X-STREAM-INF:BANDWIDTH={bitrate + 128000},RESOLUTION={width}x{height}", f"{height}p/index.m3u8"]
    (output / "master.m3u8").write_text("\n".join(master) + "\n", encoding="utf-8")
    files = sorted(str(path.relative_to(output)).replace("\\", "/") for path in output.rglob("*") if path.is_file())
    if len(files) > 15000:
        raise InvalidVideo("VIDEO_OUTPUT_LIMIT_EXCEEDED")
    return info, files
