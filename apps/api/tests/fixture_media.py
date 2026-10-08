"""QA-only WebM byte-boundary fixture, preserving the real media payload."""
import shutil
from pathlib import Path


def padded_webm(source: Path, destination: Path, size: int) -> None:
    with source.open('rb') as stream:
        header = stream.read(128)
    offset = header.find(b'\x18\x53\x80\x67')
    if offset < 0 or offset + 12 > len(header) or header[offset + 4] != 1:
        raise ValueError('Fixture must have a WebM Segment with an eight-byte size')
    payload_start = offset + 12
    payload_size = source.stat().st_size - payload_start
    declared = int.from_bytes(header[offset + 4:offset + 12], 'big') & ((1 << 56) - 1)
    if declared not in (payload_size, (1 << 56) - 1):
        raise ValueError('Existing Segment size does not match the source')
    remaining = size - source.stat().st_size - 9
    if remaining < 0 or size - payload_start >= (1 << 56) - 1:
        raise ValueError('Requested padded size is not representable')
    shutil.copyfile(source, destination)
    with destination.open('r+b') as target:
        # FFmpeg's seekable output uses a KNOWN Segment length. Enlarge that
        # length so the appended EBML Void is INSIDE the same valid Segment.
        # Unknown-length original fixtures are supported too. No media bytes
        # or SeekHead offsets relative to the Segment payload are changed.
        target.seek(offset + 4)
        target.write(((size - payload_start) | (1 << 56)).to_bytes(8, 'big'))
        target.seek(0, 2)
        target.write(b'\xec' + (remaining | (1 << 56)).to_bytes(8, 'big'))
        target.truncate(size)
