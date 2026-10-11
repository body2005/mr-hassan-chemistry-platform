# Security recheck of the role-fix images — 4 October 2026

NOT a deployment approval. All findings remain visible at their scanner
severity; no ignore list, severity downgrade or unstable distribution switch.

Docker Scout 1.24.0, run `scripts/qa/run-video.ps1 -Stage Scan -ApproveScout`,
UTC stamp `20261004-174630` (Cairo 20:46). Both scans completed and wrote SARIF;
the critical/high gate returned nonzero. API: 6 HIGH, 0 CRITICAL; video-worker:
10 HIGH, 0 CRITICAL. These overlap, not 16 distinct CVEs. SARIF files are in
ignored `.qa/audit2/scout-video-{api,video-worker}-20261004-174630.sarif`.
Scout also reported inability to remove its temporary image archive (Windows
file in use); this was not substituted for the vulnerability results.

Tested API manifest ID:
`sha256:7c65ed17bbf7aa4e60ff18b2f4a4e132c3696c1169b53ffbe065253e57145d28`.
Video-worker manifest ID:
`sha256:1403b7313b088328407af223d50fa577142efa84081453dbb956b2ce20d076e8`.

The preceding `20261004-165211` scan on API `3171b8b9…` / worker
`e5618e76…` also returned 6/10 HIGH. The latest scan above is on the rebuilt
storage-diagnostic/profile-read classification version, not borrowed evidence
from those earlier images. The intermediate `20261004-171521` scan also
returned 6/10 HIGH on API `cbf68b53…` / worker `079adf85…`.

## Actual security sources and versions

A throwaway container of the SAME API image ran `apt-get update`, then
`apt-cache policy openssl libssl3t64 libxml2 libexpat1 libstdc++6 zlib1g` and
read `/etc/apt/sources.list.d/debian.sources`. Exit 0, no change to the running
application or saved image. Enabled official signed suites: `trixie`,
`trixie-updates`, `trixie-security`; the security endpoint is
`http://deb.debian.org/debian-security`, Debian archive-keyring validation.

OpenSSL/libssl are both `3.5.7-1~deb13u3`, the same installed and candidate
security version. The Dockerfile enforces that minimum. The old OpenSSL
finding did NOT appear in either new critical/high scan. Python's bundled
`pyexpat.EXPAT_VERSION` is `expat_2.8.5`; OS `libexpat1` is separately affected,
so the fixed Python component does not close the OS alert.

`ldd /usr/bin/ffmpeg` in the actual video-worker returned bindings to
`libstdc++`, `libxml2`, `librsvg`, `libexpat`, `libcjson`. Library linkage proves
presence, NOT exploitation or absence of reachability. Python
`importlib.util.find_spec('libxml2')` returned `None` (the specific SAX Python
binding is absent). Source review below is qualified, not a reachability proof.

## Per-finding ledger

Official Debian tracker pages below were re-opened on 4 October. "No stable
fix" means no corrected trixie/trixie-security candidate, not no upstream work.
Every row remains OPEN at HIGH.

| CVE / image | Installed source package | Stable fix now | Application path and possible mitigation |
|---|---|---|---|
| [2026-102010](https://security-tracker.debian.org/tracker/CVE-2026-102010), both | gcc-14 `14.2.0-19` | No, tracker unfixed | PBDS binary-heap `erase_if` use-after-free. Python application does not directly invoke that C++ template; native parsers use libstdc++. Specific compiled call path not proven absent. Bounded inputs and isolated OCR/encoder reduce impact, not a library repair. |
| [2026-95619](https://security-tracker.debian.org/tracker/CVE-2026-95619), both | gcc-14 `14.2.0-19` | No, tracker unfixed | Aligned allocation overflow; native document/media operations are exposed to uploaded bytes. Resource caps do not establish that this allocator path is unreachable. Keep native processing bounded, track stable backport. |
| [2026-86140](https://security-tracker.debian.org/tracker/CVE-2026-86140), both | libxml2 `2.12.7+dfsg+really2.9.14-2.1+deb13u3` | No; upstream/unstable corrected | `xmlSnprintfElements` overflow. Application does not call DTD validation explicitly, but native XML dependencies remain. Do not accept arbitrary XML/SVG through the video endpoint; retain document budgets. No blanket unreachable claim. |
| [2026-74860](https://security-tracker.debian.org/tracker/CVE-2026-74860), both | same libxml2 | No stable candidate | Double free in libxml2's Python SAX `attributeDecl` callback. That Python binding is not installed; lxml is not this binding. This narrows the described route, without claiming the OS library is fixed or suppressing the finding. |
| [2026-93990](https://security-tracker.debian.org/tracker/CVE-2026-93990), both | expat `2.8.3-1~deb13u1` | No stable candidate | Malformed UTF-16 surrogate processing. CPython bundled Expat is corrected at 2.8.5, but native OS consumers remain. Scanner OS alert is real and retained. |
| [2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091), both | zlib source `1:1.3.dfsg+really1.3.1-1`, binary `-1+b1` | No; tracker marks vulnerable | Nonblocking gzip write buffer issue. Python compression/decompression exists but no direct application `gzprintf`/`gzvprintf` call was found. Upstream affected-range discussion differs from Debian's status; do not resolve that discrepancy by hiding the alert. This finding reappeared since the earlier scan. |
| [2026-96889](https://security-tracker.debian.org/tracker/CVE-2026-96889), worker | librsvg `2.60.0+dfsg-1` | No stable candidate; upstream fixes exist | SVG nested XML inclusions/entity use-after-free. Worker only accepts mov/matroska/WebM, uses file-only input protocols and fixed commands; SVG standalone is not accepted. FFmpeg still links librsvg; all indirect codec paths are not proven unreachable. |
| [2026-67216](https://security-tracker.debian.org/tracker/CVE-2026-67216), worker | cjson `1.7.18-3.1+deb13u1` | No, tracker unfixed | Exponential `cJSON_Compare` recursion. API and ffprobe-output JSON are handled by Python; no direct cJSON comparison. Native dependency remains; process CPU/time budget is mitigation, not a fix. |
| [2026-29036](https://security-tracker.debian.org/tracker/CVE-2026-29036), worker | same cjson | No, tracker unfixed | JSON Pointer/Patch key resolution. No application endpoint feeds cJSONUtils JSON Patch. Do not introduce untrusted native patch/filter config. Alert remains in the image. |
| [2026-67215](https://security-tracker.debian.org/tracker/CVE-2026-67215), worker | same cjson | No, tracker unfixed | Native JSON Patch recursion exhaustion. Encoder args and filters are server-owned, subprocess has no shell and restricted protocols/resources. Indirect native paths not exhaustively audited. |

OCR runs under a 20-second total recognition budget, one distributed slot,
pre-allocation page/image/archive limits, Tesseract CPU/address-space/file limits.
Video-worker is non-root, read-only, drops capabilities, has no-new-privileges,
2 CPU/2560 MiB/128 PID limits and bounded FFmpeg processing. These safeguards
do NOT cure native vulnerabilities or provide a complete kernel sandbox.

Re-scan after a stable security candidate or an independently reviewable native
backport. Review/signoff is still required; the developer must not self-waive
these risks or advertise zero vulnerabilities.
