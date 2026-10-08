#!/bin/sh
# Same stable Debian base; signed upstream FFmpeg 9.0.2 stable release, no
# network/device/SVG/JSON-Patch integration. Retain native media codecs/HLS.
set -eu
cd /build
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  -o ffmpeg.tar.xz https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz
printf '%s  ffmpeg.tar.xz\n' '8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e' | sha256sum -c -
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  -o ffmpeg.tar.xz.asc https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz.asc
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  -o release-key.asc https://ffmpeg.org/ffmpeg-devel.asc
export GNUPGHOME=/build/keyring
mkdir -m 700 "$GNUPGHOME"
gpg --batch --import release-key.asc
gpg --batch --status-fd 1 --verify ffmpeg.tar.xz.asc ffmpeg.tar.xz > signature-status.txt
grep -q '^\[GNUPG:\] VALIDSIG FCF986EA15E6E293A5644F10B4322F04D67658D8 ' signature-status.txt
tar -xf ffmpeg.tar.xz
cd ffmpeg-9.0.2
./configure --prefix=/usr --disable-autodetect --disable-network --disable-devices --enable-indev=lavfi \
  --disable-doc --disable-debug --disable-ffplay --disable-shared --enable-static \
  --disable-decoder=rasc --enable-gpl --enable-libx264
make -j2
# CVE-2026-58049 has no verified fix-content proof for RASC here. Remove that
# unused legacy decoder, not the scanner record. Normal MP4/MOV/WebM codecs
# stay enabled; a RASC-encoded file must fail validation, never be decoded.
./ffmpeg -v quiet -decoders > /build/runtime-decoders.txt
if grep -E '(^|[[:space:]])rasc([[:space:]]|$)' /build/runtime-decoders.txt; then
  echo 'RASC decoder unexpectedly enabled' >&2
  exit 1
fi
# Exercise real encoding, decoding and the exact production filters/muxer.
./ffmpeg -v error -f lavfi -i testsrc2=size=320x240:rate=30 -f lavfi -i sine=frequency=440 \
  -t 2 -vf scale=-2:240,setsar=1 -c:v libx264 -threads 2 -pix_fmt yuv420p \
  -c:a aac -ac 2 -f hls -hls_playlist_type vod /build/smoke.m3u8
./ffmpeg -v error -i /build/smoke.m3u8 -f null -
./ffprobe -v error -show_entries stream=codec_name -of json /build/smoke.m3u8
package=/build/package
mkdir -p "$package/DEBIAN" "$package/usr/bin" "$package/usr/share/doc/ffmpeg"
install -m 755 ffmpeg ffprobe "$package/usr/bin/"
cp COPYING.GPLv2 "$package/usr/share/doc/ffmpeg/copyright"
printf '%s\n' \
  'Upstream: https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz' \
  'Source-SHA256: 8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e' \
  'Signer: FCF986EA15E6E293A5644F10B4322F04D67658D8' \
  'GPLv2 build. Full corresponding source is the pinned upstream archive;' \
  'configuration/build instructions are scripts/build_native_ffmpeg.sh.' \
  'Local package, not an official Debian binary.' \
  > "$package/usr/share/doc/ffmpeg/chemistry-source.txt"
printf '%s\n' 'Package: ffmpeg' 'Source: ffmpeg' \
  'Version: 7:9.0.2-0chemistry1' "Architecture: $(dpkg --print-architecture)" \
  'Section: video' 'Priority: optional' 'Maintainer: Chemistry Platform maintainers' \
  'Depends: libc6 (>= 2.41), libx264-164' \
  'Description: Restricted stable FFmpeg build for Chemistry Platform encoder' \
  > "$package/DEBIAN/control"
dpkg-deb --root-owner-group --build "$package" /build/ffmpeg.deb
