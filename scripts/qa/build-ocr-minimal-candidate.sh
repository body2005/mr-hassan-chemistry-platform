#!/bin/sh
# QA-only rebuild of the CURRENT Debian stable OCR source, not an upgrade.
# Official source/checksum manifest: https://deb.debian.org/debian/pool/main/t/tesseract/tesseract_5.5.0-1.dsc
# Use a new bounded container with no application secrets/socket/data volumes.
set -eu
test "${QA_NATIVE_CANDIDATE:-}" = true
test -f /.dockerenv
test -d /candidate
test ! -e /candidate/usr/bin/tesseract
test ! -e /tmp/chemistry-ocr-minimal
printf '%s  /inputs/tesseract_5.5.0.orig.tar.gz\n' \
  'f2fb34ca035b6d087a42875a35a7a5c4155fa9979c6132365b1e5a28ebc3fc11' | sha256sum -c -
printf '%s  /inputs/tesseract_5.5.0-1.debian.tar.xz\n' \
  '339c1e99003ed57552296f0ce758650b8c62d5f1222bb22c6c93a519dc90d20d' | sha256sum -c -
apt-get update
apt-get install -y --no-install-recommends build-essential autoconf automake libtool \
  autoconf-archive pkg-config libleptonica-dev libtiff-dev xz-utils
mkdir /tmp/chemistry-ocr-minimal
cd /tmp/chemistry-ocr-minimal
tar -xf /inputs/tesseract_5.5.0.orig.tar.gz
cd tesseract-5.5.0
tar -xf /inputs/tesseract_5.5.0-1.debian.tar.xz
patch -p1 < debian/patches/0001_helptext
export DEB_BUILD_MAINT_OPTIONS=hardening=+all
task_flags="$(dpkg-buildflags --get CFLAGS) -Wall -g -fPIC"
task_links="-lleptonica -Wl,-z,defs $(dpkg-buildflags --get LDFLAGS)"
./autogen.sh
./configure --host="$(dpkg-architecture -qDEB_HOST_GNU_TYPE)" \
  --build="$(dpkg-architecture -qDEB_BUILD_GNU_TYPE)" \
  --disable-tessdata-prefix --prefix=/usr \
  --libdir="/usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)" \
  --without-curl --without-archive --disable-graphics \
  CXXFLAGS="$task_flags" LDFLAGS="$task_links"
make -j1
make DESTDIR=/candidate install
task_lib_dir="/candidate/usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)"
LD_LIBRARY_PATH="$task_lib_dir" /candidate/usr/bin/tesseract --version
LD_LIBRARY_PATH="$task_lib_dir" ldd /candidate/usr/bin/tesseract
if LD_LIBRARY_PATH="$task_lib_dir" ldd /candidate/usr/bin/tesseract | grep -E 'libarchive|libcurl|libxml2'; then
  echo 'Optional network/archive/XML dependency retained: reject candidate' >&2
  exit 1
fi
printf '%s\n' \
  'Debian stable current source: tesseract5.5.0-1 (runtime binary5.5.0-1+b1)' \
  'Source: https://deb.debian.org/debian/pool/main/t/tesseract/tesseract_5.5.0-1.dsc' \
  'Upstream-SHA256: f2fb34ca035b6d087a42875a35a7a5c4155fa9979c6132365b1e5a28ebc3fc11' \
  'Debian-SHA256: 339c1e99003ed57552296f0ce758650b8c62d5f1222bb22c6c93a519dc90d20d' \
  'Hashes from official HTTPS DSC; maintainer PGP signature not independently verified.' \
  'Debian help patch applied; no answer/model/parser changes. Strict QA pending.' \
  > /candidate/provenance.txt
