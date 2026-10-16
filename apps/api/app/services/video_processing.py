"""Bounded local HLS encoder. This is adaptive streaming, NOT licensed DRM.

Run only in the separate video-worker image. No HTTP/remote input protocols,
no shell evaluation, no filenames supplied by the client, no stderr URLs in logs.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import shutil
import time
from pathlib import Path

# Applies only to new generations. Existing playlists remain readable unchanged.
LADDER = ((360, 800_000), (480, 1_400_000), (720, 2_800_000), (1080, 5_000_000))


class InvalidVideo(ValueError):
    pass


def cpu_budget() -> int:
    """Respect container CPU quota/affinity, not the host's advertised cores."""
    cores = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    try:
        cores = min(cores, max(1, int(os.environ.get("VIDEO_ENCODING_CPU_BUDGET", "2"))))
    except ValueError:
        cores = min(cores, 2)
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota != "max":
            cores = min(cores, max(1, int(quota) // int(period)))
    except (OSError, ValueError, ZeroDivisionError):
        try:
            quota = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
            period = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
            if quota > 0:
                cores = min(cores, max(1, quota // period))
        except (OSError, ValueError, ZeroDivisionError):
            pass
    return max(1, min(cores, 8))


def memory_budget() -> int:
    budget = 2 * 1024**3
    for name in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            limit = int(Path(name).read_text())
            # Leave memory for the worker, uploader and runtime outside FFmpeg.
            budget = min(budget, max(0, limit - 256 * 1024**2))
        except (OSError, ValueError):
            continue
    if budget < 512 * 1024**2:
        raise InvalidVideo("VIDEO_WORKER_MEMORY_TOO_LOW")
    return budget


def _run(argv: list[str], timeout: int, capture=False, workspace: Path | None = None, progress=None, file_limit=256 * 1024**2):
    # Linux only, launched in a memory/CPU/pids-limited container. Output has
    # fixed size via RLIMIT_FSIZE; JSON probe selects only bounded stream fields.
    memory, cores = memory_budget(), cpu_budget()
    def check_workspace():
        used = 0
        for path in workspace.rglob("*"):
            try:
                if path.is_file():
                    used += path.stat().st_size
            except FileNotFoundError:
                # HLS temp_file atomically renames completed segments while
                # this monitor runs. Check the stable final files again at EOF.
                continue
        if used > 24 * 1024**3 or shutil.disk_usage(workspace).free < 1024**3:
            raise InvalidVideo("VIDEO_OUTPUT_LIMIT_EXCEEDED")

    capture_limit = 2 * 1024**2
    if capture:
        file_limit = min(file_limit, capture_limit)
    if os.name == 'posix':
        # Heartbeat/upload threads make Python preexec_fn unsafe after fork.
        # A fresh interpreter applies exactly the same limits, then execs the
        # encoder/probe; subprocess remains free to use its safe spawn path.
        argv = [sys.executable, '-m', 'scripts.media_limits', str(memory),
                str(max(3600, timeout * cores)), str(file_limit), *argv]
    try:
        if workspace is not None:
            with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "OMP_THREAD_LIMIT": str(cores)},
                    ) as process:
                deadline = time.monotonic() + timeout
                try:
                    while process.poll() is None:
                        if time.monotonic() > deadline:
                            raise InvalidVideo("VIDEO_ENCODING_TIMEOUT")
                        check_workspace()
                        if progress is not None:
                            progress()
                        time.sleep(1)
                    if process.returncode != 0:
                        raise InvalidVideo("VIDEO_DECODE_FAILED")
                    check_workspace()
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            return None
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "OMP_THREAD_LIMIT": str(cores)}
        if capture:
            # ffprobe metadata can be attacker-sized (many tracks). Spool a
            # bounded result instead of retaining an unlimited PIPE in RAM.
            with tempfile.TemporaryFile() as captured:
                result = subprocess.run(argv, check=True, timeout=timeout, stdin=subprocess.DEVNULL,
                    stdout=captured, stderr=subprocess.DEVNULL, env=env)
                if captured.tell() > capture_limit:
                    raise InvalidVideo('VIDEO_INVALID_METADATA')
                captured.seek(0)
                data = captured.read(capture_limit + 1)
                if len(data) > capture_limit:
                    raise InvalidVideo('VIDEO_INVALID_METADATA')
                return subprocess.CompletedProcess(result.args, result.returncode, stdout=data)
        return subprocess.run(argv, check=True, timeout=timeout, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        raise InvalidVideo("VIDEO_DECODE_FAILED") from exc


def probe(source: Path) -> dict:
    data = _run(["ffprobe", "-v", "error", "-protocol_whitelist", "file", "-format_whitelist", "mov,matroska,webm",
        "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate:stream_side_data=rotation", "-of", "json", str(source)], 30, True)
    info = json.loads(data.stdout)
    videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    try:
        raw_duration = info.get("format", {}).get("duration")
        duration = float(raw_duration) if raw_duration is not None else None
        video = videos[0]
        width, height = int(video["width"]), int(video["height"])
        numerator, denominator = map(int, video["r_frame_rate"].split("/"))
        fps = numerator / denominator
        rotation = next((float(side["rotation"]) for side in video.get("side_data_list", []) if "rotation" in side), 0)
    except (ValueError, KeyError, IndexError, ZeroDivisionError) as exc:
        raise InvalidVideo("VIDEO_INVALID_METADATA") from exc
    if (duration is not None and (not math.isfinite(duration) or not 0 < duration <= 4 * 3600)) or not 2 <= width <= 7680 or not 2 <= height <= 4320 or width * height > 33_177_600 or not 0 < fps <= 120:
        raise InvalidVideo("VIDEO_LIMIT_EXCEEDED")
    if not math.isfinite(rotation):
        raise InvalidVideo("VIDEO_INVALID_METADATA")
    # FFmpeg autorotates before filtering (phone recordings can be portrait).
    if round(rotation) % 180 == 90:
        width, height = height, width
    return {"duration": duration, "width": width, "height": height, "codec": video.get('codec_name'),
        "has_audio": any(s.get("codec_type") == "audio" for s in info.get("streams", []))}


def renditions(height: int) -> list[tuple[int, int]]:
    selected = [r for r in LADDER if r[0] <= height]
    return selected or [(height - height % 2, 500_000)]  # Never invent/upscale 4K.


def encode(source: Path, output: Path, progress=None) -> tuple[dict, list[str]]:
    info = probe(source)
    master = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-INDEPENDENT-SEGMENTS"]
    ladder = renditions(info["height"])
    cores = cpu_budget()
    # Every rendition needs at least one encoder thread. On a two-vCPU worker
    # these bounded encoders share the container quota; they do not each get
    # two CPUs. Keep decoder/filter/lookahead pools small as well.
    auxiliary_threads = min(2, max(1, cores // 4))
    encoder_threads = min(2, max(1, (cores - 2 * auxiliary_threads) // len(ladder)))
    filters = ["[0:v:0]fps=30,split=" + str(len(ladder)) + "".join(f"[in{i}]" for i in range(len(ladder)))]
    dimensions = []
    for index, (height, bitrate) in enumerate(ladder):
        directory = output / f"{height}p"
        directory.mkdir(parents=True)
        # Round DOWN to even dimensions: neither axis can exceed the source.
        width = max(2, (info["width"] * height // info["height"]) // 2 * 2)
        dimensions.append((width, height))
        filters.append(f"[in{index}]scale={width}:{height},setsar=1[v{index}]")
    progress_file = output / "encoding.progress"
    args = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-xerror", "-progress", str(progress_file), "-stats_period", "2",
        "-filter_complex_threads", str(auxiliary_threads), "-filter_threads", str(auxiliary_threads),
        "-err_detect", "explode", "-protocol_whitelist", "file", "-format_whitelist", "mov,matroska,webm",
        "-threads", str(auxiliary_threads)]
    if info.get('codec') == 'av1':
        # The native AV1 decoder requires unavailable hardware on this worker.
        # Explicit software decoding still shares one bounded input decode.
        args += ['-c:v', 'libdav1d']
    args += ["-i", str(source), "-filter_complex", ";".join(filters)]
    for index, (height, bitrate) in enumerate(ladder):
        directory = output / f"{height}p"
        args += ["-t", "14401", "-map", f"[v{index}]", "-map", "0:a:0?", "-sn", "-dn", "-map_metadata", "-1",
            "-c:v", "libx264", "-threads:v", str(encoder_threads), "-preset", "veryfast",
            "-x264-params", f"threads={encoder_threads}:lookahead-threads=1:rc-lookahead=10:open-gop=0",
            "-pix_fmt", "yuv420p", "-r", "30", "-b:v", str(bitrate), "-maxrate", str(bitrate), "-bufsize", str(bitrate * 2),
            "-g", "180", "-keyint_min", "180", "-sc_threshold", "0", "-force_key_frames", "expr:gte(t,n_forced*6)",
            "-c:a", "aac", "-threads:a", "1", "-b:a", "128k", "-ac", "2", "-max_muxing_queue_size", "256"]
        if info["has_audio"]:
            args += ["-af", "aresample=async=1:first_pts=0"]
        args += ["-f", "hls", "-hls_time", "6", "-hls_playlist_type", "vod",
            "-hls_flags", "independent_segments+temp_file", "-hls_segment_filename", str(directory / "segment_%06d.ts"), str(directory / "index.m3u8")]

    def report():
        fraction = 0.0
        if info["duration"] and progress_file.exists():
            try:
                # FFmpeg appends updates for hours; only the last completed
                # out_time update is needed, not the entire growing history.
                with progress_file.open('rb') as stream:
                    stream.seek(max(0, progress_file.stat().st_size - 16 * 1024))
                    tail = stream.read(16 * 1024).decode('utf-8', errors='ignore')
                for line in tail.splitlines():
                    if line.startswith("out_time_us="):
                        try:
                            fraction = min(1.0, max(0.0, int(line.split("=", 1)[1]) / 1_000_000 / info["duration"]))
                        except ValueError:
                            pass
            except OSError:
                pass  # FFmpeg may be writing a progress update now.
        if progress:
            progress(min(84, 5 + int(80 * fraction)), "encoding:shared")
    report()
    # One finite budget for the entire graph; this is a safety bound, not an ETA.
    deadline = min(24 * 3600, max(3600, int((info["duration"] or 14400) * 3 * len(ladder) / cores)))
    try:
        _run(args, deadline, workspace=output, progress=report)
    finally:
        progress_file.unlink(missing_ok=True)

    segment_durations = None
    for index, (height, bitrate) in enumerate(ladder):
        directory = output / f"{height}p"
        playlist = (directory / "index.m3u8").read_text(encoding="utf-8")
        durations = [float(line.split(":", 1)[1].rstrip(",")) for line in playlist.splitlines() if line.startswith("#EXTINF:")]
        segments = [line for line in playlist.splitlines() if line and not line.startswith("#")]
        decoded_duration = sum(durations)
        if not math.isfinite(decoded_duration) or not 0 < decoded_duration <= 14400:
            raise InvalidVideo("VIDEO_DURATION_LIMIT_EXCEEDED")
        if ("#EXT-X-ENDLIST" not in playlist or len(segments) != len(durations)
                or any(not name.startswith("segment_") or not name.endswith(".ts") or Path(name).name != name
                    or not (directory / name).is_file() or (directory / name).stat().st_size == 0 for name in segments)):
            raise InvalidVideo("VIDEO_OUTPUT_INCOMPLETE")
        if segment_durations is not None and (len(durations) != len(segment_durations)
                or any(abs(a - b) > 0.05 for a, b in zip(durations, segment_durations))):
            raise InvalidVideo("VIDEO_RENDITIONS_NOT_ALIGNED")
        segment_durations = durations
        info["duration"] = decoded_duration
        width, actual_height = dimensions[index]
        master += [f"#EXT-X-STREAM-INF:BANDWIDTH={bitrate + (128000 if info['has_audio'] else 0)},RESOLUTION={width}x{actual_height}", f"{height}p/index.m3u8"]
    (output / "master.m3u8").write_text("\n".join(master) + "\n", encoding="utf-8")
    files = sorted(str(path.relative_to(output)).replace("\\", "/") for path in output.rglob("*") if path.is_file())
    if len(files) > 15000 or any(not name.endswith((".m3u8", ".ts")) for name in files):
        raise InvalidVideo("VIDEO_OUTPUT_LIMIT_EXCEEDED")
    if progress:
        progress(85, "encoding:shared")
    return info, files
