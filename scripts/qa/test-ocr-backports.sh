#!/bin/sh
# Compile the unchanged upstream test bodies against the REAL candidate.
set -eu
test "${QA_NATIVE_CANDIDATE:-}" = true
test -f /.dockerenv
task_source="${1:?compiled candidate source required}"
case "$task_source" in /tmp/chemistry-ocr-backport.*/tesseract-5.5.0) ;; *) exit 1 ;; esac
cd "$task_source"
test -f .libs/libtesseract.a
test -f /candidate/usr/bin/tesseract
test ! -e /candidate/security-tests.xml
sh /native-backports/run-security-tests.sh "$task_source" /candidate

task_triplet="$(dpkg-architecture -qDEB_HOST_MULTIARCH)"
sha256sum /candidate/usr/bin/tesseract /candidate/usr/lib/"$task_triplet"/libtesseract.so.5.* \
  > /candidate/binary-sha256.txt
printf '%s\n' \
  'QA candidate: signed Debian stable tesseract5.5.0-1 plus six upstream security backports.' \
  'DSC-Signer: 406220C8B8552802378CCE411F5C7A8B45564314 (Debian keyring)' \
  'Source-SHA256: f2fb34ca035b6d087a42875a35a7a5c4155fa9979c6132365b1e5a28ebc3fc11' \
  'Patch origin: official GitHub HTTPS commit.patch; pinned SHA256; NOT independently PGP-signed.' \
  'No model/parser/reference changes. Original strict fidelity comparison still REQUIRED.' \
  'No application package/image adopted; raw scans and final image tests still REQUIRED.' \
  > /candidate/provenance.txt
