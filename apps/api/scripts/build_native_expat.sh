#!/bin/sh
# Stable upstream security release, built on the SAME stable Debian base.
# This is a transparently versioned local package, not a Debian security build.
set -eu
cd /build
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  -o expat.tar.xz https://github.com/libexpat/libexpat/releases/download/R_2_8_5/expat-2.8.5.tar.xz
printf '%s  expat.tar.xz\n' '1e727b8933ec51a77a9a9d9afcf8e688bce45d907c13e36ab7393fe36e703182' | sha256sum -c -
tar -xf expat.tar.xz
cd expat-2.8.5
triplet=$(dpkg-architecture -qDEB_HOST_MULTIARCH)
./configure --prefix=/usr --libdir="/usr/lib/$triplet" \
  --without-xmlwf --without-docbook --enable-shared --disable-static
make -j2
make check
make DESTDIR=/build/install install
package=/build/package
mkdir -p "$package/DEBIAN" "$package/usr/lib/$triplet" "$package/usr/share/doc/libexpat1"
cp -a /build/install/usr/lib/"$triplet"/libexpat.so.1* "$package/usr/lib/$triplet/"
cp COPYING "$package/usr/share/doc/libexpat1/copyright"
printf '%s\n' \
  'Upstream: https://github.com/libexpat/libexpat/releases/tag/R_2_8_5' \
  'Source-SHA256: 1e727b8933ec51a77a9a9d9afcf8e688bce45d907c13e36ab7393fe36e703182' \
  'Local build; not an official Debian binary. Upstream tests executed during build.' \
  > "$package/usr/share/doc/libexpat1/chemistry-source.txt"
printf '%s\n' 'Package: libexpat1' 'Source: expat' \
  'Version: 2.8.5-0chemistry1' "Architecture: $(dpkg --print-architecture)" \
  'Section: libs' 'Priority: optional' 'Maintainer: Chemistry Platform maintainers' \
  'Depends: libc6 (>= 2.41)' 'Multi-Arch: same' \
  'Description: Expat 2.8.5 stable upstream security build for Chemistry Platform' \
  > "$package/DEBIAN/control"
dpkg-deb --root-owner-group --build "$package" /build/libexpat1.deb
