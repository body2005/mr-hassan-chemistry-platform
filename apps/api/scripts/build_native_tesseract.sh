#!/bin/sh
# Rebuild the current Debian STABLE OCR source without optional URL/archive/
# training/debug integrations, plus six SHA-pinned upstream security backports.
# Preserve source5.5.0/models, honest custom-package revision and provenance.
set -eu
cd /build
for task_file in tesseract_5.5.0-1.dsc tesseract_5.5.0.orig.tar.gz tesseract_5.5.0-1.debian.tar.xz; do
  curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
    -o "$task_file" "https://deb.debian.org/debian/pool/main/t/tesseract/$task_file"
done
printf '%s  tesseract_5.5.0-1.dsc\n' \
  '80dc6a0e5d6189b3fe9df632a114642b17ed8582a43b55e45ca508efb995cf1c' | sha256sum -c -
printf '%s  tesseract_5.5.0.orig.tar.gz\n' \
  'f2fb34ca035b6d087a42875a35a7a5c4155fa9979c6132365b1e5a28ebc3fc11' | sha256sum -c -
printf '%s  tesseract_5.5.0-1.debian.tar.xz\n' \
  '339c1e99003ed57552296f0ce758650b8c62d5f1222bb22c6c93a519dc90d20d' | sha256sum -c -
# Verify against Debian's signed-package maintainer keyring, not a key fetched
# from the source archive. Fail closed if the signer cannot be verified.
gpgv --status-fd 1 --keyring /usr/share/keyrings/debian-keyring.gpg \
  tesseract_5.5.0-1.dsc > tesseract-signature-status.txt
grep -q '^\[GNUPG:\] VALIDSIG 406220C8B8552802378CCE411F5C7A8B45564314 ' tesseract-signature-status.txt
tar -xf tesseract_5.5.0.orig.tar.gz
cd tesseract-5.5.0
tar -xf ../tesseract_5.5.0-1.debian.tar.xz
patch --fuzz=0 -p1 < debian/patches/0001_helptext
task_assets=/build/native-tesseract
task_evidence=/build/tesseract-security-evidence
task_patches=/build/tesseract-security-patches
mkdir -p "$task_patches"
while read -r task_cve task_commit task_sha; do
  case "$task_cve" in ''|'#'*) continue ;; esac
  curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
    -o "$task_patches/$task_commit.patch" \
    "https://github.com/tesseract-ocr/tesseract/commit/$task_commit.patch"
  printf '%s  %s\n' "$task_sha" "$task_patches/$task_commit.patch" | sha256sum -c -
done < "$task_assets/backports.tsv"
sh "$task_assets/apply-backports.sh" /build/tesseract-5.5.0 "$task_patches" "$task_evidence"
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
make DESTDIR=/build/tesseract-install install
# Build-time-only GoogleTest/compiler/static objects. The image cannot proceed
# with a security regression; the actual26-case XML is retained as evidence.
sh "$task_assets/run-security-tests.sh" /build/tesseract-5.5.0 "$task_evidence"
task_lib="/build/tesseract-install/usr/lib/$task_triplet"
LD_LIBRARY_PATH="$task_lib" /build/tesseract-install/usr/bin/tesseract --version
LD_LIBRARY_PATH="$task_lib" ldd /build/tesseract-install/usr/bin/tesseract > /build/tesseract-library-links.txt
if grep -E 'not found|libarchive|libcurl|libxml2|libpango|libcairo|libicu' /build/tesseract-library-links.txt; then
  echo 'Unused optional dependency retained' >&2
  exit 1
fi
task_version=5.5.0-1+chemistry2
task_library_package=/build/tesseract-library-package
task_cli_package=/build/tesseract-cli-package
mkdir -p "$task_library_package/DEBIAN" "$task_library_package/usr/lib/$task_triplet" \
  "$task_library_package/usr/share/doc/libtesseract5" \
  "$task_cli_package/DEBIAN" "$task_cli_package/usr/bin" \
  "$task_cli_package/usr/share/tesseract-ocr/5/tessdata" "$task_cli_package/usr/share/doc/tesseract-ocr"
cp -a "$task_lib"/libtesseract.so.5* "$task_library_package/usr/lib/$task_triplet/"
install -m 755 /build/tesseract-install/usr/bin/tesseract "$task_cli_package/usr/bin/tesseract"
# Debug/static objects and training tools stay in the build stage, not runtime.
find "$task_library_package/usr/lib/$task_triplet" -type f -name 'libtesseract.so.*' -exec strip --strip-unneeded {} \;
strip --strip-unneeded "$task_cli_package/usr/bin/tesseract"
cp -a /build/tesseract-install/usr/share/tessdata/. "$task_cli_package/usr/share/tesseract-ocr/5/tessdata/"
for task_package in "$task_library_package/usr/share/doc/libtesseract5" "$task_cli_package/usr/share/doc/tesseract-ocr"; do
  cp LICENSE "$task_package/copyright"
  printf '%s\n' \
    'Source: Debian stable tesseract5.5.0-1, not an official Debian binary.' \
    'Upstream-SHA256: f2fb34ca035b6d087a42875a35a7a5c4155fa9979c6132365b1e5a28ebc3fc11' \
    'Debian-SHA256: 339c1e99003ed57552296f0ce758650b8c62d5f1222bb22c6c93a519dc90d20d' \
    'DSC-Signer: 406220C8B8552802378CCE411F5C7A8B45564314 (Debian keyring)' \
    'Build: scripts/build_native_tesseract.sh; optional curl/archive/graphics disabled.' \
    'Backports: six official upstream SHA-pinned patches; reviewed5.5.0 context ports.' \
    'Patch manifest: applied-patches.tsv; official HTTPS/checksum, not independently PGP-signed.' \
    'Native tests:15 unchanged upstream bodies plus11 overflow/valid controls, build-time26/0/0 required.' \
    'Recognition/model/source-fidelity and runtime security gates remain independent.' \
    > "$task_package/chemistry-source.txt"
  cp "$task_evidence/applied-patches.tsv" "$task_package/applied-patches.tsv"
done
printf '%s\n' 'Package: libtesseract5' 'Source: tesseract (5.5.0-1)' \
  "Version: $task_version" "Architecture: $(dpkg --print-architecture)" \
  'Section: libs' 'Priority: optional' 'Maintainer: Chemistry Platform maintainers' \
  'Depends: libc6 (>= 2.41), libgcc-s1, libgomp1, libleptonica6 (>= 1.84.1), libstdc++6 (>= 14.2.0-19)' \
  'Multi-Arch: same' \
  'Description: Current stable Tesseract library without optional URL/archive integration' \
  > "$task_library_package/DEBIAN/control"
printf '%s\n' 'Package: tesseract-ocr' 'Source: tesseract (5.5.0-1)' \
  "Version: $task_version" "Architecture: $(dpkg --print-architecture)" \
  'Section: graphics' 'Priority: optional' 'Maintainer: Chemistry Platform maintainers' \
  "Depends: libtesseract5 (= $task_version), libc6 (>= 2.41), libgcc-s1, libleptonica6 (>= 1.84.1), libstdc++6 (>= 14.2.0-19), tesseract-ocr-eng, tesseract-ocr-osd" \
  'Description: Current stable OCR executable without unused training/network integration' \
  > "$task_cli_package/DEBIAN/control"
dpkg-deb --root-owner-group --build "$task_library_package" /build/libtesseract5.deb
dpkg-deb --root-owner-group --build "$task_cli_package" /build/tesseract-ocr.deb
