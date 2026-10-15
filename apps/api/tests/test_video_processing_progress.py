from pathlib import Path
from app.services import video_processing as encoder


def test_encoder_uses_one_shared_graph_and_reports_actual_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(encoder, "probe", lambda source: {"duration": 1800, "width": 1920, "height": 1080, "has_audio": True})
    monkeypatch.setattr(encoder, "cpu_budget", lambda: 2)
    events = []
    calls = []
    def run(argv, timeout, capture=False, workspace=None, progress=None):
        calls.append((argv, timeout))
        progress_path = Path(argv[argv.index("-progress") + 1])
        progress_path.write_text("out_time_us=900000000\n")
        progress()
        for value in argv:
            if value.endswith("index.m3u8"):
                playlist = Path(value)
                playlist.write_text("#EXTM3U\n#EXTINF:1800,\nsegment_000000.ts\n#EXT-X-ENDLIST\n")
                (playlist.parent / "segment_000000.ts").write_bytes(b"segment")
    monkeypatch.setattr(encoder, "_run", run)
    info, files = encoder.encode(tmp_path / "source", tmp_path / "hls", progress=lambda percent, stage: events.append((percent, stage)))
    assert info["duration"] == 1800
    assert len(calls) == 1
    argv, timeout = calls[0]
    assert argv.count("-i") == 1
    assert "split=4" in argv[argv.index("-filter_complex") + 1]
    assert argv.count("-c:v") == 4
    assert argv.count("0:a:0?") == 4
    assert timeout == 10800
    assert all(argv[i + 1] == "1" for i, arg in enumerate(argv) if arg == "-threads:v")
    assert events[-1][0] == 85
    assert all(5 <= percent <= 85 for percent, _ in events)
    assert (45, "encoding:shared") in events
    assert all(stage == "encoding:shared" for _, stage in events)
    assert not any("progress" in name for name in files)
    assert len([name for name in files if name.endswith("index.m3u8")]) == 4
    manifest = (tmp_path / "hls/master.m3u8").read_text()
    assert "144p/" not in manifest and "240p/" not in manifest
    assert "RESOLUTION=1920x1080" in manifest


def test_ladder_never_upscales_and_keeps_a_small_source():
    assert [height for height, _ in encoder.renditions(720)] == [360, 480, 720]
    assert [height for height, _ in encoder.renditions(359)] == [358]
    assert [height for height, _ in encoder.renditions(240)] == [240]
