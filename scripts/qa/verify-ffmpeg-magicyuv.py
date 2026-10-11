"""Verify the upstream MagicYUV fix in the pinned release, not an exploit test.

Only the expected regular source member is copied into a temporary directory.
No runtime binary is changed and no uploaded media/third-party PoC is executed.
Run with the same release archive SHA recorded by build_native_ffmpeg.sh.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile


RELEASE_SHA = 'de668509caf9e35e3cd162473441fdb29538c6d96ed080292b3cf9e6fc5d558f'
PATCH_SHA = 'a18ad773eab74dbd268f82933cc9bf93d77ac959afbb9be12abb5e6d62ba5d5f'
COMMIT = '15882781ac5267a653e4e55f5fa656ba9db688fd'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--patch', type=Path, required=True)
    parser.add_argument('--git', default='git')
    args = parser.parse_args()
    archive = args.archive.resolve(strict=True)
    patch = args.patch.resolve(strict=True)
    assert archive.is_file() and archive.stat().st_size <= 32 * 1024 * 1024
    assert patch.is_file() and patch.stat().st_size <= 64 * 1024
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == RELEASE_SHA
    patch_bytes = patch.read_bytes()
    assert hashlib.sha256(patch_bytes).hexdigest() == PATCH_SHA
    assert patch_bytes.startswith(('From ' + COMMIT + ' ').encode())
    with tarfile.open(archive, 'r:xz') as release:
        member = release.getmember('ffmpeg-7.1.5/libavcodec/magicyuv.c')
        assert member.isfile() and member.size <= 1024 * 1024
        with release.extractfile(member) as stream:
            source = stream.read()
    with tempfile.TemporaryDirectory(prefix='qa-magicyuv-') as scratch:
        target = Path(scratch) / 'libavcodec' / 'magicyuv.c'
        target.parent.mkdir()
        target.write_bytes(source)
        # Check-only: fails if the exact patch's fixed side is not present.
        checked = subprocess.run([args.git, 'apply', '--no-index', '--reverse',
            '--check', '--whitespace=error', str(patch)], cwd=scratch,
            text=True, capture_output=True, check=False)
        assert checked.returncode == 0, checked.stderr
        assert target.read_bytes() == source, 'Check-only must never edit the source'
    blob = hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest()
    print(json.dumps({'passed': 3, 'failed': 0, 'skipped': 0,
        'source_release': '7.1.5', 'release_sha256': RELEASE_SHA,
        'upstream_fix_commit': COMMIT, 'patch_sha256': PATCH_SHA,
        'source_git_blob_sha1': blob, 'reverse_check_exit': checked.returncode,
        'boundary': 'Pinned upstream source includes this exact fix; no per-CVE binary exploit proof. Raw scanner findings remain open.'}))


if __name__ == '__main__':
    main()
