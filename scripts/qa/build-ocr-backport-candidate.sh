#!/bin/sh
# QA ONLY: signed stable 5.5.0 source plus exact upstream security changes.
# Never installs into an application image or changes models/parser/references.
# /inputs and /qa-tools are read-only; /candidate is a new empty private output.
set -eu
test "${QA_NATIVE_CANDIDATE:-}" = true
test -f /.dockerenv
test -d /candidate
test ! -e /candidate/usr/bin/tesseract
test ! -e /candidate/applied-patches.tsv
test -f /native-backports/backports.tsv

apt-get update
apt-get install -y --no-install-recommends build-essential autoconf automake \
  autoconf-archive libtool pkg-config libleptonica-dev libtiff-dev xz-utils \
  git gpgv debian-keyring libgtest-dev libgmock-dev
printf '%s  /inputs/tesseract_5.5.0-1.dsc\n' \
  '80dc6a0e5d6189b3fe9df632a114642b17ed8582a43b55e45ca508efb995cf1c' | sha256sum -c -
printf '%s  /inputs/tesseract_5.5.0.orig.tar.gz\n' \
  'f2fb34ca035b6d087a42875a35a7a5c4155fa9979c6132365b1e5a28ebc3fc11' | sha256sum -c -
printf '%s  /inputs/tesseract_5.5.0-1.debian.tar.xz\n' \
  '339c1e99003ed57552296f0ce758650b8c62d5f1222bb22c6c93a519dc90d20d' | sha256sum -c -
gpgv --status-fd 1 --keyring /usr/share/keyrings/debian-keyring.gpg \
  /inputs/tesseract_5.5.0-1.dsc > /candidate/signature.txt
grep -q '^\[GNUPG:\] VALIDSIG 406220C8B8552802378CCE411F5C7A8B45564314 ' /candidate/signature.txt
task_work_dir="$(mktemp -d /tmp/chemistry-ocr-backport.XXXXXXXX)"
cd "$task_work_dir"
tar -xf /inputs/tesseract_5.5.0.orig.tar.gz
cd tesseract-5.5.0
tar -xf /inputs/tesseract_5.5.0-1.debian.tar.xz
patch --fuzz=0 -p1 < debian/patches/0001_helptext
sh /native-backports/apply-backports.sh "$task_work_dir/tesseract-5.5.0" /patches /candidate

git diff --no-index /dev/null /candidate/applied-patches.tsv > /candidate/patch-inventory.diff || test "$?" -eq 1
# Allows a lightweight signature/applicability check while live browser tests
# run. It is not a binary/regression/fidelity success, and produces no runtime.
if test "${QA_BACKPORT_PREPARE_ONLY:-false}" = true; then
  printf '%s\n' 'PREPARED ONLY: six exact upstream patches; no binary built or adopted.'
  exit 0
fi

export DEB_BUILD_MAINT_OPTIONS=hardening=+all
task_flags="$(dpkg-buildflags --get CFLAGS) -Wall -g -fPIC"
task_links="-lleptonica -Wl,-z,defs $(dpkg-buildflags --get LDFLAGS)"
task_triplet="$(dpkg-architecture -qDEB_HOST_MULTIARCH)"
./autogen.sh
./configure --host="$(dpkg-architecture -qDEB_HOST_GNU_TYPE)" \
  --build="$(dpkg-architecture -qDEB_BUILD_GNU_TYPE)" \
  --disable-tessdata-prefix --prefix=/usr --libdir="/usr/lib/$task_triplet" \
  --without-curl --without-archive --disable-graphics \
  CXXFLAGS="$task_flags" LDFLAGS="$task_links"
make -j1
make DESTDIR=/candidate install
task_lib="/candidate/usr/lib/$task_triplet"
LD_LIBRARY_PATH="$task_lib" /candidate/usr/bin/tesseract --version
LD_LIBRARY_PATH="$task_lib" ldd /candidate/usr/bin/tesseract > /candidate/library-links.txt
if grep -E 'not found|libarchive|libcurl|libxml2|libpango|libcairo|libicu' /candidate/library-links.txt; then
  echo 'Missing or unused optional native dependency: reject candidate' >&2
  exit 1
fi

# Original upstream security tests exercise the candidate's actual static
# library, not a Python mock or a standalone reimplementation of its checks.
# The additional overflow cases cover the upstream change without test bodies.
sh /qa-tools/test-ocr-backports.sh "$task_work_dir/tesseract-5.5.0"
