"""Private CBCS/CMAF packaging using Shaka; never uploads clear intermediates."""
import base64
import math
import os
import re
import tempfile
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.services.video_drm import new_content_key
from app.services.video_processing import InvalidVideo, _run


def package(clear: Path, output: Path, info: dict, progress=None) -> tuple[list[str], dict]:
    packager = Path(get_settings().video_drm_packager_path)
    if not packager.is_file() or not os.access(packager, os.X_OK):
        raise InvalidVideo('VIDEO_DRM_PACKAGER_NOT_CONFIGURED')
    raw_key, metadata = new_content_key()
    output.mkdir(parents=True, exist_ok=True)
    scratch = output.parent / 'drm-private'
    scratch.mkdir(mode=0o700)
    # The encoder remains one decode/split graph. This second FFmpeg process
    # only remuxes copies (no decoder/encoder), for Shaka's MP4 demuxer.
    variants = sorted(clear.glob('*p/index.m3u8'), key=lambda p: int(p.parent.name[:-1]))
    if not variants or len(variants) > 4:
        raise InvalidVideo('VIDEO_DRM_RENDITIONS_INVALID')
    inputs, outputs, descriptors = [], [], []
    for index, playlist in enumerate(variants):
        height = int(playlist.parent.name[:-1])
        if height > 1080 or (height >= 360 and height not in {360, 480, 720, 1080}):
            raise InvalidVideo('VIDEO_DRM_RENDITIONS_INVALID')
        source = scratch / f'{height}p.mp4'
        inputs += ['-protocol_whitelist', 'file', '-allowed_extensions', 'ts', '-i', str(playlist)]
        outputs += ['-map', f'{index}:v:0', '-map', f'{index}:a:0?', '-c', 'copy',
            '-movflags', '+frag_keyframe+empty_moov', str(source)]
        directory = output / f'{height}p'
        directory.mkdir()
        descriptors.append(f'in={source},stream=video,init_segment={directory}/init.mp4,segment_template={directory}/$Number$.m4s,playlist_name={height}p/index.m3u8,drm_label=CONTENT')
    _run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *inputs, *outputs], 3600,
        workspace=output.parent, file_limit=8 * 1024**3)
    if info['has_audio']:
        audio = output / 'audio'
        audio.mkdir()
        descriptors.append(f'in={scratch}/{variants[0].parent.name}.mp4,stream=audio,init_segment={audio}/init.mp4,segment_template={audio}/$Number$.m4s,playlist_name=audio/index.m3u8,hls_group_id=audio,hls_name=Audio,drm_label=CONTENT')
    # Raw key is in a worker-private flag file, never argv, storage or logs.
    fd, flags_name = tempfile.mkstemp(prefix='video-drm-', suffix='.flags', dir=scratch)
    flags = Path(flags_name)
    kid = uuid.UUID(metadata['key_id'])
    iv = base64.b64decode(metadata['iv']).hex()
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write('--enable_raw_key_encryption\n--protection_scheme=cbcs\n--protection_systems=Widevine,FairPlay\n')
            stream.write(f'--keys=label=CONTENT:key_id={kid.hex}:key={raw_key.hex()}:iv={iv}\n')
        expected = max(1, math.ceil(info['duration'] / 6) * len(descriptors))
        def report():
            if progress:
                progress(min(84, 75 + int(9 * len(list(output.rglob('*.m4s'))) / expected)), 'packaging:drm')
        # Shaka defaults to a clear lead. Every published segment must be
        # encrypted, including the first one; validation still checks outputs.
        _run([str(packager), *descriptors, f'--flagfile={flags}', '--clear_lead=0',
            '--segment_duration=6',
            '--fragment_duration=6', '--hls_playlist_type=VOD', f'--hls_key_uri=skd://{kid}:{iv}',
            f'--hls_master_playlist_output={output}/master.m3u8'], 3600,
            workspace=output.parent, progress=report)
    finally:
        flags.unlink(missing_ok=True)
        # Python cannot guarantee zeroization of every interpreter copy. The
        # isolated worker/filesystem/container remain part of the trust boundary.
        del raw_key
    files = validate_output(output, metadata, len(variants), info['has_audio'])
    if progress:
        progress(85, 'packaging:drm')
    return files, metadata


def validate_output(output: Path, metadata: dict, video_count: int, has_audio: bool) -> list[str]:
    files = sorted(p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file())
    if len(files) > 15000 or not files or any(not n.endswith(('.m3u8', '.mp4', '.m4s')) for n in files):
        raise InvalidVideo('VIDEO_DRM_OUTPUT_INVALID')
    master = (output / 'master.m3u8').read_text()
    if master.count('#EXT-X-STREAM-INF:') != video_count:
        raise InvalidVideo('VIDEO_DRM_OUTPUT_INCOMPLETE')
    allowed = set(files)
    aligned_durations = None
    for playlist in output.rglob('*.m3u8'):
        text = playlist.read_text()
        if playlist.name != 'master.m3u8':
            if ('#EXT-X-ENDLIST' not in text or 'METHOD=NONE' in text or 'METHOD=AES-128' in text
                or 'com.apple.streamingkeydelivery' not in text
                or 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed' not in text.lower()):
                raise InvalidVideo('VIDEO_DRM_OUTPUT_NOT_ENCRYPTED')
            durations = re.findall(r'#EXTINF:([0-9.]+)', text)
            if not durations:
                raise InvalidVideo('VIDEO_DRM_OUTPUT_INCOMPLETE')
            if playlist.parent.name.endswith('p'):
                actual = [float(value) for value in durations]
                if aligned_durations is not None and (len(actual) != len(aligned_durations)
                        or any(abs(a - b) > .05 for a, b in zip(actual, aligned_durations))):
                    raise InvalidVideo('VIDEO_RENDITIONS_NOT_ALIGNED')
                aligned_durations = actual
        for uri in [line for line in text.splitlines() if line and not line.startswith('#')] + re.findall(r'URI="([^"]+)"', text):
            if uri.startswith(('skd://', 'data:')):
                continue
            import posixpath
            target = posixpath.normpath(posixpath.join(playlist.parent.relative_to(output).as_posix(), uri))
            if target not in allowed:
                raise InvalidVideo('VIDEO_DRM_OUTPUT_INCOMPLETE')
    inits = list(output.rglob('init.mp4'))
    if len(inits) != video_count + int(has_audio):
        raise InvalidVideo('VIDEO_DRM_OUTPUT_INCOMPLETE')
    for init in inits:
        if init.stat().st_size > 1024 * 1024:
            raise InvalidVideo('VIDEO_DRM_OUTPUT_INVALID')
        data = init.read_bytes()
        if b'tenc' not in data or b'cbcs' not in data or uuid.UUID(metadata['key_id']).bytes not in data or not (b'encv' in data or b'enca' in data):
            raise InvalidVideo('VIDEO_DRM_OUTPUT_NOT_ENCRYPTED')
    # These are trusted packager outputs, not arbitrary client artifacts.
    # Still reject missing sample-encryption auxiliary information on segments.
    for name in files:
        path = output / name
        if not path.stat().st_size:
            raise InvalidVideo('VIDEO_DRM_OUTPUT_INCOMPLETE')
        if name.endswith('.m4s'):
            with path.open('rb') as stream:
                header = stream.read(1024 * 1024)
            if b'senc' not in header and not (b'saiz' in header and b'saio' in header):
                raise InvalidVideo('VIDEO_DRM_OUTPUT_NOT_ENCRYPTED')
    return files
