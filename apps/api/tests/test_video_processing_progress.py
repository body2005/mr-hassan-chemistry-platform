from pathlib import Path
from app.services import video_processing as encoder


def test_encoder_reports_actual_quality_progress_and_excludes_progress_files(tmp_path, monkeypatch):
    monkeypatch.setattr(encoder, "probe", lambda source: {"duration": 1800, "width": 1920, "height": 1080})
    events = []
    calls = []
    def run(argv, timeout, capture=False, workspace=None, progress=None):
        calls.append((argv, timeout))
        playlist = Path(argv[-1])
        progress_path = Path(argv[argv.index("-progress") + 1])
        progress_path.write_text("out_time_us=900000000\n")
        progress()
        playlist.write_text("#EXTM3U\n#EXTINF:1800,\nsegment_000000.ts\n")
        (playlist.parent / "segment_000000.ts").write_bytes(b"segment")
    monkeypatch.setattr(encoder, "_run", run)
    info, files = encoder.encode(tmp_path / "source", tmp_path / "hls", progress=lambda percent, stage: events.append((percent, stage)))
    assert info["duration"] == 1800
    assert len(calls) == 6
    assert all(argv[argv.index("-preset") + 1] == "veryfast" and timeout == 5400 for argv, timeout in calls)
    assert events[-1][0] == 85
    assert all(5 <= percent <= 85 for percent, _ in events)
    assert any("encoding:480p:4:6" == stage for _, stage in events)
    assert not any("progress" in name for name in files)
    assert len([name for name in files if name.endswith("index.m3u8")]) == 6
