#!/bin/sh
# QA-only stable-source experiment. Run in a NEW bounded disposable container,
# never in an application service; do not give it app env, sockets or data volumes.
# The source archive is downloaded separately from the official signed5.5.3 tag.
set -eu
test "${QA_NATIVE_CANDIDATE:-}" = true
test -f /.dockerenv
test -f /inputs/tesseract-5.5.3.tar.gz
test -d /candidate
test ! -e /tmp/chemistry-native-candidate
test ! -e /candidate/usr/bin/tesseract
printf '%s  /inputs/tesseract-5.5.3.tar.gz\n' \
  '9218e62793116d42a9f6d14cd9348518b27f382096eea3d0f2d1a24616bb5884' | sha256sum -c -
apt-get update
apt-get install -y --no-install-recommends build-essential cmake pkg-config libleptonica-dev libtiff-dev
mkdir /tmp/chemistry-native-candidate
cd /tmp/chemistry-native-candidate
tar -xf /inputs/tesseract-5.5.3.tar.gz
cmake -S tesseract-5.5.3 -B build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr \
  -DCMAKE_INSTALL_LIBDIR="lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)" \
  -DBUILD_SHARED_LIBS=ON -DBUILD_TRAINING_TOOLS=OFF -DBUILD_TESTS=OFF \
  -DDISABLE_CURL=ON -DDISABLE_ARCHIVE=ON -DGRAPHICS_DISABLED=ON \
  -DOPENMP_BUILD=ON -DENABLE_NATIVE=OFF -DENABLE_LTO=OFF \
  -DENABLE_PRECOMPILED_HEADERS=OFF -DINSTALL_CONFIGS=OFF
cmake --build build --parallel 1
DESTDIR=/candidate cmake --install build
task_lib_dir="/candidate/usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)"
LD_LIBRARY_PATH="$task_lib_dir" \
  /candidate/usr/bin/tesseract --version
LD_LIBRARY_PATH="$task_lib_dir" ldd /candidate/usr/bin/tesseract
if LD_LIBRARY_PATH="$task_lib_dir" ldd /candidate/usr/bin/tesseract | grep -E 'libarchive|libcurl|libxml2'; then
  echo 'Optional network/archive/XML dependency retained: reject candidate' >&2
  exit 1
fi
printf '%s\n' \
  'Upstream: https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.3' \
  'Tag object: 6951ffe10ce031374bcd04fe400811da1e7e04ad' \
  'Commit: db0ec62f81b0737fbbe184d8fea40af5738f8eef' \
  'Archive-SHA256: 9218e62793116d42a9f6d14cd9348518b27f382096eea3d0f2d1a24616bb5884' \
  'Candidate only; no runtime upgrade or OCR accuracy claim.' \
  > /candidate/provenance.txt
