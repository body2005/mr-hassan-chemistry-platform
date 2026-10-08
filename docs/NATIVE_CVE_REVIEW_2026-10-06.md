# Native vulnerability review — 6 October 2026

Release gate **OPEN**, not a waiver. No ignores, severity overrides, unstable
distribution, fabricated Debian revision, or claim of complete unreachability.
This report is a source review plus local binary/configuration evidence, not an
exploit test for every CVE. Future stable backports must be rebuilt and retested.

## Latest immutable-image Trivy review — 8 October, 10:21 UTC

Fresh pinned Trivy0.69.3 downloaded its current DB and scanned ACTUAL API
`d8c8c6ff…` and encoder`9f228147…`, not tags. Evidence
`trivy-20261008-102034/{api,video-worker}.sarif` and immutable-ID commands.
API **62High/0Critical package findings,20 unique CVEs**; encoder
**78High/0Critical,36 unique CVEs**. Each rawExit1, wrapperExit1.
Both use genuine Expat2.9.0-0chemistry1/Tesseract5.5.0-1+chemistry2; encoder
uses signed restricted FFmpeg7:9.0.2-0chemistry1. No alerts suppressed.
Scout's additional77214/zlib85091 and shared93990 remain in the three-row
Scout table below; the combined CURRENT union is38 unique IDs, not the older
41-ID historical union. Absence of an older ID from this DB is not proof it
was repaired or that all its consumers are safe.

Primary Debian/CNA pages were rechecked8October10:24–10:30UTC. Below, "stable
unfixed" means the reviewed trixie package has NO official fixed candidate,
not that an upstream source patch is impossible. Backported/custom binary
fix evidence is separate from distribution-based scanner matching and still
needs independent release review; no source-package renaming/fake Debian
revision/ignore/VEX/severity override is used to force a passing scan.

Actual read-only runtime checksExit0 EACH: UID10001, privileged=false,
cap_dropALL, NoNewPrivs1, effective capabilitiesZERO. `systemd-homed`,
`tiffcrop`, `setfacl`, `getfacl` and `/usr/share/perl*/Archive/Tar.pm` absent;
`infocmp`, `nsenter`, `mount` and Perl executable present. This is precise
presence/configuration evidence, NOT an exploit test or general RCE exclusion.

### Twenty shared API/encoder CVEs

| Current raw CVE | Installed package / fix status / actual-path assessment |
|---|---|
| [2025-69720](https://security-tracker.debian.org/tracker/CVE-2025-69720) | ncurses6.5+20250216-2; upstream6.5-20251213 repairs infocmp; stable unfixed. Actual infocmp exists but no app infocmp workflow/attacker-supplied terminal analysis. Keep raw warning; bounded non-root execution is mitigation, not a fixed binary. |
| [2026-16742](https://security-tracker.debian.org/tracker/CVE-2026-16742) | systemd257.13-1~deb13u1 shared libraries; upstream258.10/261.2 patches; stable unfixed. Described homed-managed privileged account path: actual systemd-homed absent; application containers do not manage OS user groups. Narrow path exclusion, not all systemd library flaws excluded. |
| [2026-36849](https://security-tracker.debian.org/tracker/CVE-2026-36849) | libtiff4.7.0-3+deb13u3; upstream4.7.1 fix / stable unfixed. Tesseract links libtiff through Leptonica. Main OCR passes pixel/area-bounded normalized PIL images; untrusted image/PDF handling exists. Native path not globally excluded; size/pixel/time/concurrency/cgroup bounds limit DoS, do not patch libtiff. |
| [2026-52490](https://security-tracker.debian.org/tracker/CVE-2026-52490) | same libtiff; upstream4.7.2 fix / stable unfixed. Specific tiffcrop process_command_opts tool absent and not invoked by app. Shared decoder library still present/reachable; do not conflate this tool-specific issue with36849. |
| [2026-54369](https://security-tracker.debian.org/tracker/CVE-2026-54369) | libacl2.3.2-2+b1; upstream2.4.0 new ABI, stable unfixed; Debian explicitly advises against isolated patch backport. App has no privileged pathname ACL workflow; CLI tools absent and all capabilities dropped. Raw alert remains; no unsafe ABI swap. |
| [2026-66046](https://security-tracker.debian.org/tracker/CVE-2026-66046) | Expat2.9.0; official2.8.4 storeAtts complexity fixes plus required follow-up are contained in signed stable2.9.0. Native/Python XML consumers exist. Source/five upstream XML groups evidence, not a dedicated complexity exploit benchmark; raw Debian range warning remains. |
| [2026-76956](https://security-tracker.debian.org/tracker/CVE-2026-76956) | same Expat; getentropy return fix40daa999… in2.8.4, retained2.9.0. Actual native+CPython dynamic linkage verified; XML potentially attacker-derived. Not claimed unreachable or dedicated entropy attack tested. |
| [2026-76957](https://security-tracker.debian.org/tracker/CVE-2026-76957) | same Expat; encoding-handler depth fixes127b7d4b…/acbd2e11… in2.8.4, retained2.9.0. Source-fixed dependency with functioning C/Python bindings; not every custom callback UAF exploit tested. Raw review still open. |
| [2026-93990](https://security-tracker.debian.org/tracker/CVE-2026-93990) | same Expat; malformedUTF16 fix belongs to upstream2.8.5, retained2.9.0. Actual expanded native/pyexpat/C-elementtree20/0/0 EACH includes malformed+validLE/BE; native/Python source and linkage verified. Debian range still flags raw. |
| [2026-73066](https://security-tracker.debian.org/tracker/CVE-2026-73066) | Tesseract5.5.0-1+chemistry2; fixed official2f4d2f4b… backport, no fixed trixie package. Convolve deserializer tests included in mandatory compiled26/0/0. Root-owned SHA-pinned trusted traineddata only; uploaded models not accepted. Raw alert retained. |
| [2026-88047](https://security-tracker.debian.org/tracker/CVE-2026-88047) | same Tesseract; ReadNormProtos fix1bda5079… backported/tested26-case scope, no fixed official stable release. Default OCR/trusted model path unchanged. Custom-build independent review needed, not only language/model-based mitigation. |
| [2026-88048](https://security-tracker.debian.org/tracker/CVE-2026-88048) | same Tesseract; FullyConnected dimension fix103dc134… backported and compiled regression tested. Fixed root-owned models and input/time bounds retained. No official stable fixed package; raw range remains. |
| [2026-88051](https://security-tracker.debian.org/tracker/CVE-2026-88051) | same Tesseract; GenericVector reserved/used guard56e09ca1… backported/tested; source/context ports reviewed. Trusted models only, no arbitrary model loader. Raw package alert remains even with actual patched library proof. |
| [2026-88052](https://security-tracker.debian.org/tracker/CVE-2026-88052) | same Tesseract; UNICHARSET index fix2d04d640… backported/tested. Actual library/model hashes fixed and dependency-only7-output comparison identical; this is not a Biology accuracy repair or whole-library ASAN claim. |
| [2026-88053](https://security-tracker.debian.org/tracker/CVE-2026-88053) | same Tesseract; IntTemplates count fix8b057468… reviewed5.5.0-context backport, runtime security guards retained. Mandatory native26-case compiled-library gate passes. Stable official package remains unfixed / custom-source review open. |
| [2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642) | util-linux2.41.5-0+deb13u1 across9 binary packages; upstream2.42.3 fix, stable unfixed. Mount post-hooks exist in tools but no application mount workflow, privileged container, mount capability or privilege acquisition permitted. Not9 independent CVEs. |
| [2026-78408](https://security-tracker.debian.org/tracker/CVE-2026-78408) | same util-linux; nsenter join-cgroup fix2.42.4, stable unfixed. Actual nsenter exists but is not used against host namespaces by app; UID10001/zero capabilities/no-new-privileges. Do not claim absent executable or kernel exploit tested. |
| [2026-78409](https://security-tracker.debian.org/tracker/CVE-2026-78409) | same util-linux; subdirectory mount traversal fix2.42.3, stable unfixed. No app-controlled privileged fstab/mount hook; actual no-new-privileges blocks acquiring SUID privilege. Raw findings/partial path assessment retained. |
| [2026-78410](https://security-tracker.debian.org/tracker/CVE-2026-78410) | same util-linux; bind mount source TOCTOU fix2.42.3, stable unfixed. No authorized user mount/host namespace workflow; bounded unprivileged runtime. No filesystem/kernel exploitation attempted. |
| [2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538) | Perl-base5.40.1-6+deb13u1; Archive::Tar3.10 fix, stable postponed pending upstream regressions. Perl exists but inspected Archive::Tar module absent; uploads use Python libraries, not Perl tar. Narrow module-path assessment; raw source-package alert retained. |

### Sixteen additional encoder CVEs

ALL following rows refer to actual signed restricted FFmpeg
**7:9.0.2-0chemistry1**. The fifteen non-RASC Debian pages identify upstream
n9.0/9.0.1/9.0.2 fixes while trixie's official7.1.x stays vulnerable. Building
that stable upstream on Debian13 does NOT install sid or claim an official
fixed Debian binary. Six runtime/provenance/config checks and real HLS
upload/encode/play/seek pass; neither proves every crafted exploit absent.

| Current raw CVE | Specific affected path / mitigation / fix evidence |
|---|---|
| [2026-58049](https://access.redhat.com/security/cve/cve-2026-58049) | RASC memory corruption: no independently verified fixing-content assertion; actual binary explicitly compiles RASC OUT and mandatory decoder-list check rejects accidental enablement. Allowed containers could carry RASC, so extension checking alone was never called sufficient. Raw warning remains. |
| [2026-64830](https://security-tracker.debian.org/tracker/CVE-2026-64830) | VobSub stream-count overflow, fixed n9.0 branch; standalone SUB/IDX excluded by format whitelist. Do not claim all subtitle code removed. |
| [2026-64832](https://security-tracker.debian.org/tracker/CVE-2026-64832) | NVDEC double-free, fixed n9.0; actual configure disables hardware autodetection and has no NVDEC acceleration. No GPU/device passed to worker. |
| [2026-64833](https://security-tracker.debian.org/tracker/CVE-2026-64833) | SPDIF-DTS mux bounds, fixed n9.0; output fixed to HLS/H264/AAC, not SPDIF. Encoded audio still handled; no blanket codec exclusion. |
| [2026-64834](https://security-tracker.debian.org/tracker/CVE-2026-64834) | RTP/ASF loop, fixed n9.0; network inputs/protocols disabled in actual binary, file-only whitelisted sources. |
| [2026-64835](https://security-tracker.debian.org/tracker/CVE-2026-64835) | ADX channel-state bounds, fixed n9.0; standalone AAX excluded but embedded decoder reachability not globally excluded. Signed newer source is primary evidence. |
| [2026-66036](https://security-tracker.debian.org/tracker/CVE-2026-66036) | hqdn3d variable-resolution/reinit-disabled path, fixed n9.0; app uses scale/setsar, not hqdn3d or reinit_filter0. |
| [2026-66039](https://security-tracker.debian.org/tracker/CVE-2026-66039) | MACE6/CAF integer overflow, fixed n9.0; CAF excluded, possible codec-in-other-container parsing not assumed impossible. |
| [2026-66040](https://security-tracker.debian.org/tracker/CVE-2026-66040) | PNG/APNG EXIF serialization, fixed n9.0; output H264/AAC, metadata discarded, no PNG/APNG encoding workflow. |
| [2026-66041](https://security-tracker.debian.org/tracker/CVE-2026-66041) | QUIRC filter copy, fixed n9.0; external library autodetection disabled, no QUIRC integration or subtitle filter in app command. |
| [2026-70628](https://security-tracker.debian.org/tracker/CVE-2026-70628) | DVB subtitle parser, fixed n9.0; WTV excluded and subtitles not selected for output. Probe parsing is not globally excluded solely by output selection. |
| [2026-70632](https://security-tracker.debian.org/tracker/CVE-2026-70632) | CFHD decoder invariant, fixed n9.0; AVI excluded, MOV CAN contain CFHD. Decoder can be reached; rely on verified newer source, not a false unreachability statement. |
| [2026-75142](https://security-tracker.debian.org/tracker/CVE-2026-75142) | MPEG-PS stream counts, fixed n9.0.1; no PS output, bounded mapped video/audio output streams. |
| [2026-75143](https://security-tracker.debian.org/tracker/CVE-2026-75143) | async RIST buffer, fixed n9.0.1; network/RIST protocol not compiled into actual restricted worker. |
| [2026-75144](https://security-tracker.debian.org/tracker/CVE-2026-75144) | VC2/Dirac RTP packetizer, fixed n9.0.1; no RTP output, fixed file HLS pipeline. |
| [2026-75146](https://security-tracker.debian.org/tracker/CVE-2026-75146) | live DASH negative fragment index, fixed n9.0.1; no live DASH/network demux workflow or protocol. |

All36 Trivy IDs and the3 Scout IDs have an explicit assessment, but raw scanner
gates remain NONZERO. Actual patched dependency evidence, absent/disabled
specific code and bounded non-root mitigation are three DIFFERENT states.
Unfixed stable-library risks/custom-build sign-off still require review before
release; no external server/CDN/DRM or blanket security readiness is claimed.

##8October resumed fresh scans — new Expat blocker

The following early-morning scan is historical BEFORE the later repair.
Final actual runtime images read09:33UTC are API`d8c8c6ff…` and encoder
`9f228147…`: both native AND CPython XML bindings2.9.0, stable Debian base
unchanged. Actual expanded UTF-16/buffer-capacity regressions20/0/0 EACH,
complete backend388/0/0, fresh/previous PostgreSQL migrations and missing-MPU
recovery allExit0. Mandatory Tesseract26 build cases and six signed/restricted
FFmpeg configuration checks also0. The old API buffer-capacity reproduction
failed0/1/0; it is not replaced by an unexplained version-only assertion.
The immutable dependency-only Extract comparison produced identical raw and
parsed outputs forALL7 fixtures, with exact unchanged parser/model hashes.
Both strict scopes remain6/1/0 (the user-deferred Biology failure), not7/0/0.
Details/current identities are in `QA_2026-10-08.md`. Final-image Scout was
started09:43UTC; results still pending, so the preceding3-High output below
is NOT the result of that final-image scan and no scanner gate is called closed.

That final-image Scout scan subsequently completed: actual API`d8c8c6ff…`
and encoder`9f228147…` EACH **3High/0Critical, rawExit2**, wrapperExit1.
Evidence `scout-video-{api,video-worker}-20261008-094322.sarif` and matching
immutable-ID command records. API252 packages/encoder255 indexed. BOTH raw
SARIFs still report77214,93990(expat2.9.0-0chemistry1) and85091(zlib source
1:1.3.dfsg+really1.3.1-1). All three use Debian trixie's **affected range>0 /
fixed version:not fixed**, so numerical upstream2.9.0 does not clear them.
No package/source renaming, fake official Debian revision or VEX-ignore is
used to conceal that limitation.

| Final Scout finding | Package/fix/actual-path assessment | Gate disposition |
|---|---|---|
| [77214](https://security-tracker.debian.org/tracker/CVE-2026-77214), expat2.9.0-0chemistry1, BOTH | The current tracker names the exact reviewed4d9b1c49… fix in stableR_2_9_0. Signed/hash-pinned2.9.0 is built on unchanged stable Debian, not sid. Native AND matching unmodified CPython XML bindings link this actual library. Before capacity regression0/1/0; after expanded20/0/0 EACH. XML callers exist; no blanket unreachability claim. | Application dependency repaired and regression verified; raw distro scanner warning retained, independent custom-build/source review required. |
| [93990](https://security-tracker.debian.org/tracker/CVE-2026-93990), expat2.9.0-0chemistry1, BOTH | The tracker identifies0cfd15bd… and28fcfba5… inR_2_8_5;2.9.0 retains both. The expanded native/pyexpat/C-elementtree LE/BE malformed+valid UTF-16 cases ALL pass. The early review's phrase2.8.4 applies to other Expat IDs, not the upstream release carryingTHIS93990 fix. | Actual source/binary fix verified; raw trixie>0 alert still visible, not suppressed or called scannerExit0. |
| [85091](https://security-tracker.debian.org/tracker/CVE-2026-85091), zlib1.3.1, BOTH | No current official stable Debian fixed package. Authenticated matching Debian source/quilt review finds no newly introducedgz_vacate helper/nonblocking1.3.1.2 path; exact source/signers/hashes above. App ZIP/compression/native zlib callers exist. This supports a narrowly scoped not-affected inference, not a compiled exploit test, update, or proof all zlib paths safe. | Raw scanner gate OPEN; independent review of source/range disagreement remains required. |

Scout also warned that Windows held its automatically created temporary image
archives open during cleanup. BOTH vulnerability reports were written and
the recorded exits are2 for detected findings, not silently treated as scanner
success. No manual deletion of Docker/user data or disk compaction followed.
Current final-image Trivy evidence remains pending, not inferred from Scout.

Actual immutable API`fe82e5f4…` and encoder`19de8aac…` scans completed on
this continuation. Scout EACH Exit2,3High/0Critical (wrapperExit1):
`CVE-2026-77214`, `CVE-2026-93990`, `CVE-2026-85091`.
Evidence: `scout-video-{api,video-worker}-20261008-064135.sarif`.
Trivy EACH Exit1 (wrapperExit1), API62 package findings/20unique CVEs,
encoder78/36: `trivy-20261008-064449/{api,video-worker}.sarif`.
The old41-CVE union below is historical, not today's exact result.
No raw alerts were removed, suppressed or severity-relabelled.

| Finding | Actual evidence and current state |
|---|---|
| [Expat77214](https://security-tracker.debian.org/tracker/CVE-2026-77214), native2.8.5-0chemistry1 | NEW OPEN blocker. Official buffer-capacity regression reproduced on the exact API image in128MiB/no-network/no-app-data isolated container: expected error41, actual4,0/1/0 Exit1. Stable upstream2.9.0 fixes it; adoption pending. Native XML callers and separately bundled Python2.8.5 require distinct verification. Existing UTF-16 tests do not cover this path. |
| Expat93990 and other Trivy Expat IDs | Source2.8.5 already contains the cited upstream malformed UTF-16/2.8.4 fixes; prior native4/0/0 proves only UTF-16. Debian range alerts stay visible; new2.9.0 adoption must rerun these tests too. |
| [zlib85091](https://security-tracker.debian.org/tracker/CVE-2026-85091) | Raw scanner gate remains OPEN. Packaged-source reconciliation below now exists for the ACTUAL installed1.3.1 source. It supports a narrowly scoped not-affected assessment for the introduced nonblocking helper, not a package update, exploit test, or scanner suppression. |

###8October authenticated zlib packaged-source reconciliation

Read-only `dpkg-query` on both actual API and encoder returned
`zlib1g:amd64|1:1.3.dfsg+really1.3.1-1+b1|zlib|1:1.3.dfsg+really1.3.1-1`,
Exit0. `scripts/qa/check-zlib-source.ps1` verified Debian's signed source
descriptor and all SHA256-pinned source/quilt archives in a separate bounded
container, with NO application data, secrets, or runtime changes. Review
Exit0; evidence `zlib-source-review-20261008-085155/`.
Descriptor signer subkey`ADE668AA675718B59FE29FEA24D68B725D5487D0`, primary
`3F2568AAC26998F9E813A1C5C3F436CA30F5D8EB`, authenticated by Debian keyring.
The reproducible tool now also enforces both full fingerprints and the actual
installed source metadata, refusing this conclusion if either differs.

The authenticated source has `ZLIB_VERSION "1.3.1"`, an empty Debian quilt
series and NO `gz_vacate`. `gzwrite.c` SHA256 is
`469b1e58932ea11bdda2a153f6655f7b3c13254240fae157181b49ed1bc93b47`.
The [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-85091)
still marks trixie vulnerable, but its description and introduction note
identify1.3.1.2..1.3.2 nonblocking-device support. The
[official fixing commit](https://github.com/madler/zlib/commit/df84af25dc1942490e1d1c899a07619152a46148)
resets the stalled external buffer pointer in that newer path. This is a
source-based inference that the described newly introduced path is absent
from THIS packaged revision. It is NOT a general claim that gzip/ZIP/Python
or native callers cannot use zlib. No CVE was removed from either raw scan,
no severity/ignore rule was introduced, and independent review of the
tracker/version disagreement remains required before treating the scanner
gate as closed. This review did not compile/reproduce the third-party exploit.

[Stable2.9.0 release notes](https://raw.githubusercontent.com/libexpat/libexpat/R_2_9_0/expat/Changes)
also identify `CVE-2026-102633`, a32-bit `expat_realloc` integer overflow.
Actual runtimes are Linuxamd64; this is source assessment, not a32-bit exploit
test. Neither it nor the upstream's remaining non-public issue list justifies
claiming all Expat flaws removed after an update.

##8October actual application adoption — before the resumed scans

Two complete Build/startup commandsExit0; the second contains the final
discussion/application source. Actual runtimes read04:46UTC: API
`sha256:fe82e5f474b60275df0cfa8354b8417051adea086e09b38faac68fdd47fd86a2`,
encoder`sha256:19de8aac2dffc2c8bd04bc13cd7a0f8f24d2bce30aa2abd8ee11953b86af01a2`.
Read-only inventoryExit0 EACH: authentic OpenSSL3.5.7-1~deb13u3,
liblzma5.8.1-1+deb13u2 and genuine Tesseract5.5.0-1+chemistry2.
The six pinned reviewed official backports were independently compiled and
their mandatory26/0/0 native tests passed in the actual production builder.
The nonsecret XML/patch/signature/source evidence is retained inside both
images. Native test/compiler/GoogleTest executables remain out of runtime;
no claim of rerunning the test binary there or ASAN/exploit proof.
Trustedara/eng/osd model SHA match all three original pre-update bytes in
BOTH images, Exit0. Candidate strict7-output parity remains6/1/0 EACH, not a
biology fidelity fix. Final actual-image strict comparison still required.

Backend gateExit0: API382/0/0, actual Expat4/0/0 EACH, actual signed/restricted
FFmpeg9.0.2 checks6/0/0, fresh/previous-head migrations and real missing-MPU
recovery. Source SHA gateExit0 compares121 files in each API/Celery/encoder,
zero differences. These results are NOT a fresh Trivy/Scout pass or permission
to erase earlier alerts; raw scans/sign-off remain OPEN.

The new liblzma update fixes the
[decoder-reinitialization allocation-failure issue](https://security-tracker.debian.org/tracker/TEMP-1147318-639065)
which remained vulnerable inu1. The separately named
[CVE-2026-34743 index-append issue](https://security-tracker.debian.org/tracker/CVE-2026-34743)
was already fixed inu1; do not count it as newly repaired. Signed stable suites
only, no scanner ignores/version fabrication/severity overrides.

## Resumed B10 runtime check — 7 October,19:03UTC

The B7 raw scan table below is historical, NOT a scan of B10. Current read-only
`scripts.security_runtime_inventory` returnedExit0 for BOTH running B10 images
(API57dc0269…, encoder e295c415…), with actual OpenSSL/libssl
`3.5.7-1~deb13u3`, Expat/Python Expat2.8.5 and Tesseract5.5.0-1+chemistry1.
Evidence: `security-b10-{api,video-worker}-20261007-1857.json`.
The [current Debian OpenSSL tracker](https://security-tracker.debian.org/tracker/CVE-2026-84782)
marks that authentic trixie-security revision fixed. The isolated stable-package
probe returnedExit0; `stable-packages-20261007-190244/policy.txt` confirms signed
trixie, trixie-updates and trixie-security enabled, installed/candidate OpenSSL
matching, and the simulated upgrade reporting0 upgraded/0 new/0 removed/0 held.
It did not modify the running application. Fresh BOTH-image raw scans remain
required; a corrected package is not a blanket zero-vulnerability claim.

The original paragraph's PREPARE-only evidence is superseded by the8October
candidate result below, NOT by an adopted application image. Six official
upstream patches are pinned in the now-shared
`apps/api/scripts/native/tesseract/backports.tsv`. Original Debian source hashes and signer
406220C8B8552802378CCE411F5C7A8B45564314 were actually verified. The first
prepare attempt failed because88053 did not apply unchanged to5.5.0; the second
failed our context-count guard. Both failures/artifacts remain. Reviewed
context-only ports preserve added runtime security guards; the derived88053
patch is independently pinned at718594436d7fa5f6fedb194484f8d75a4f3cb91c38398c71310d3005177b8675.
Prepare-v3 returnedExit0 (`tesseract-backport-prepare-v3-20261007-1902/`), but
that Prepare result is still not a binary/test result.

On8October the first compile failedExit2 at the old pointer-taking call; the
reviewed `stable-callsite.diff` preserves it via `.data()`, SHA
1646a66c1e340b6f71fa4852945b77d42c91189d8599a6e1746128cd4869ceab.
The second build compiled/installed the engine, then failedExit1 BEFORE test
collection because the runner lacked5.5.0's training/unicharset header path.
That failed run and one failed test-only include-path attempt remain retained.
Corrected actual static-library regressions completed **26/0/0, Exit0**;
the new shared runner independently repeated26/0/0. Fifteen original upstream
bodies and eleven overflow/negative/valid controls, no mocks or ASAN claim.
Raw artifacts: `tesseract-native-tests-20261008-040955-443516/` and
`tesseract-native-tests-20261008-041546-836167/`.

`ocr-runtime-20261008-041158/`: both actual baseline and mounted candidate use
the same models/parser/reference/original input SHA. ALL7 parsed results are
identical; both strict outcomes **6/1/0, Exit1**. Biology's known7/10matching
and CER0.008645533141210375 remain failures, explicitly deferred by the user.
No image-specific answer/reference/model edit or strict-gate waiver.

Shared source application/native-test tooling is now used by the proposed
application build: genuine `5.5.0-1+chemistry2`, not a fictional Debian fixed
revision or scanner suppression. Its26-case build-time test gate is mandatory;
only nonsecret test/source/signature/patch metadata enter runtime, not compiler,
GoogleTest or native test binary. Real application build and full runtime/scans
are currently PENDING. Until those complete, all six runtime Tesseract rows
remain OPEN; candidate evidence alone is not current runtime protection.

The8October fresh signed stable assessment (`stable-packages-20261008-041131/`,
Exit0) additionally found liblzma5 installed5.8.1-1+deb13u1, candidateu2, exactly
one simulated upgrade. Reviewed runtime apt-index refresh and minimumu2
assertion are in source, but that probe itself did NOT install into the app.
No unstable distribution, ignored CVE or lowered severity.

## Actual B7 scan and inventory — 7 October,09:44UTC

The in-progress paragraph below is historical. Same-version signed OCR build
and actual package/ldd inventory are complete; the security gate is still OPEN.

| Actual image | Trivy High / Critical / Exit | Scout High / Critical / Exit |
|---|---|---|
| API `sha256:dfb1939048e78ee4a7520a2c88a636b00a702c2873c7b25638be9cd9f7d29884` | 62 / 0 / 1 | 3 / 0 / 2 |
| Encoder `sha256:5a5cc7470cec835993825698a5c06c2a60678ab5f28741ac29ec804fadb31c40` | 79 / 0 / 1 | 5 / 0 / 2 |

Complete raw evidence: `trivy-20261007-094251/{api,video-worker}.sarif`,
`scout-video-{api,video-worker}-20261007-094408.sarif`, respective command JSON,
and `security-b7-20261007-0941/`. Fresh Trivy DB was actually downloaded. Scout
cleanup-lock warning is retained separately from complete indexed reports.
No suppressions, ignores, severity overrides or fabricated version strings.
Actual deduplicated union across these FOUR reports: **41 CVE IDs**, not57.
Historical reports/assessments below are retained; counts must not be mixed.

Actual B7 OS libxml2/curl/Poppler/libarchive are absent. Tesseract5.5.0 local
package is compiled from signed Debian5.5.0-1 with genuine provenance, no
optional curl/archive/XML/graphics links. This removes unused dependencies,
not the six remaining engine/model findings. Native Expat2.8.5 and Python
Expat2.8.5 each pass4/0/0 regressions per image; Linux64 nothrow aligned-new
passes10/0/0 per image but is NOT a blanket GCC/PBDS waiver. OpenSSL remains
the authentic fixed trixie-security3.5.7-1~deb13u3. **Bundled lxml/libxml2.14.6
is separate**, external-entity probe false/Python SAX binding absent are only
narrow mitigation evidence, not proof that every native XML flaw is absent.

Current raw Scout records, individually reviewed against primary trackers:

| CVE / actual package / scope | Current source/fix status and reachability | Gate |
|---|---|---|
| [95619](https://security-tracker.debian.org/tracker/CVE-2026-95619); gcc14.2.0-19, both | Stable trixie still unfixed. C++ native libraries present; limited actual aligned-new10/0/0 negative-path test does not exclude all C++ paths. Non-root/bounded process mitigations. | OPEN |
| [85091](https://security-tracker.debian.org/tracker/CVE-2026-85091); zlib1:1.3.dfsg+really1.3.1-1+b1/Python1.3.1, both | Tracker still marks trixie vulnerable while described introduction is1.3.1.2. Application compression exists; no direct nonblocking gzprintf/gzvprintf identified. Upstream patch exists; version dispute is NOT suppressed. | OPEN |
| [93990](https://security-tracker.debian.org/tracker/CVE-2026-93990); libexpat1 2.8.5-0chemistry1/Python2.8.5, both | Actual upstream fixed release and4/0/0 runtime regressions EACH image, including malformedUTF16. Debian range matching remains raw despite the corrected binary. | Corrected binary evidenced; scanner/sign-off OPEN |
| [30997](https://security-tracker.debian.org/tracker/CVE-2026-30997); FFmpeg7:7.1.5-0chemistry1, encoder | AV1 input reachable. Upstream7.1.4 fix is included in authentic7.1.5; raw Debian revision comparison still flags. New9.0.2 stable candidate requires fresh tests. | OPEN raw finding |
| [38347](https://security-tracker.debian.org/tracker/CVE-2026-38347); same FFmpeg, encoder | swscale is actually used. Upstream7.1.5 fix/provenance retained, no claim of every crafted exploit tested. New9.0.2 candidate pending. | OPEN raw finding |

Fresh source rechecks also confirm no current stable trixie update for
[ACL54369](https://security-tracker.debian.org/tracker/CVE-2026-54369)
(new acl_*_at ABI), [TIFF36849](https://security-tracker.debian.org/tracker/CVE-2026-36849),
[TIFF52490](https://security-tracker.debian.org/tracker/CVE-2026-52490),
[systemd16742](https://security-tracker.debian.org/tracker/CVE-2026-16742),
[ncurses69720](https://security-tracker.debian.org/tracker/CVE-2025-69720),
[Perl9538](https://security-tracker.debian.org/tracker/CVE-2026-9538) and the
four util-linux76642/78408/78409/78410 rows below. Their existing per-path
assessments remain OPEN; fixed testing/unstable packages are not installed.
Current versions: ACL2.3.2-2+b1; TIFF4.7.0-3+deb13u3; systemd257.13-1~deb13u1;
ncurses6.5+20250216-2; Perl5.40.1-6+deb13u1; util-linux2.41.5-0+deb13u1.
Expat66046/76956 fixes are in actual2.8.5. The76957 primary re-fetch failed
twice today; its earlier fixed2.8.4 assessment is retained, not a new fetch.

Current Tesseract engine/model rows below still apply to actual
5.5.0-1+chemistry1. New primary88051/88052/88053 rechecks confirm crafted
traineddata initialization paths and no fixed release even in5.5.3; upstream
patches exist. Fixed language/model configuration narrows input reachability,
but no uploaded traineddata exploit or blanket dependency fix is claimed.
The5.5.3 OCR experiment was rejected for worse original-fixture accuracy;
the user's later BIOLOGY deferral does not erase these security alerts.

Actual B7 read-only model inspection on7October: tessdata directory0:0/0755,
ara/eng/osd models0:0/0644, source provenance0:0/0644. Actual SHA256:
ara`e3206d3dc87fd50c24a0fb9f01838615911d25168f4e64415244b67d2bb3e729`,
eng`7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`,
osd`9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff`.
This establishes trusted model ownership/identity for this image only, not
absence of every model parser issue or a reason to hide the six raw CVEs.

## Stable upstream encoder update in progress — 7 October,10:13UTC

[Official FFmpeg9.0.2](https://ffmpeg.org/download.html) is a signed STABLE
release, not an unstable Debian distribution. The archive's actual pinned
SHA256 `8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e`
and GPG VALIDSIG `FCF986EA15E6E293A5644F10B4322F04D67658D8` were verified
locally, Exit0, before updating the native builder. B8 remains PENDING: stable
Debian base and network/device restrictions remain, but real codec/HLS/seek,
fault recovery, BOTH raw scans and final tests must be repeated. No B7 result
is claimed as proof for the new major encoder version.

Primary rechecks of FFmpeg64830/64832/64833/64834/64835,66036/66039/66040/66041,
70628/70632,75142/75143/75144/75146 and8461 retain their fixed9.0-series
upstream status (with exact commits linked in the individual rows below).
This motivated trying the actual stable source instead of merely recording
missing trixie7.1 backports. Each actual-image alert still requires rescan.
[RASC58049 CNA](https://access.redhat.com/security/cve/cve-2026-58049) does NOT
provide fix-content proof for this candidate. The build therefore explicitly
disables that unused legacy decoder and fails if actual `ffmpeg -decoders`
still lists it. This is a code-path mitigation, not a package/CVE waiver:
its raw alert remains visible. Common MP4/MOV/WebM codecs remain enabled;
RASC-encoded uploads cannot be supported by this restricted worker and must
fail safely rather than invoke the decoder. Actual binary/build/video tests
are still PENDING. No external PoC was downloaded or executed.

### Historical B7 dependency-reduction build in progress (7October09:24UTC)

Primary Debian pages were fetched again successfully for
[OpenSSL84782](https://security-tracker.debian.org/tracker/CVE-2026-84782),
[gcc95619](https://security-tracker.debian.org/tracker/CVE-2026-95619),
[libxml2 Critical6653](https://security-tracker.debian.org/tracker/CVE-2026-6653)
and [86140](https://security-tracker.debian.org/tracker/CVE-2026-86140): fixed
OpenSSL trixie-security3.5.7-1~deb13u3 and affected stable GCC/libxml revisions
are unchanged. The gcc102010 fetch timed out; its earlier assessment is retained,
not claimed as a successful new check. B7 builds the SAME signed Debian OCR
source without unused URL/archive/graphics integrations and removes unused
curl/Poppler. Official DSC gpgv and exact signer checks have actually passed.
The candidate has identical parsed outputs on all seven originals but retains
the strict biology failure. Actual final image package absence, native/runtime
regressions and BOTH raw scanners are still PENDING. Prior image scan counts
below must not be represented as B7 findings or a clean security gate.

### Primary-source recheck — 7 October, after B4 integration

The earlier gcc95619 tracker timeout is historical: today's successful
[Debian95619](https://security-tracker.debian.org/tracker/CVE-2026-95619)
fetch still lists gcc14.2.0-19 affected and no fixed stable revision.
The successful recheck also retains affected stable
[gcc102010](https://security-tracker.debian.org/tracker/CVE-2026-102010),
[libxml2 Critical6653](https://security-tracker.debian.org/tracker/CVE-2026-6653)
and [libxml286140](https://security-tracker.debian.org/tracker/CVE-2026-86140).
The first diagnostic requested an incorrect26653 URL and failed;6653 is the
actual report finding, verified separately. No failed fetch is used as proof.
[OpenSSL84782](https://security-tracker.debian.org/tracker/CVE-2026-84782)
still records trixie-security3.5.7-1~deb13u3 fixed, already installed.
[FFmpeg30997](https://security-tracker.debian.org/tracker/CVE-2026-30997) and
[38347](https://security-tracker.debian.org/tracker/CVE-2026-38347) still record
upstream7.1.4/7.1.5 fixes and stable Debian7.1.5u1. Package-revision matching
versus verified custom build remains a separate assessment, never suppression.
Final B4 actual-image raw scans are separate from the earlier B3 outputs below.

## Final security-header rebuild scan (6 October,18:01UTC)

### Latest refresh — 7 October,03:32UTC

The API and encoder immutable identities below are unchanged. Both images
were scanned again after Docker's normal restart (no reset/data deletion):
Trivy `trivy-20261007-033203/` has the same92/109 findings (API91High+1Critical;
encoder108High+1Critical), eachExit1. Scout
`scout-video-{api,video-worker}-20261007-033207.sarif` reports API5High,
encoder7High,0Critical; eachExit2, wrapperExit1. Both complete raw outputs
and command JSON remain private QA artifacts. No ignores/severity overrides
or packages were changed between these scans.

Scout no longer includes CVE-2026-102010 in its High/Critical output. Current
scanner union is56distinct IDs; the historical57-ID review below is preserved.
This is a scanner-data/filter observation, NOT a code fix or severity change
made by this project. The [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-102010)
still lists trixie gcc14.2.0-19 vulnerable and marks the issue no-dsa/minor.
Its previous assessment is not erased. Current primary-source rechecks retain
trixie [libxml2 Critical6653](https://security-tracker.debian.org/tracker/CVE-2026-6653)
and [86140](https://security-tracker.debian.org/tracker/CVE-2026-86140) as affected;
the unstable2.15.4 ABI is not substituted. Stable
[OpenSSL3.5.7-1~deb13u3](https://security-tracker.debian.org/tracker/CVE-2026-84782)
is still the fixed trixie-security version already installed.

Scout retains FFmpeg30997/38347 against the custom7.1.5 package revision.
Debian records genuine7.1.4/7.1.5 upstream fixes and stable Debian7.1.5u1:
[30997](https://security-tracker.debian.org/tracker/CVE-2026-30997),
[38347](https://security-tracker.debian.org/tracker/CVE-2026-38347).
The pinned upstream source/build provenance remains separate from raw scanner
matching; no Debian revision is fabricated to clear them. A new fetch of the
gcc95619 tracker timed out twice, so yesterday's assessment is retained without
claiming that failed fetch verified today's status. Release gate remains OPEN.

Fresh signed apt indexes were also fetched in disposable image-derived
containers, with no application environment/volumes/socket and no package
installation. `check-stable-packages.ps1` Exit0 for API and encoder;
`stable-packages-20261007-034310`/`034226` retain raw policy and provenance.
Sources are trixie, trixie-updates and trixie-security, not unstable or frozen
snapshot URLs (snapshot lines are comments only). API simulation: zero
upgrades. OpenSSL/libssl3t64 candidate equals installed3.5.7-1~deb13u3;
libxml2 candidate equals installed2.12.7+dfsg+really2.9.14-2.1+deb13u3;
libstdc++6 remains14.2.0-19, PCRE2 remains10.46-1~deb13u3. Genuine Expat2.8.5
custom build remains newer than Debian's2.8.3u1, not a hidden downgrade.

Encoder simulation keeps ffmpeg back: Debian7:7.1.5-0+deb13u1 is offered
against the custom7:7.1.5-0chemistry1 build. Both use upstream7.1.5; the
Debian package is not an additional upstream fix. The custom source/build
verification and disabled network/devices/hardware accelerators remain
material mitigations; swapping to the distro build would add dependencies
and enable paths and is not automatically a security improvement. No fake
package revision or forceful replacement was used. Raw30997/38347 findings
remain visible. Initial apt probe with all capabilities dropped exited100
(could not switch downloader user); subsequent limited disposable apt
capabilities succeeded. No production capability/user change.

Current immutable B3 images each also passed `native-aligned-new.py` again,
Exit0,10/0/0. This is the limited64-bit Linux nothrow aligned-new ABI test,
not an exemption for PBDS, all C++ paths, or the raw GCC finding.

Current rebuild at the start of the final functional repeat:

| Runtime | Actual immutable image | Trivy High / Critical | Scout High / Critical |
|---|---|---|---|
| API | `sha256:b4bbc0e0767568b936916b5af116362f158926a3fc55364258571160f7688f98` | 91 / 1 | 6 / 0 |
| Encoder | `sha256:d3de48f473a91abce97cfb5fc3d055f2abd05038940fae9756974ab79aa82513` | 108 / 1 | 8 / 0 |

Trivy `.qa/audit2/trivy-20261006-180138/`: every raw scanExit1, wrapperExit1,
complete SARIF/command artifacts. Exact ruleID+finding-message comparison to
173046 again gave **zero differences** for either image. Scout complete raw
reports `scout-video-{api,video-worker}-20261006-180212.sarif`, eachExit2,
wrapperExit1, completed18:03:49Z/18:05:21Z. The temporary archive cleanup lock
warning remains separate from successful report indexing. All57 reviewed
union IDs below still apply; no finding was suppressed or severity changed.

The API security-header code changed; native builder/source/package revisions
did not. Subsequent functional/image source tests must refer to these image
identities, not the earlier17:30 or14:18 tables retained below.

## Two-step/backoff scan (6 October,17:30UTC)

The earlier image tables below are historical. Rebuilt runtime images at this
scan (the later security-header rebuild needs its own repeat):

| Runtime | Actual immutable image | Trivy High / Critical | Scout High / Critical |
|---|---|---|---|
| API | `sha256:fa0f8bfb7e04067b03eba9739040a1d7adb324fc4019e656c95ef3eabe9a5f9f` | 91 / 1 | 6 / 0 |
| Encoder | `sha256:7693bd46d712d08bd617dbcc9fb43f75945782d4d207f3813921a47675a4d96a` | 108 / 1 | 8 / 0 |

`run-trivy.ps1`: wrapper and each image Exit1, complete SARIFs in
`.qa/audit2/trivy-20261006-173046/`, command JSON retained. Comparing every
rule ID and full finding message to141841 yields **zero differences** in
both images. All52 distinct Trivy CVEs/57 union IDs below remain accounted for.
`run-video.ps1 -Stage Scan -ApproveScout`: wrapperExit1, each scannerExit2,
reports `scout-video-{api,video-worker}-20261006-173114.sarif`; completed
API17:32:49Z/encoder17:34:44Z. The Windows temporary archive cleanup lock
warning followed complete report generation, not an absent scan result.
No native dependency version, CVE severity, ignore rule or scanner exclusion
was changed to make these application-only rebuilds pass.

### MagicYUV exact source-content verification

The [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-8461)
names the official n7.1.5 fix
[15882781](https://github.com/FFmpeg/FFmpeg/commit/15882781ac5267a653e4e55f5fa656ba9db688fd).
`scripts/qa/verify-ffmpeg-magicyuv.py` verifies the release SHA pinned by
`build_native_ffmpeg.sh`, the exact official patch SHA/header, then performs
`git apply --no-index --reverse --check --whitespace=error` on ONLY the regular
MagicYUV source member in a disposable temporary directory; never edits runtime
binaries or executes media/third-party PoCs. **Exit0,3/0/0** on6October:

- Archive SHA256 `de668509caf9e35e3cd162473441fdb29538c6d96ed080292b3cf9e6fc5d558f`.
- Patch SHA256 `a18ad773eab74dbd268f82933cc9bf93d77ac959afbb9be12abb5e6d62ba5d5f`.
- Release source Git blob SHA1 `074ac0e3ffa92fd901b6725f08820c06d1971e88`.
- Actual current encoder `dpkg-query` and `ffmpeg -version`, bothExit0:
  `7:7.1.5-0chemistry1`, upstream7.1.5 and expected static/no-network flags.

First default-sandbox invocation failed WinError5 reading the archive; the
same check succeeded with authorized read access, not by relaxing assertions.
Reading `/usr/share/doc/ffmpeg/chemistry-source.txt` returnedExit1 because the
slim base's dpkg configuration excludes documentation except copyright.
This file's presence is **not** claimed as evidence. The pinned build script,
source SHA and actual binary version are separate provenance observations.
Upstream's commit says no testcase: this reverse check establishes fix-content
in the pinned source, **not** a specific binary exploitation/regression proof.
The raw finding and overall native gate stay OPEN.

## Image and scanner provenance

Fresh Trivy results after the final runtime rebuild at
`.qa/audit2/trivy-20261006-141841/`:

| Runtime | Immutable tested/scanned image | High / Critical package-CVE occurrences | Exit |
|---|---|---|---|
| API | `sha256:b89f26fa60dd681f2410252b17b2c631d74a08a4e2c248f08762a53dc1d6e015` | 91 / 1 | 1 |
| Encoder | `sha256:056a126088a2fc5cae47719263de42b44bec1659aaf8ecfc05085c470e9f06ee` | 108 / 1 | 1 |

Scanner: `aquasec/trivy:0.69.3@sha256:7228e304ae0f610a1fad937baa463598cadac0c2ac4027cc68f3a8b997115689`.
52 distinct CVEs across both images; repeated binary packages are NOT distinct
vulnerabilities. Both raw SARIFs and `commands.json` are retained locally.
The earlier125754 scan is retained too. Comparing every rule ID and full
result message (including package/version/fix text) gives zero differences
for both images; the per-CVE review below therefore still covers all current
findings. The final rebuild changed application code, not native package fixes.
The scanner warned that a newer tool version exists; its vulnerability database
was freshly fetched. An initial Docker Scout attempt failed authentication;
the user then signed in and the repeat produced complete current SARIFs.
Run `scripts/qa/run-trivy.ps1` to repeat; `run-video.ps1 -Stage Scan -ApproveScout`
requires Scout authentication and the separately approved SBOM sharing.

An ephemeral container from this same API image ran `apt-get update` and
`apt-cache policy`: signed **trixie / trixie-updates / trixie-security** only.
Installed OpenSSL/libssl `3.5.7-1~deb13u3` equals the stable candidate and fixes
the previously reported [CVE-2026-84782](https://security-tracker.debian.org/tracker/CVE-2026-84782).
The other installed stable package candidates below were unchanged. This does
not imply that each upstream fix is packaged in trixie.

## Versions and reachability evidence

Both images carry the API's OCR/PDF dependencies. Runtime inventory
`python -m scripts.security_runtime_inventory` (Exit 0) shows that Poppler and
Tesseract link native dependencies. Python lxml bundles libxml **2.14.6**, not
the OS libxml binary; the DOCX parser's external-entity probe returned false.
That narrows one path, not all XML paths in native consumers.

* XML: `libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3`.
* Tesseract: `tesseract-ocr/libtesseract5 5.5.0-1+b1`; signed, fixed, root-owned
  traineddata; uploads cannot replace model files.
* Curl: `curl/libcurl4t64/libcurl3t64-gnutls 8.14.1-2+deb13u5`.
* Expat: authentic stable source `libexpat1 2.8.5-0chemistry1`; build/source hash
  is pinned in `build_native_expat.sh`; Python and OS runtime checked separately.
* GnuPG: `2.4.7-21+deb13u1` (some binaries `+b5`); simulated purging also removes
  Poppler PDF support, so it was not blindly applied.
* util-linux: `2.41.5-0+deb13u1`; bsdutils has epoch `1:`, login is
  `1:4.16.0-2+really2.41.5-0+deb13u1`. Related binary packages: libblkid1,
  liblastlog2-2, libmount1, libsmartcols1, libuuid1, mount, util-linux, bsdutils.
* ncurses/libtinfo: `6.5+20250216-2`; systemd/udev libs: `257.13-1~deb13u1`;
  TIFF: `4.7.0-3+deb13u3`; ACL: `2.3.2-2+b1`; Perl base: `5.40.1-6+deb13u1`;
  X11: `2:1.8.12-1`; Xrender: `1:0.9.12-1`.
* Encoder FFmpeg: stable, signed upstream **7.1.5**, package
  `7:7.1.5-0chemistry1`; never relabelled as an official Debian binary.

API and workers are non-root with dropped capabilities/no-new-privileges.
The headless runtime has no DISPLAY or X11 socket directory. `infocmp` and
`gpg` exist; `tiffcrop` and `systemd-homed` were not found on PATH. Absence of a
CLI is not proof that every affected library entry point is unreachable.

Video probe and encoding accept **file only**, format whitelist
`mov,matroska,webm`, fixed output H264/AAC/HLS, maps one video plus optional
audio, disables subtitle/data output and metadata; only `scale,setsar` filters.
Actual `ffmpeg -hwaccels` is empty. `-protocols` contains no HTTP/RTP/RIST network
inputs. Build disables network/devices/autodetection. Native decoder probing
still happens: an allowed container can wrap a rare codec, so a demux whitelist
alone is NOT proof that ADX/MACE/CFHD/RASC/MagicYUV decoder defects cannot run.
Memory/CPU/file-size/deadline limits and isolation reduce impact, not CVE status.

## Every current CVE

All rows remain in raw results at their original severity. Except Expat source
fixes below, **OPEN** means no verified compatible stable-image fix applied.
Debian source-package status is not always a perfect match for a custom binary.
Each Debian link is the primary tracker consulted on 6 October; if it timed
out, an available primary vendor source is noted instead.

| CVE (primary source) | Package family / affected path | Fixed version or remaining action; application assessment |
|---|---|---|
| [2025-69720](https://security-tracker.debian.org/tracker/CVE-2025-69720) | ncurses / infocmp string analysis | Upstream 6.5-20251213/6.6; stable candidate still affected. Application does not invoke infocmp; tool is present. OPEN. |
| [2026-12064](https://curl.se/docs/CVE-2026-12064.html) | curl / default SSH protocol verification | Upstream fix exists, stable candidate unchanged. No SSH upload/downloader API; native libcurl consumers not exhaustively proven unreachable. OPEN. |
| [2026-16742](https://security-tracker.debian.org/tracker/CVE-2026-16742) | systemd / homed local groups | Upstream 258.10/261.2; installed libs still flagged, homed CLI not found. No privileged homed service configured. OPEN. |
| [2026-24882](https://security-tracker.debian.org/tracker/CVE-2026-24882) | GnuPG / TPM2 PKDECRYPT | Upstream 2.5.17; stable candidate unchanged. No TPM key/decryption workflow; GPG binaries present and PDF consumer retained. OPEN. |
| [2026-36849](https://security-tracker.debian.org/tracker/CVE-2026-36849) | TIFF / SamplesPerPixel resource exhaustion | Upstream 4.7.2; uploaded OCR images reach TIFF/Leptonica. Bounded subprocesses, no complete exclusion proof. OPEN. |
| [2026-52490](https://security-tracker.debian.org/tracker/CVE-2026-52490) | TIFF / tiffcrop options | Upstream 4.7.2; tiffcrop CLI not found, application invokes fixed OCR/PDF commands, not tiffcrop. Library still flagged. OPEN. |
| [2026-54369](https://security-tracker.debian.org/tracker/CVE-2026-54369) | ACL / pathname symlinks | Upstream 2.4.0 entails ABI changes; no verified trixie backport. No privileged app ACL calls, but not a library fix. OPEN. |
| [2026-66046](https://security-tracker.debian.org/tracker/CVE-2026-66046) | Expat / attribute complexity | Upstream fixed 2.8.4, our authentic 2.8.5 includes it. Scanner OPEN; upstream-fix evidence, not a specific uploaded exploit test. |
| [2026-6653](https://security-tracker.debian.org/tracker/CVE-2026-6653) | **libxml2 CRITICAL** / internal subset entity UAF | Upstream 2.11 fix; stable legacy ABI candidate remains flagged. New distro ABI is not a safe drop-in. DOCX XXE disabled, native consumers retained. OPEN. |
| [2026-73066](https://security-tracker.debian.org/tracker/CVE-2026-73066) | Tesseract / Convolve model deserialization | Upstream 5.5.3; stable 5.5.0 unchanged. Trusted read-only traineddata, not arbitrary user models. OPEN. |
| [2026-74860](https://security-tracker.debian.org/tracker/CVE-2026-74860) | libxml2 / native XML processing | Stable candidate still affected; separate bundled lxml does not clear OS finding. Native parser reachability not fully excluded. OPEN. |
| [2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642) | util-linux / mount helper privileges | Upstream 2.42.3; no app mount/fstab workflow, non-root/no capabilities. OPEN. |
| [2026-76956](https://security-tracker.debian.org/tracker/CVE-2026-76956) | Expat / entropy hash flooding | Fixed upstream 2.8.4; genuine 2.8.5 compiled. Scanner OPEN, no suppression. |
| [2026-76957](https://security-tracker.debian.org/tracker/CVE-2026-76957) | Expat / custom encoding callback | Fixed upstream 2.8.4; genuine 2.8.5 compiled. Scanner OPEN, no claim of per-CVE exploitation proof. |
| [2026-78408](https://security-tracker.debian.org/tracker/CVE-2026-78408) | util-linux / nsenter cgroups | Upstream 2.42.4; no nsenter workflow/container host privileges. OPEN. |
| [2026-78409](https://security-tracker.debian.org/tracker/CVE-2026-78409) | util-linux / subdir mount symlink | Upstream 2.42.3; no user mounts/privileged fstab workflow. OPEN. |
| [2026-78410](https://security-tracker.debian.org/tracker/CVE-2026-78410) | util-linux / bind mount TOCTOU | Upstream 2.42.3; no mount capability in application runtime. OPEN. |
| [2026-8286](https://curl.se/docs/CVE-2026-8286.html) | curl / STARTTLS connection reuse | Upstream fix exists; stable package unchanged. SMTP uses Python, not curl STARTTLS; native consumer scope not fully proven. OPEN. |
| [2026-8458](https://curl.se/docs/CVE-2026-8458.html) | curl / Negotiate connection reuse | Upstream fix exists; no app Negotiate workflow, native consumer scope not fully proven. OPEN. |
| [2026-86138](https://security-tracker.debian.org/tracker/CVE-2026-86138) | libxml2 / dictionary QNames | Upstream 2.15.4; stable candidate unchanged, native consumers may process upload-derived XML. OPEN. |
| [2026-86139](https://security-tracker.debian.org/tracker/CVE-2026-86139) | libxml2 / URI escaping | Upstream 2.15.4; introduced-version versus Debian really2.9.14 needs binary-specific verification; retained OPEN. |
| [2026-86140](https://security-tracker.debian.org/tracker/CVE-2026-86140) | libxml2 / native parser path | Upstream stable fix not available as current trixie candidate; partial consumer assessment, no waiver. OPEN. |
| [2026-86142](https://security-tracker.debian.org/tracker/CVE-2026-86142) | libxml2 / XPointer length | Upstream 2.15.4; native XML dependencies retained. OPEN. |
| [2026-86143](https://security-tracker.debian.org/tracker/CVE-2026-86143) | libxml2 / output callback negative length | Upstream 2.15.4; no custom callback in Python DOCX path, native consumers not fully excluded. OPEN. |
| [2026-86144](https://security-tracker.debian.org/tracker/CVE-2026-86144) | libxml2 / XInclude NONET loss | Upstream 2.15.4; DOCX entity resolution off, not proof for all native XML consumers. OPEN. |
| [2026-88047](https://security-tracker.debian.org/tracker/CVE-2026-88047) | Tesseract / NormProtos model | Upstream patch, no verified fixed stable release installed. Root-owned fixed traineddata. OPEN. |
| [2026-88048](https://security-tracker.debian.org/tracker/CVE-2026-88048) | Tesseract / LSTM dimensions | Upstream patch, stable release unchanged; no uploaded traineddata accepted. OPEN. |
| [2026-88051](https://security-tracker.debian.org/tracker/CVE-2026-88051) | Tesseract / INTTEMP vector size | Upstream patch, stable release unchanged; trusted models only. OPEN. |
| [2026-88052](https://security-tracker.debian.org/tracker/CVE-2026-88052) | Tesseract / UNICHARSET index | Upstream patch, stable release unchanged; trusted models only. OPEN. |
| [2026-88053](https://security-tracker.debian.org/tracker/CVE-2026-88053) | Tesseract / IntTemplates counts | Upstream patch, stable release unchanged; trusted models only. OPEN. |
| [2026-88806](https://security-tracker.debian.org/tracker/CVE-2026-88806) | X11 / malicious X server mapping | Upstream 1.8.14; headless runtime, no DISPLAY/socket. Dependency still present. OPEN. |
| [2026-88807](https://lists.debian.org/debian-x/2026/09/msg00076.html) | Xrender / RenderQueryPictFormats heap | Tracker timed out; Debian security bug identifies fixed 0.9.13. Installed 0.9.12; no X server connection configured. OPEN. |
| [2026-8927](https://curl.se/docs/CVE-2026-8927.html) | curl / proxy Digest state | Upstream fix exists, stable unchanged; video subprocess has clean environment, no app dynamic curl proxy pools. Not exhaustive native proof. OPEN. |
| [2026-93990](https://security-tracker.debian.org/tracker/CVE-2026-93990) | Expat / UTF16 alignment | Fixed upstream 2.8.5, actual OS and Python regression **4/0/0 each image**, Exit0. Raw scanner retained OPEN. |
| [2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538) | Perl / Archive::Tar RAM exhaustion | Upstream Archive::Tar 3.10; application does not use Perl archives. Perl-base package still flagged, no blanket package waiver. OPEN. |
| [2026-58049](https://access.redhat.com/security/cve/cve-2026-58049) | FFmpeg / RASC decoder | Primary CNA confirms crafted stream heap write. Installed custom stable source needs fix-content proof; allowed containers may wrap codecs. OPEN. |
| [2026-64830](https://security-tracker.debian.org/tracker/CVE-2026-64830) | FFmpeg / VobSub demux | Upstream 9.0.2; no verified stable 7.1 backport. Input format whitelist excludes standalone VobSub; OPEN. |
| [2026-64832](https://security-tracker.debian.org/tracker/CVE-2026-64832) | FFmpeg / NVDEC | Upstream 9.0.2; actual binary has no hardware acceleration methods. Raw finding remains OPEN. |
| [2026-64833](https://security-tracker.debian.org/tracker/CVE-2026-64833) | FFmpeg / SPDIF-DTS mux | Upstream 9.0.2; output is HLS only, no SPDIF mux use. Compiled code not removed by this assessment. OPEN. |
| [2026-64834](https://security-tracker.debian.org/tracker/CVE-2026-64834) | FFmpeg / RTP-ASF demux | Upstream 9.0.2; no network inputs, file format whitelist. OPEN. |
| [2026-64835](https://security-tracker.debian.org/tracker/CVE-2026-64835) | FFmpeg / ADX-AAX decoder | Upstream 9.0.2; AAX format excluded, embedded ADX decoder scope not fully excluded. OPEN. |
| [2026-66036](https://security-tracker.debian.org/tracker/CVE-2026-66036) | FFmpeg / hqdn3d reinit disabled | Upstream 9.0.2; only scale/setsar filters, no hqdn3d or reinit_filter=0. OPEN. |
| [2026-66039](https://security-tracker.debian.org/tracker/CVE-2026-66039) | FFmpeg / MACE6-CAF | Upstream 9.0.2; CAF excluded, codec reachability inside allowed containers unproven. OPEN. |
| [2026-66040](https://security-tracker.debian.org/tracker/CVE-2026-66040) | FFmpeg / PNG-APNG encoder EXIF | Upstream 9.0.2; H264/AAC outputs, metadata discarded. OPEN. |
| [2026-66041](https://security-tracker.debian.org/tracker/CVE-2026-66041) | FFmpeg / QR-QUIRC subtitle filter | Upstream 9.0.2; no autodetected external QUIRC library, subtitles/filter not selected. OPEN. |
| [2026-70628](https://security-tracker.debian.org/tracker/CVE-2026-70628) | FFmpeg / DVB subtitle-WTV | Upstream 9.0.2; WTV excluded, subtitles disabled in output, probe parsing still needs scope verification. OPEN. |
| [2026-70632](https://security-tracker.debian.org/tracker/CVE-2026-70632) | FFmpeg / CFHD decoder | Upstream 9.0.2; AVI excluded, **MOV may carry CFHD**, no unreachability claim. OPEN. |
| [2026-75142](https://security-tracker.debian.org/tracker/CVE-2026-75142) | FFmpeg / MPEG-PS mux counts | Upstream 9.0.2; HLS output maps bounded video/audio, no PS output. OPEN. |
| [2026-75143](https://security-tracker.debian.org/tracker/CVE-2026-75143) | FFmpeg / RIST async read | Upstream 9.0.2; actual binary no RIST/network input protocol. OPEN. |
| [2026-75144](https://security-tracker.debian.org/tracker/CVE-2026-75144) | FFmpeg / VC2-Dirac RTP write | Upstream 9.0.2; no RTP output selected, fixed HLS path. OPEN. |
| [2026-75146](https://security-tracker.debian.org/tracker/CVE-2026-75146) | FFmpeg / live DASH demux | Upstream 9.0.2; no DASH/network input allowed. OPEN. |
| [2026-8461](https://security-tracker.debian.org/tracker/CVE-2026-8461) | FFmpeg / MagicYUV | Debian fixed 7:7.1.5-0+deb13u1; tracker names upstream n7.1.5 commit15882781. Fresh pinned-source reverse check below passes; runtime reports genuine7.1.5. Raw scanner remains OPEN; source-fix evidence is not a binary exploit test. |

Historical Scout GCC/zlib findings in `QA_FIXES_2026-10-05.md` are retained as
historical open assessments. Their absence in a different scanner is not proof
that upstream GCC/libstdc++ or zlib risks were fixed. Their old package version
notes require a new compatible backport/reachability sign-off, not suppression.

## Current Docker Scout repeat after user sign-in

`run-video.ps1 -Stage Scan -ApproveScout`, completed14:32:11Z:
wrapper Exit1; each scanner **Exit2** because findings exist. API6High/0Critical,
encoder8High/0Critical,4/5 affected source packages respectively. Reports:
`.qa/audit2/scout-video-{api,video-worker}-20261006-142816.sarif` and
`video-commands-Scan-20261006-142816.json`. Same actual image IDs as the table
above. A Windows temporary-archive cleanup lock warning occurred after indexing;
both complete SARIF reports were written. No deletion workaround was attempted.

Scout's8distinctCVEs and Trivy's52 have **57 distinct IDs in their union**.
Different vulnerability feeds/package matching produce different counts;
neither scanner's missing finding proves it fixed or safe. The five Scout-only
IDs are102010,30997,38347,95619,85091. The table below reviews every Scout finding;
the earlier table retains all52 Trivy findings. Debian tracker pages for all
eight Scout findings were reopened on6October, not copied as current results
from the5October report.

| Current CVE / package / image | Fix availability and actual application-path assessment | Status |
|---|---|---|
| [2026-102010](https://security-tracker.debian.org/tracker/CVE-2026-102010); gcc-14 source14.2.0-19/libstdc++; both | PBDS binary-heap erase_if use-after-free. No fixed trixie package; upstream patch exists. Python app does not directly call PBDS, but absence from every native OCR/PDF consumer is not proven. Bounded non-root execution only limits impact. | OPEN, no blanket unreachable claim. |
| [2026-95619](https://security-tracker.debian.org/tracker/CVE-2026-95619); same gcc source; both | Aligned-new size overflow. No fixed trixie package; upstream patch exists. Fresh `scripts/qa/native-aligned-new.py` on each exact image: **10/0/0, Exit0**,9 overflow inputs plus1 valid allocation,128MiB/no-network temporary container. This tests only Linux64-bit nothrow aligned-new ABI, not PBDS/every C++ call/platform. | OPEN raw finding; narrow negative-path evidence, not a waiver. |
| [2026-86140](https://security-tracker.debian.org/tracker/CVE-2026-86140); libxml2 `2.12.7+dfsg+really2.9.14-2.1+deb13u3`; both | xmlSnprintfElements stack overflow; upstream2.15.4 fixed, current trixie still affected. Not a verified drop-in ABI replacement for native consumers. DOCX uses separate lxml, but that does not exclude OS-native parser reachability. | OPEN; reviewed compatible backport still needed. |
| [2026-74860](https://security-tracker.debian.org/tracker/CVE-2026-74860); same libxml2; both | SAX attributeDecl double-free in specific Python libxml2 bindings. Upstream2.15.3 fix, no fixed trixie candidate. Runtime inventory shows that binding absent; lxml is a separate binding. This narrows the described path, not all XML consumer risks. | OPEN raw OS finding; partial reachability evidence. |
| [2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091); zlib source `1:1.3.dfsg+really1.3.1-1`; both | Nonblocking gzwrite/gzprintf stale-buffer path; tracker marks trixie affected while documented introduction is1.3.1.2. Application compression exists, but no direct gzprintf/gzvprintf calls identified. Upstream fix exists; packaged-source reconciliation is not completed. | OPEN, version-range dispute not suppressed. |
| [2026-93990](https://security-tracker.debian.org/tracker/CVE-2026-93990); Expat `2.8.5-0chemistry1`; both | Authentic upstream2.8.5 fixes malformed UTF16. Actual OS-native regressions **4/0/0 each, Exit0** in the final Backend gate. Scout reports trixie >0/unfixed despite the custom upstream package; actual corrected binary evidence does not erase the raw alert. | Code fix evidenced; raw scanner/sign-off OPEN. |
| [2026-30997](https://security-tracker.debian.org/tracker/CVE-2026-30997); FFmpeg `7:7.1.5-0chemistry1`; encoder | AV1 read_global_param; upstream7.1.4 commit9abe92e3 and Debian7:7.1.5-0+deb13u1 fixed. Signed upstream7.1.5 source/build provenance retained; historical reverse-patch evidence belongs to5October, not a new exploit test. Native video input reaches decoder. | Raw scanner OPEN; custom revision is not renamed to pass. |
| [2026-38347](https://security-tracker.debian.org/tracker/CVE-2026-38347); same FFmpeg; encoder | swscale alpha blending; upstream7.1.5 commitbb88e295 and Debian7:7.1.5-0+deb13u1 fixed. Scaling is actually used; authentic build provenance/historical reverse-patch evidence is narrower than testing every crafted exploit. | Raw scanner OPEN; no severity override. |

Fresh aligned-new artifacts: `.qa/audit2/native-aligned-{api,video-worker}-20261006-final.json`.

## Required next security closure

1. Track signed trixie-security backports; rebuild both actual image payloads.
2. Verify custom FFmpeg per-fix content (especially RASC/MagicYUV), not package
   revision ordering. Consider a reviewed stable-source update, never sid-only
   substitution to make the report green.
3. Validate native exploit/negative fixtures in isolated bounded workers where
   applicable; preserve regression and real upload/seek behavior.
4. Repeat raw scans and backend/PostgreSQL/browser gates after changes. Retain
   this report and failures; no production-ready claim while gate is OPEN.
