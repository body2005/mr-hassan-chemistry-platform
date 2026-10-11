#!/bin/sh
# Stable upstream security release, built on the SAME stable Debian base.
# This is a transparently versioned local package, not a Debian security build.
set -eu
cd /build
task_keyhome=/build/expat-keyring
mkdir -m 700 "$task_keyhome"
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  -o expat-maintainer.asc https://github.com/hartwork.gpg
printf '%s  expat-maintainer.asc\n' '94ecb6d2dce61f22935c1352552ab3d75599c2ef4ff5e42d4ae0724c32431898' | sha256sum -c -
gpg --batch --homedir "$task_keyhome" --no-default-keyring --keyring /build/expat-release.gpg --import expat-maintainer.asc
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  -o expat.tar.xz https://github.com/libexpat/libexpat/releases/download/R_2_9_0/expat-2.9.0.tar.xz
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  -o expat.tar.xz.asc https://github.com/libexpat/libexpat/releases/download/R_2_9_0/expat-2.9.0.tar.xz.asc
printf '%s  expat.tar.xz\n' '1e6371862cc31999b368c3b89b49994f0677e1bab5f1b2b85ae3741f5d803051' | sha256sum -c -
printf '%s  expat.tar.xz.asc\n' 'd1f5832ac46a9f92492ee15ceb50bc1bb2c8d590e5932ccf931cf7e8de1adf4a' | sha256sum -c -
gpg --batch --homedir "$task_keyhome" --no-default-keyring --keyring /build/expat-release.gpg \
  --status-fd 1 --verify expat.tar.xz.asc expat.tar.xz > /build/expat-signature-status.txt
grep -q '^\[GNUPG:\] VALIDSIG CB8DE70A90CFBF6C3BF5CC5696262ACFFBD3AEC6 .*3176EF7DB2367F1FCA4F306B1F9B0E909AF37285$' /build/expat-signature-status.txt
tar -xf expat.tar.xz
cd expat-2.9.0
triplet=$(dpkg-architecture -qDEB_HOST_MULTIARCH)
./configure --prefix=/usr --libdir="/usr/lib/$triplet" \
  --without-xmlwf --without-docbook --enable-shared --disable-static
make -j2
make check
cp tests/test-suite.log /build/expat-tests.log
make DESTDIR=/build/install install
package=/build/package
mkdir -p "$package/DEBIAN" "$package/usr/lib/$triplet" "$package/usr/share/doc/libexpat1"
cp -a /build/install/usr/lib/"$triplet"/libexpat.so.1* "$package/usr/lib/$triplet/"
cp COPYING "$package/usr/share/doc/libexpat1/copyright"
printf '%s\n' \
  'Upstream: https://github.com/libexpat/libexpat/releases/tag/R_2_9_0' \
  'Source-SHA256: 1e6371862cc31999b368c3b89b49994f0677e1bab5f1b2b85ae3741f5d803051' \
  'Verified-signer: CB8DE70A90CFBF6C3BF5CC5696262ACFFBD3AEC6 / 3176EF7DB2367F1FCA4F306B1F9B0E909AF37285' \
  'Local build; not an official Debian binary. Upstream tests executed during build.' \
  > "$package/usr/share/doc/libexpat1/chemistry-source.txt"
printf '%s\n' 'Package: libexpat1' 'Source: expat' \
  'Version: 2.9.0-0chemistry1' "Architecture: $(dpkg --print-architecture)" \
  'Section: libs' 'Priority: optional' 'Maintainer: Chemistry Platform maintainers' \
  'Depends: libc6 (>= 2.41)' 'Multi-Arch: same' \
  'Description: Expat 2.9.0 stable upstream security build for Chemistry Platform' \
  > "$package/DEBIAN/control"
dpkg-deb --root-owner-group --build "$package" /build/libexpat1.deb
