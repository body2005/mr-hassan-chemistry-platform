#!/bin/sh
# Matching, signed CPython modules linked to the reviewed stable Expat build.
# Rebuild BOTH: _elementtree checks the Expat version in pyexpat's C capsule.
# This is a documented custom build, not a claim the official image changed.
set -eu
cd /build
python -c 'import sys; assert sys.version_info[:3] == (3, 12, 15)'
task_keyhome=/build/python-keyring
mkdir -m 700 "$task_keyhome"
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  -o python-maintainer.asc https://github.com/Yhg1s.gpg
printf '%s  python-maintainer.asc\n' '33c3af79f23a83c2a8a569bfd546601be400cb26dd7eb31f6d5e5b621667c391' | sha256sum -c -
gpg --batch --homedir "$task_keyhome" --no-default-keyring --keyring /build/python-release.gpg --import python-maintainer.asc
for task_file in Python-3.12.15.tar.xz Python-3.12.15.tar.xz.asc; do
  curl --fail --location --proto '=https' --tlsv1.2 --retry 3 -o "$task_file" "https://www.python.org/ftp/python/3.12.15/$task_file"
done
printf '%s  Python-3.12.15.tar.xz\n' 'c2c4321961fab0fb999d66e0cecf521c2ab3994c7992873ea99e306c1094fd5a' | sha256sum -c -
gpg --batch --homedir "$task_keyhome" --no-default-keyring --keyring /build/python-release.gpg \
  --status-fd 1 --verify Python-3.12.15.tar.xz.asc Python-3.12.15.tar.xz > /build/python-xml-signature-status.txt
grep -q '^\[GNUPG:\] VALIDSIG .*7169605F62C751356D054A26A821E680E5FA6305' /build/python-xml-signature-status.txt
tar -xf Python-3.12.15.tar.xz
task_triplet=$(dpkg-architecture -qDEB_HOST_MULTIARCH)
task_lib="/build/install/usr/lib/$task_triplet"
task_suffix=$(python -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
task_include=$(python -c 'import sysconfig; print(sysconfig.get_path("include"))')
task_dest=$(python -c 'import sysconfig; print(sysconfig.get_config_var("DESTSHARED"))')
mkdir /build/python-xml-modules
for task_module in pyexpat _elementtree; do
  cc -shared -fPIC $(python3-config --cflags) -I"$task_include/internal" \
    -I/build/expat-2.9.0 -I/build/install/usr/include \
    "/build/Python-3.12.15/Modules/$task_module.c" \
    -L"$task_lib" -Wl,-z,relro,-z,now -lexpat \
    -o "/build/python-xml-modules/$task_module$task_suffix"
  install -m 755 "/build/python-xml-modules/$task_module$task_suffix" "$task_dest/$task_module$task_suffix"
done
LD_LIBRARY_PATH="$task_lib" ldd "$task_dest/pyexpat$task_suffix" > /build/python-xml-links.txt
grep -F "libexpat.so.1 => $task_lib/" /build/python-xml-links.txt
LD_LIBRARY_PATH="$task_lib" PYTHONPATH=/build/Python-3.12.15/Lib python /build/run_python_xml_tests.py
cp /build/Python-3.12.15/LICENSE /build/python-xml-license.txt
printf '%s\n' \
  'CPython: official signed3.12.15 source; matching pyexpat/_elementtree, unmodified binding sources.' \
  'Source-SHA256: c2c4321961fab0fb999d66e0cecf521c2ab3994c7992873ea99e306c1094fd5a' \
  'Verified-primary-signer: 7169605F62C751356D054A26A821E680E5FA6305 (Python.org linked key)' \
  'Linked-Expat: stable2.9.0, built on the same pinned stable Debian base.' \
  'Custom compiled modules, not an official Python Docker binary; upstream XML tests executed.' \
  > /build/python-xml-source.txt
