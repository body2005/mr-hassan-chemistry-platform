"""Read-only checks against the ACTUAL restricted encoder, not a mutable tag.

Run through `verify-native-video.ps1` after rebuilding chemistryaudit2.
These are binary/configuration checks, not six crafted-CVE exploit tests.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

VERSION = '9.0.2'
SOURCE_SHA = '8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e'
SIGNER = 'FCF986EA15E6E293A5644F10B4322F04D67658D8'
PROVENANCE = Path('/usr/local/share/chemistry-native/ffmpeg')


def command(program, *arguments):
    result = subprocess.run([program, *arguments], capture_output=True, text=True, timeout=15, check=True,
                            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    return result.stdout


def codecs(output):
    return set(re.findall(r'^\s*\S{6}\s+(\S+)\s', output, re.MULTILINE))


class NativeVideo(unittest.TestCase):
    def test_actual_ffmpeg_and_ffprobe_version(self):
        for program in ('ffmpeg', 'ffprobe'):
            self.assertRegex(command(program, '-version').splitlines()[0], rf'^{program} version {re.escape(VERSION)}(?:\s|$)')

    def test_signed_pinned_source_provenance(self):
        source = PROVENANCE / 'source.txt'
        signature = PROVENANCE / 'signature.txt'
        for item in (source, signature, PROVENANCE / 'decoders.txt'):
            self.assertEqual(item.stat().st_uid, 0)
            self.assertFalse(item.stat().st_mode & 0o022, 'Provenance must not be group/world writable')
            self.assertFalse(os.access(item, os.W_OK), 'Runtime user must not write native provenance')
        metadata = source.read_text()
        self.assertIn(f'https://ffmpeg.org/releases/ffmpeg-{VERSION}.tar.xz', metadata)
        self.assertIn('Source-SHA256: ' + SOURCE_SHA, metadata)
        self.assertIn('Signer: ' + SIGNER, metadata)
        self.assertIn('[GNUPG:] VALIDSIG ' + SIGNER + ' ', signature.read_text())

    def test_rasc_decoder_removed_in_build_and_actual_binary(self):
        self.assertIn('--disable-decoder=rasc', command('ffmpeg', '-buildconf'))
        self.assertNotIn('rasc', codecs(command('ffmpeg', '-v', 'quiet', '-decoders')))
        self.assertNotIn('rasc', codecs((PROVENANCE / 'decoders.txt').read_text()))

    def test_no_network_input_or_output_protocols(self):
        protocols = set(command('ffmpeg', '-v', 'quiet', '-protocols').split())
        self.assertIn('file', protocols)
        self.assertFalse(protocols & {'http', 'https', 'ftp', 'tcp', 'udp', 'tls', 'rist', 'rtmp', 'srt'})

    def test_no_hardware_acceleration(self):
        lines = command('ffmpeg', '-v', 'quiet', '-hwaccels').splitlines()
        self.assertEqual([line.strip() for line in lines if line.strip() and line.strip() != 'Hardware acceleration methods:'], [])

    def test_common_codecs_and_hls_remain_available(self):
        decoders = codecs(command('ffmpeg', '-v', 'quiet', '-decoders'))
        encoders = codecs(command('ffmpeg', '-v', 'quiet', '-encoders'))
        self.assertTrue({'h264', 'hevc', 'vp8', 'vp9', 'aac', 'opus'} <= decoders)
        self.assertTrue({'libx264', 'aac'} <= encoders)
        self.assertRegex(command('ffmpeg', '-v', 'quiet', '-muxers'), r'(?m)^\s*E\s+hls\s')


if __name__ == '__main__':
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(NativeVideo).run(result)
    print(json.dumps({'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
                      'failed': len(result.failures) + len(result.errors), 'skipped': len(result.skipped),
                      'expected_release': VERSION, 'source_sha256': SOURCE_SHA,
                      'failures': [{'case': str(case), 'traceback': trace} for case, trace in [*result.failures, *result.errors]],
                      'boundary': 'Actual native configuration/provenance; not a crafted exploit test or scanner waiver.'}))
    sys.exit(0 if result.wasSuccessful() else 1)
