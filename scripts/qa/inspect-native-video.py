"""Read-only encoder capability evidence; NOT an exploit test or CVE waiver.

Mount into the isolated current video-worker and run as its non-root user.
Prints only public binary/version/capability metadata, never app configuration.
"""
import json
import re
import subprocess


def ffmpeg(*args):
    return subprocess.run(
        ['ffmpeg', *args], check=True, capture_output=True, text=True,
        timeout=15, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
    ).stdout


def names(option):
    result = set()
    for line in ffmpeg('-v', 'quiet', option).splitlines():
        fields = line.split()
        if len(fields) >= 2 and re.fullmatch(r'[A-Z.|]+', fields[0]) and re.fullmatch(r'[a-z0-9_,]+', fields[1]):
            result.update(fields[1].split(','))
    return result


def main():
    decoders, filters = names('-decoders'), names('-filters')
    muxers, demuxers = names('-muxers'), names('-demuxers')
    protocols = sorted({word for word in ffmpeg('-v', 'quiet', '-protocols').split()
                        if re.fullmatch(r'[a-z0-9_]+', word)})
    print(json.dumps({
        'version': ffmpeg('-version').splitlines()[0],
        'decoders_present': {name: name in decoders for name in ('rasc', 'cfhd', 'magicyuv', 'adpcm_adx', 'mace6')},
        'filters_present': {name: name in filters for name in ('hqdn3d', 'quirc', 'scale', 'setsar')},
        'muxers_present': {name: name in muxers for name in ('mpeg', 'rtp', 'spdif', 'hls')},
        'demuxers_present': {name: name in demuxers for name in ('dash', 'webm_dash_manifest', 'mov', 'matroska', 'caf', 'wtv')},
        'protocols': protocols,
        'boundary': 'Capability inventory only. Presence is not proof of app reachability; absence is not a general vulnerability waiver.',
    }, sort_keys=True))


if __name__ == '__main__':
    main()
