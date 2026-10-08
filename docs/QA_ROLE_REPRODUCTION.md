# Re-running teacher/student closure gates

## Current source/evidence and native-dependency tools (8 October)

Use PowerShell7 from the repository root. Keep `.qa` ignored; manifests,
screenshots, traces, credentials and synthetic backups can contain private
runtime data and must not be committed. Complete the fresh-checkout preparation
steps below before using live tools. Do not overlap Browser, Integration,
Recovery, Load or the storage drill on the same QA project.

```powershell
# After the intended code edits, before a complete gate:
./scripts/qa/snapshot-source.ps1 -Mode Snapshot -Manifest .qa/audit2/current-source.json
./scripts/qa/run-video.ps1 -Project chemistryaudit2 -Stage Browser
# Even after a failed gate, verify the SAME preceding manifest:
./scripts/qa/snapshot-source.ps1 -Mode Verify -Manifest .qa/audit2/current-source.json
./scripts/qa/verify-runtime-source.ps1

# Independent raw scanners, after native rebuild/runtime tests:
./scripts/qa/run-trivy.ps1
# Only after the human approves sharing image/SBOM package metadata:
./scripts/qa/run-video.ps1 -Project chemistryaudit2 -Stage Scan -ApproveScout
./scripts/qa/check-zlib-source.ps1 -Project chemistryaudit2

# Exact immutable images only; retain the old image BEFORE a native rebuild:
./scripts/qa/compare-extract-images.ps1 -BaselineImage sha256:<old-id> -CandidateImage sha256:<tested-new-id>
```

Source manifests exclude generated load CSV/account files, secrets, private
runtime storage and unrelated projects. A zero source-check exit does not
replace application tests. Runtime verification compares123 backend source
files per image (as of8October) and every fresh-built/served web asset/config;
counts may increase with source changes. It fails on missing/extra/mismatched
code or old served web images. An interrupted gate is unfinished, not passed.

Discovery/publication fixtures wait for real login200 and an authenticated
bootstrap with the SAME server ID/email within the client's15s transport
budget, then retain5s UI assertions. No401/429 login replay is synthesized.
No-photo cases forward actual origin responses under controlled5.5s delays
to prove this synchronization (not a mocked successful identity). All three
still verify no photo inputs/requests/URLs, ignored stale cached avatar data,
authenticated legacy photo routes410, logout/re-login and delayed identity
mutation guards. They never upload a personal image. Pending upload-response
rejections are captured immediately and thrown when awaited; an earlier
failed branch cannot create an unhandled rejection in the next QA worker.
Docker teacher provisioning uses one asynchronous call, with the unchanged
20s control-plane deadline and no automatic retries.

On a constrained host, do not run native builds/scans, fault drills or load
beside Browser. Stop other platform projects ONLY with explicit permission,
retain their exact original running-container IDs privately, and never delete
their data to obtain a passing suite. Better behavior after freeing resources
is not a claim of representative deployment capacity or of a repaired
Docker/host dependency fault. Retain the original failed JUnit evidence.

Trivy is pinned and bounded to1CPU/768MiB/no additional capabilities; it
retains both actual-image SARIFs and nonzero security exits with no suppression.
The zlib review verifies installed Debian source metadata, signed DSC against
the FULL allowed fingerprints, original/quilt SHA and the reviewed source path;
it is source evidence, not a scanner waiver or a claimed official Debian fix.

The Extract parity tool runs the SAME seven strict fixtures/source/comparator
and trusted ara/eng/osd models in each restricted offline image, compares raw
pages and parsed outputs, and writes inventories/results/commands privately.
Exit2 is a parity regression; Exit1 retains existing accuracy failures. A
missing baseline image is a setup failure: do not substitute a mutable tag or
claim parity. User-deferred Biology accuracy stays a recorded failure, not a
skipped or newly passing test. The native XML build JSON separately records
unittest executed methods and skip EVENTS; skipped subtests/classes are not
all independent skipped methods, so its legacy derived794 is not an exact
unique-method passed count.

The classic `production-storage-drill.ps1` refuses a project with a video-worker
before any service mutation. Use `video-storage-drill.ps1` for this pipeline:
ALL ingress/API/Celery/encoder writers freeze, the actual tested image backs up
data, fresh stores receive the restore, every object SHA/metadata and database
row is compared, and actual restored API/video browser checks run before
returning to the original stores. No old MinIO volume is used by SeaweedFS.

The old `infra/scripts/backup.sh` and `restore.sh` refuse all invocations with
Exit64. They do not create/prune archives, read credentials or run Docker, even
with an old dump argument and confirmation. `./scripts/qa/check-retired-storage.ps1`
checks these guards in an offline128MiB non-root read-only container, with no
engine socket or application data/secrets. Four passing refusal/syntax tests
do NOT replace the actual video-storage backup/restore drill.

## Lost upload reservation and byte-boundary regression (7 October)

Build the current runtime and QA images first. The unit gate includes
`test_lease_loss_responses.py` (seven ASGI cancellation/renewal cases) and
`test_material_overflow_validation.py` (known/unknown size overflow). The full
Integration stage includes `test_upload_lease_loss.py`: a real paused multipart
request, read-only observation of the Redis reservation, an allowlisted QA
Redis outage,503 with Retry-After2, no LessonAsset and readiness recovery before
logout. It must never stop a different project or erase lease/rate counters.

The live byte-boundary cases transfer actual1GiB materials and5GiB videos; they
are not small-file substitutes. Their size padding proves byte limits, not
realistic audience capacity. Run sequentially, without browser/load/restore
interference, and retain every failed JUnit. QA runner and backup client have
1GiB memory caps to bound their file cache; this does not increase API memory,
change upload limits, or prove that memory caused an earlier renewal failure.

```powershell
./scripts/qa/run-video.ps1 -Stage Build
./scripts/qa/run-video.ps1 -Stage Backend
./scripts/qa/run-video.ps1 -Stage Integration
```

Intentional loss of a distributed reservation before response headers is a
retryable503, not500. Client cancellation remains cancellation; a started
stream is stopped without sending a second status or a false successful end.
Re-run source parity and the final browser/storage gates after runtime edits.

## Uniform reset queue and playback regressions (7 October)

Run `run-video.ps1 -Stage Build` before final Backend/Integration/Browser gates.
The migration head is f3e5a7c9b1d3. The public reset handler queues an encrypted
identity; deterministic SMTP tests must call process_reset_requests BEFORE
deliver_reset_mail. Do not weaken the same-body, single-use, fragment-link,
SMTP-TLS or ciphertext-erasure assertions. Real-PG concurrency uses a private
UUID schema and never truncates runtime data. The final unit test retains both
known and unknown requests and checks both complete, only one sends mail.

Focused commands from a rebuilt QA test image:

```text
python -m pytest tests/test_reset_request_admission.py tests/test_session_security.py -q
python -m pytest tests/integration/test_session_maintenance_pg.py -q
npm run test -- src/components/VideoLessonPage.test.tsx src/components/useHlsTransport.test.tsx
```

Two actual shared-cookie tabs in manual-grading exercise blob download,
multipart preflight, JSON/bootstrap and SSE under refresh503; the HLS journey
also tests token-renewal failure and SSE recovery in a second tab. No live
counter deletion, header-spoofed client identity or automatic file replay.
Browser result must be recorded after these new cases actually execute.

`scripts/qa/ocr-render-candidate.py` is QA-only, not imported by runtime. Mount
it read-only at /qa-tools/ocr-render-candidate.py in a fresh offline immutable
API container; use1CPU/1GiB and64MiB storage tmpfs owned10001:10001. Supply
`--scale 1.75 --output /qa/candidate.json`; optional `--retain-color` or
`--language ara|eng+ara` experiments. It retains all seven original fixtures,
unchanged strict comparator and complete differences. Every current candidate
failed6/1/0 (Exit1) and was rejected. A loop wrapper Exit0 does NOT change each
candidate's Exit1. No source-word dictionaries or production parser rewrite.

Use a disposable local Docker project, never a production database. Commands
below are run from the repository root in PowerShell7 (`pwsh`). They need Docker Desktop
and Node/npm, plus a Python runtime with `pypdf` for inspecting downloaded PDFs.
Set `$qaPython` to that Python executable. Do not put credentials in this file.

1. Run `./scripts/qa/prepare-production.ps1 -Project chemistryaudit2` on a fresh
   checkout. This writes random secrets and a self-signed local certificate into
   ignored `.qa/audit2/`. Review the generated local environment before use.
2. Build and start the production template plus isolated QA/video overlays:
   `./scripts/qa/run-video.ps1 -Stage Build`.
3. Run `./scripts/qa/prepare-media.ps1 -Project chemistryaudit2`, then
   `./scripts/qa/prepare-test-data.ps1 -Project chemistryaudit2` to generate
   the large synthetic media and seed disposable teacher/student accounts and
   the matching storage checkpoint. Also see `docs/PRODUCTION_DOCKER_RUNBOOK.md`. The
   storage checkpoint is needed for the live fault/restore tests; it contains
   synthetic IDs and private file hashes, not user content to publish.
4. Run `./scripts/qa/run-video.ps1 -Stage Tests` for backend unit/security,
   missing-multipart recovery and publication/playback tests.
   `-Stage Backend` runs the same backend/native/storage checks without the
   overlapping focused browser subset when ALL Browser will be run afterwards.
5. Run `./scripts/qa/run-video.ps1 -Stage Integration` for ALL live PostgreSQL,
   concurrency, storage transactions, SSE, byte-boundaries and fault cases.
6. Set `$env:QA_PYTHON=$qaPython` and run
   `./scripts/qa/run-video.ps1 -Stage Browser` for lint, build, frontend unit,
   ALL Playwright journeys, npm audit and diff check. No expected-failure masks.
7. Run `./scripts/qa/run-role-discovery.ps1 -Python $qaPython` for the dedicated
   discovery suite and strict Extract comparison against the independent
   QA-only source transcription. Its exit is nonzero if EITHER gate fails.
8. Run `./scripts/qa/verify-runtime-source.ps1` after the last source change and
   rebuild. This checks API/video-worker application hashes, plus web image
   identity, served assets and nginx configuration against the current build.
   The Browser wrapper builds with `VITE_API_URL=/api/v1`, matching Docker.
   For a manual build, set `$env:VITE_API_URL='/api/v1'` first; a developer's
   `.env.local` URL produces different bundles and must not be treated as a
   source mismatch silently. Recreate an old web container, then retest it.
9. Run `./scripts/qa/run-video.ps1 -Stage Assets`, then `-Stage Recovery`, then
   `-Stage Load`, and `./scripts/qa/video-storage-drill.ps1` sequentially. The
   restore drill freezes QA writers, preserves original volumes, restores to
   fresh volumes and finally returns the original configuration.
   `./scripts/qa/check-backup-permissions.ps1` independently proves non-root
   backup writes and rejects symlink/file targets without changing their data.
   The full drill runs the production permission initializer explicitly because
   its backup commands use `--no-deps`; neither the API nor S3 backup is root.
10. With explicit approval to share image package/SBOM metadata, run
    `./scripts/qa/run-video.ps1 -Stage Scan -ApproveScout`. Nonzero is a real
    open security gate, not a reason to suppress CVEs.
    The scan resolves the actual Compose container image ID and verifies its
    project/service ownership. It does not assume a newly tagged build is the
    running payload (BuildKit attestations can change the tag manifest).

NEVER overlap Browser, Integration, Recovery, Load or restore. Their deliberate
service failures and shared synthetic account counters would invalidate results.
For the final handoff, repeat steps 7 and 8 after the storage drill returns the
original configuration: final Extract/discovery/source proof must not be an
earlier run from before a rebuild, recovery or restore exercise.
The browser harness waits for real shared-IP and user rate windows on
allowlisted QA; it never erases those counters or relaxes production limits.

## New regression evidence

- `discovery.spec.ts`: OCR-source acknowledgement for BOTH quiz and assignment
  publication (including reload and invalidation after a text edit), assignment
  options/score/start, atomic failure and lost
  response, audience isolation, calendar outage/partial save retry, no-personal-
  photo controls/requests/endpoints for both roles (including stale cached URLs
  and delayed server identity hydration), course selection and persisted binding, real profile data,
  printable Latin questions. Run the entire file, not only a passing selection.
- `test_role_discovery_regressions.py`: direct API/DB checks of those contracts.
  The old avatar upload contract was superseded by the user's7October no-photo
  decision; its historical failed B8 browser case remains in the ledger.
- `test_video_refresh_slots.py`: actual HTTPS/PostgreSQL/Redis rotation and
  eight concurrent token requests reuse one stable family slot, while a third
  device remains429, old/copied links remain403 and logout frees only its family.
  This admission test does not substitute real encoded-media browser playback.
- `test_extract_source_preservation.py`: preserve bilingual words and source
  spellings, render delta without inventing an H, keep scientific glyphs intact.
- `test_native_expat_security.py` and `python -m scripts.verify_native_expat`:
  load the ACTUAL OS `libexpat.so.1`, not just Python's bundled Expat. Verify
  malformed/valid UTF-16 in both byte orders. Stage Tests runs this on both API
  and encoder. The native source builder additionally runs upstream make check.
- `test_multipart_cleanup.py` and the real-storage case in
  `tests/integration/test_storage_transactions.py`: an incomplete multipart
  allocation has no HEAD object; cleanup must still abort its EXACT retired key,
  leave a prefix neighbour alone, and retry permission/storage failures.
- `requestStorm.test.ts`: maximum four concurrent course-content/assessment
  reads, no blockage of identity/playback mutations, no cross-account in-flight
  sharing, late cache/refresh/file response rejected after an account switch.
- `hydration.spec.ts`: actual catalog requests and PostgreSQL responses,
  measured request concurrency plus errors and a usable identity endpoint.
  Seeds the synthetic student catalog to at least 20 enrollments when needed;
  old large QA catalogs are not erased. Do not run against a user's project.
- `test_audit_concurrency.py`: independent TCP requests released by a barrier
  and actual PostgreSQL row counts (including publication and submission).
- `test_assignment_pdf_fonts.py`: glyph coverage and science text. Also run
  `python -m scripts.qa_assignment_pdf` in QA (writes `/qa/role-pdf-fonts.pdf`),
  render with `pdftoppm`, and inspect the rendered page visually.
- `qa_extract_fidelity.py`: strict stem/type/ordered options/blank/formula
  comparison. A correct number of questions alone is NOT a pass.
- `qa_ocr_candidate.py`, `qa_ocr_lines.py`, `qa_ocr_ensemble.py`,
  `qa_ocr_words.py`, `qa_ocr_native_crops.py`: rejected candidate experiments. They override OCR ONLY
  inside the QA process; they are not production fixes. The reference is read
  by the comparator, never used as runtime OCR input or a correction dictionary.

`scripts/qa/ocr-render-scale.py` is another QA-only experiment. Run it with
`PYTHONPATH=/srv` in qa-tests, mount the file read-only at
`/qa-tools/ocr-render-scale.py`, and pass `--scale 2 --output /qa/ocr-raster.json`.
It retains the runtime pixel/time budgets, compares ALL blind files, and uses a
separate cache version. Higher DPI is not automatically better: the 144-DPI
candidate lost two biology questions and was rejected. Do not promote this
experiment or tune the comparator to accept it.

`scripts/qa/ocr-native-page.py` is a separate rejected QA-only experiment:
mount it read-only at `/qa-tools/ocr-native-page.py`, run with
`PYTHONPATH=/srv` and `--output /qa/ocr-native-page.json`. It tries an embedded
full-page image only when its bounds cover the PDF page, avoiding raster
resampling; otherwise it uses the ordinary parser. All blind files remain in
the comparison. The measured biology PDF lost two questions and matched only
3/10, so this was NOT installed as a production OCR path.

`scripts/qa/native-aligned-new.py` can be mounted read-only into each isolated
image and run with Python (network not needed). It checks the actual Linux
64-bit libstdc++ non-throwing aligned-new ABI: nine upstream overflow cases and
one valid aligned allocation. This narrows CVE-2026-95619 reachability on this
platform; it does not prove PBDS or every C++ path safe, repair the package, or
waive the raw High scanner finding.

Results are in ignored `.qa/audit2/`: JUnit XML, command exit JSON, SARIF, hash
manifests and traces. Traces/cookies/logs/secrets must NOT be uploaded as-is.
Publish a sanitized report that separates each failing iteration from the last
successful one and identifies the tested images and uncommitted source state.
Local TLS, load and SMTP do not verify an external server, certificate, CDN,
DRM vendor or 1000 active users.

## Rejected local OCR experiment (QA only)

After all load/fault/restore measurements, optionally run
`./scripts/qa/run-ocr-paddle.ps1 -Mode lines` and then `-Mode words`.
The disposable `infra/qa/Dockerfile.ocr-candidate` supplies OpenCV's libGL
dependency; an initial run without it failed at import, not at a fidelity
assertion. Neither this image nor Paddle is used by the production services.

The setup pins PaddlePaddle3.2.0, PaddleOCR3.3.2 and PaddleX3.3.13. It downloads
the publisher's Arabic PP-OCRv5 model and verifies archive SHA256
`a25c1f96cd0cda485b942851b5afb4a95bc4041a56c295bb4439190d53ee0a14`.
The actual recognition container has `--network none`, one CPU,2GiB memory,
128PID limit, no compose environment, credentials, DB network or Docker socket.
It retains the20-second OCR/5000-token budgets. The comparator's source
transcription is not supplied to the recognition engines. Files/models/venv
are ignored under `.qa/audit2/paddle-candidate/`; do not commit them.

5October results: lines PDF4/10, PNG3/5 matching questions; words PDF7/10,
PNG4/5. Both return Exit1,0passed/2failed/0skipped files. Both were rejected;
the tested application's better baseline remains PDF7/10 and PNG5/5. A high
model score alone is NOT evidence of source fidelity. See the closure report
for remaining diffs and do not activate this candidate in production.

## Official tessdata_best candidate (QA only, 6 October)

The publisher model was fetched from immutable commit
`e12c65a915945e4c28e237a9b52bc4a8f39a0cec` of
[tesseract-ocr/tessdata_best](https://github.com/tesseract-ocr/tessdata_best).
Arabic model SHA256:
`ab9d157d8e38ca00e7e39c7d5363a5239e053f5b0dbdb3167dde9d8124335896`.
The existing image English model was copied, not upgraded: SHA256
`7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.
Weights stay ignored/private, never committed or silently installed.

Mount the current `apps/api/scripts/qa_tessdata_fidelity.py` read-only into
the isolated QA image and the directory read-only at `/models`; run without
network,1.5CPU/1GiB memory and a writable ignored artifact directory:

```sh
python -m scripts.qa_tessdata_fidelity --tessdata-dir /models \
  --ara-sha256 ab9d157d8e38ca00e7e39c7d5363a5239e053f5b0dbdb3167dde9d8124335896 \
  --eng-sha256 7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2 \
  --output /qa/tessdata-best-fidelity.json
```

This verifies model bytes and uses a separate model-specific parser cache key.
It does not alter production parser/models or the strict reference. Poppler
rendered both biology pages at108dpi for actual visual inspection. This full
candidate FAILED:5/2/0 files, PDF9questions/4matching,CER0.138263666;
PNG4questions/3matching,CER0.123123123. It was rejected, not made default.

Optional localized comparison: mount the current `qa_ocr_words.py` read-only;
run `python -m scripts.qa_ocr_words --candidate-tessdata-dir /models
--word-psm 7 --output /qa/best-words-7.json` (or8). This keeps ordinary page
recognition and only tries low-confidence Arabic word crops, protecting numbers
and scientific tokens. PSM7 also FAILED:0/2/0 files, PDF10/7matching,
CER0.014409222; PNG5/4matching,CER0.010362694. Confidence cannot override the
fidelity comparator. Do not import either QA-only candidate into request handlers.

PSM8 also returned Exit1,0/2/0 files: PDF10questions/7matching,
CER0.012968300; PNG5questions/4matching,CER0.010362694. Both word modes were
rejected, despite isolated improvements. The current production baseline is
still stronger; review warnings remain mandatory.

## Pinned FFmpeg fix-content check (not a scanner waiver)

For `scripts/qa/check-clean.ps1`, first build the working tree's web project
with `VITE_API_URL=/api/v1` (the Browser gate does this), and review/stage the
intended source index. The clean gate now requires every generated web asset
to have the same SHA-256 as that fresh build. CSS source discovery is explicit,
so an ignored QA export must not accidentally scan dependency/tool files.

Download only the official7.1.5 release archive from
`https://ffmpeg.org/releases/ffmpeg-7.1.5.tar.xz` and official patch from
`https://github.com/FFmpeg/FFmpeg/commit/15882781ac5267a653e4e55f5fa656ba9db688fd.patch`
into an ignored private QA directory. Then:

```powershell
python scripts/qa/verify-ffmpeg-magicyuv.py --archive .qa/audit2/ffmpeg-7.1.5.tar.xz --patch .qa/audit2/native-magicyuv-20261006/15882781.patch
```

The tool validates both exact SHA256 pins before a check-only reverse patch
against one regular source member in a temporary directory. Python and Git are
required; runtime images are not edited. Exit0/3 checks passed on6October.
This proves source fix-content, not exploitation resistance in every binary.
Keep the complete raw scanner results and native release gate open separately.

## Current stable-package candidates without altering runtime

Run `./scripts/qa/check-stable-packages.ps1 -Image sha256:<actual-runtime-id>`
for each tested API/encoder identity. This disposable, resource-bounded apt
probe receives no application environment, volumes, secrets or Docker socket.
It prints configured Debian sources, freshly fetches their signed indexes,
reports installed/candidate versions and SIMULATES upgrade only. Exit0 is
successful assessment, not a clean vulnerability gate. Private stdout/command
provenance is under `.qa/audit2/stable-packages-*`; keep raw scanner findings.

## Native PDF-image OCR experiment (rejected, 7 October)

`scripts/qa/ocr-native-image.py` uses the existing PyMuPDF APIs documented by
the publisher ([page image geometry](https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_image_rects),
[original image extraction](https://pymupdf.readthedocs.io/en/latest/document.html#Document.extract_image)).
It monkey-patches OCR only inside its disposable QA process; no production
parser, dictionary/model or strict reference change. Mount the tool at
`/qa-tools/candidate.py`, original fixtures read-only at
`/srv/tests/fixtures/blind_inputs`, writable ignored reports at `/qa`, set
`PYTHONPATH=/srv`, then run `python /qa-tools/candidate.py --output
/qa/native-image.json`. Use the immutable API image, `--network none`,1CPU,
1GiB and fresh64MiB tmpfs at `/srv/storage` owned10001:10001. No Compose
environment, database network, credentials or socket is needed.

The7October candidate failed6/1/0 files; biology8questions/3 fully matching
versus baseline10/7, CER0.731958763 versus0.008645533. It is rejected and must
not be imported into handlers. The complete baseline strict repeat separately
returned6/1/0, Exit1; manual source review remains necessary. A single
full-page image filter is not universal annotation/transform layout proof.

## Unchanged authentication budgets and repeated reset timing

The live Integration stage includes `test_shared_auth_budget.py`: one real
Docker client IP, fifteen mixed refresh/logout requests, the sixteenth429,
another credential mutation429, read-only profile not charged to auth, and
recovery after real expiry. It checks the running deployment's15/60 setting.
The route's60/min check does not replace the shared15/min middleware budget.

`test_reset_timing_repeated.py` allocates twelve concurrent clients with
distinct real IPs, five requests each (the real5/300s reset limit), thirty
existing-account/thirty missing-account samples and thirty durable jobs to
the QA mail sink. Raw timings, medians, p95 and a descriptive bootstrap
interval appear in captured JUnit stdout. This is not a universal statistical
side-channel guarantee. Both cases wait for genuine Redis window expiry;
no forged XFF, live counter deletion or rate-limit relaxation. Use the same
allowlisted isolated project and CA required by `run-video.ps1 -Stage Integration`.

## Safe recovery when a disposable fault runner is interrupted

`run-video.ps1 -Stage Integration` takes an exact ten-service baseline with
`runtime-recovery.ps1` and restores initially-running containers in a controller
finally. Image/project/service/name must still match. It starts, never recreates
or resets; a changed/missing identity fails closed. Original failed/interrupted
suite and separate recovery exits remain in the commands JSON. This does not
guarantee recovery after forcibly terminating the controller itself: inspect
health after any interruption and never label an incomplete JUnit as a pass.

```powershell
./scripts/qa/test-runtime-recovery.ps1
# Intentional worker fault; ONLY chemistryaudit2, and cleanup even on failure:
./scripts/qa/test-runtime-recovery-live.ps1
```

The first is mock-only. The second requires a ready isolated audit stack and
checks actual HTTPS200→worker stop→503→same-image worker recovery→200/ready;
no login credentials or real-user writes. Keep its private JSON and exact IDs.

## Native OCR dependency candidates (not runtime upgrades)

`build-ocr-candidate.sh` builds pinned official5.5.3; `build-ocr-minimal-candidate.sh`
rebuilds the existing Debian stable5.5.0-1 source with its Debian help-text patch.
They require `QA_NATIVE_CANDIDATE=true`, a NEW disposable container, read-only
downloaded official archives at `/inputs`, and fresh private output `/candidate`.
Never run either inside API/worker; give no application env, network attachment,
socket or data volume. Bound memory768MiB/CPU1/build threads1. Explicit hashes
and official URLs are in the scripts; source archives/binaries stay ignored.
The minimal build uses these files from the official Debian pool:

- `tesseract_5.5.0.orig.tar.gz`: f2fb34ca035b6d087a42875a35a7a5c4155fa9979c6132365b1e5a28ebc3fc11.
- `tesseract_5.5.0-1.debian.tar.xz`:339c1e99003ed57552296f0ce758650b8c62d5f1222bb22c6c93a519dc90d20d.

After build, run ALL original files against the same immutable API/parser/model
baseline; the tool mounts candidate binary/libs only in a fresh offline process:

```powershell
./scripts/qa/compare-ocr-runtime.ps1 -Image sha256:<actual-baseline-id> -CandidateDirectory .qa/audit2/<candidate>/output
```

Both exact commands/exits, full strict JSON, source SHA and parsed-output/CER
comparison are saved under `.qa/audit2/ocr-runtime-*`. Wrapper1 if either strict
gate fails, even if the replacement is equivalent. No expected reference is
passed to OCR. 7October5.5.3 FAILED5/2/0 versus6/1/0 baseline and was rejected;
its absent native XML/network dependencies do not justify worse source fidelity.
Any adopted runtime dependency change would require actual rebuild, regressions,
final source parity and raw scans, not a count-only/native-options claim.

## Current stable encoder and publication acceptance — 7 October

The native encoder builder pins upstream STABLE FFmpeg9.0.2, its archiveSHA256
and published PGP signing fingerprint. Debian13 remains stable; do not install
forky/sid merely to match a scanner's package revision. The build explicitly
disables the legacy RASC decoder as a mitigation for58049, keeps common codecs,
and executes real x264/AAC/HLS encoding/decoding before packaging. Native
source/signature/decoder inventory is root-owned under
`/usr/local/share/chemistry-native/ffmpeg/`, outside slim doc exclusions.

After a real Build, run:

```powershell
./scripts/qa/verify-native-video.ps1 -Project chemistryaudit2
./scripts/qa/run-video.ps1 -Stage Backend
./scripts/qa/run-video.ps1 -Stage Integration
./scripts/qa/run-video.ps1 -Stage Browser
./scripts/qa/run-video.ps1 -Stage Assets
./scripts/qa/run-video.ps1 -Stage Recovery
./scripts/qa/run-video.ps1 -Stage Load
./scripts/qa/video-storage-drill.ps1
./scripts/qa/verify-runtime-source.ps1
```

The six native cases check ACTUAL ffmpeg/ffprobe version, pinned signed source,
non-writable provenance, removed RASC, no network/hardware paths, common
decoder/encoder registration and HLS availability. JSON records actual runtime
image identity and Passed/Failed/Skipped. These are NOT six crafted-CVE exploit
tests or scanner waivers. Backend and CI invoke the same native proof. Always
repeat both raw scanners after an adopted native change and retain nonzero
alerts; do not rename a package to a fictional fixed Debian revision.

`QuizPublishConfirmation` owns only display/native dialog semantics; the existing
publication/draft/history/notification lifecycle stays in `QuizGeneratorView`.
Its eleven component cases do not prove native browser inertness/keyboard focus.
The real `publication.spec.ts` dark390px mobile scenario separately checks
normal/error/loading axe states, preserved draft and zero backend publication
on injected400, locked cancel/Escape while a real retry is paused, then actual
PostgreSQL publication once released. Keep the resulting screenshot/trace and
full collection counts, not merely a focused success.

Browser and clean-index frontend runners now explicitly use one Vitest worker
with per-file isolation and default+JUnit reporters. This prevents concurrent
jsdom allocation on a constrained host, without dropping cases/assertions or
changing real auth/refresh/upload limits. Unit artifacts are
`frontend-video-<run-id>.xml` and `clean-results-<run-id>/frontend.xml`.

The user deferred BIOLOGY Extract improvements on7October. Preserve the strict
6/1/0 original-fixture result and unchanged references; this is NOT a passing
OCR gate, nor permission to remove/exclude that test from the strict CI check.

## Bounded mixed-load stop policy

`./scripts/qa/run-video.ps1 -Stage Load` runs all planned1/5/10×180s stages
sequentially and saves unique `load-<UTC>.json` artifacts. The safety controller
in `scripts/qa_load_policy.py` has ten isolated unit cases; the actual load run
must separately prove real video/PDF transfers and resource samples.
New work stops on a rolling100-request error rate>1%, interactive p95>2000ms,
any whole-file upload>15000ms, or three consecutive samples at≥90% actual
cgroupCPU/RAM,≥80% PostgreSQL max_connections, or≥50 queued/processing videos.
Pending requests retain bounded transport timeouts, and no next stage starts.
Raw actual limits, samples/queue depth, stop reason, planned/completed stages,
throughput and per-operation p95/p99 remain in the report. No429 automatic
retry, no route/user counter erasure and no production-limit relaxation.
Any error or early stop is Exit1 even if the stop threshold was not crossed.
These local safety bounds are not application-pool utilization or proof of
external25–500×10min/1000/5000-user capacity.

## Isolated Tesseract security-backport candidate (not adopted)

`prepare-ocr-backport.ps1` downloads the signed Debian5.5.0-1 source and six
exact official upstream commit patches into a NEW private ignored directory.
Every SHA is pinned in source. The native script verifies the DSC against the
Debian maintainer keyring; GitHub patches have HTTPS/checksum provenance, not
an independently verified PGP signature. `Prepare` checks applicability only:

```powershell
./scripts/qa/prepare-ocr-backport.ps1 -Mode Prepare
# Run serially after Browser/fault/load/restore suites on a constrained host:
./scripts/qa/prepare-ocr-backport.ps1 -Mode Build
# Use the actual immutable API identity and the returned output directory:
./scripts/qa/compare-ocr-runtime.ps1 -Image sha256:<actual-api-id> -CandidateDirectory <candidate>/output
```

The third patch needs three reviewed5.5.0 context adaptations: the original
matcher flag name, the original elapsed-time argument in two declaration
contexts, and removal of a deletion for a constructor loop absent in5.5.0.
All added security guards remain upstream's. Both the original and derived
patch bytes are SHA-pinned; `git apply --recount` does not enable fuzzy matching.
The adaptation diff is retained. Later-version build-system hunks are not used.
The old5.5.0 additional `AmbigClassifier` pointer-taking call also requires the
reviewed SHA-pinned `apps/api/scripts/native/tesseract/stable-callsite.diff`
(`Class.data()`). This is
not a security-check removal. Build must compile successfully before any
candidate security/fidelity success is recorded; the original Exit2 failure
is retained with its exact error and source.
The original fifteen upstream security test bodies plus eleven additional
overflow/valid-control cases compile against the candidate's actual library.
Their26-case result is not presumed until the binary is built and executed.

Containers receive no app network, secrets, data volumes or Docker socket.
Prepare/build failures remain retained; no binary is installed into the app.
Adoption additionally requires original7-input unchanged-comparator parity,
unchanged trusted models, actual API/encoder rebuild and all final raw scans
and runtime gates. The known strict biology failure is still a failure, even
if candidate output is byte-for-byte identical to baseline. This tool is not
a scanner waiver or a fictional upgrade of Debian's package version.

The shared manifest, patch applier and actual-library test runner are now in
`apps/api/scripts/native/tesseract/`, within the normal API build context.
Candidate tools mount that directory read-only too, so QA/application build
cannot silently use different patch lists or test bodies. Original upstream
patches are downloaded from the six official pinned commits and checked
before exact-context application. The shared runner includes the real5.5.0
`src/training/unicharset` header directory; a compilation failure means
ZERO collected native cases, not26 failed cases.

If a retained QA-only compiled source/library needs a test-runner repeat,
`test-ocr-backport-candidate.ps1 -CompiledImage sha256:<immutable-qa-cache-id>
-SourceDirectory /tmp/chemistry-ocr-backport.<id>/tesseract-5.5.0
-RuntimeDirectory <retained-private-candidate>/output` creates a NEW private
output, copies only the candidate runtime/nonsecret provenance, and runs with
no network/app volumes/secrets/socket,768MiB/1CPU/no added capabilities.
The cache must carry `chemistry.qa.candidate=true`; this is not an app image.
Default clean reproduction remains the full Prepare/Build command above,
and the actual production Dockerfile independently rebuilds/tests its library.

`Dockerfile.api` now includes a reviewed `DEBIAN_SECURITY_REFRESH` build stamp,
default2026-10-08, forcing fresh signed stable indexes when bumped. No apt
mirror/suite or scanner policy is changed. The actual runtime liblzma5 must
be at least5.8.1-1+deb13u2; source/source-byte evidence alone does not prove the
installed package. Use `check-stable-packages.ps1` for disposable simulation,
then rebuild, inventory actual runtimes and repeat the native/application gates.
