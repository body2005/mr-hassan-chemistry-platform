# Trusted local browser QA

This is a local **chemistryaudit2-only** runner, not external TLS certification
or permission to deploy. It validates TLS instead of using
`ignoreHTTPSErrors`, certificate-error Chromium flags, or disabling Node TLS.
The old `chemistryprodlocal` project is not started by this runner.
QA preparation now defaults to `chemistryaudit2` too. The classic storage drill
still refuses an existing video pipeline: use `video-storage-drill.ps1` for
this project, not a storage-only overlay. Retained older data is untouched.

## Prerequisites and run

Start the synthetic QA project using the production/video overlays, including
its SMTP inbox and valid media fixtures. Do not use production data. The local
certificate must have a valid localhost SAN and validity period; its public
certificate is at `.qa/audit2/secrets/cert.pem`. Never commit `.qa` secrets.

From the repository root, using PowerShell 7:

```powershell
pwsh -NoProfile -File scripts/qa/run-video.ps1 -Stage Build -Project chemistryaudit2
pwsh -NoProfile -File scripts/qa/run-trusted-browser.ps1 -Build -SpecPattern tests/qa/trusted-tls.spec.ts
pwsh -NoProfile -File scripts/qa/run-video.ps1 -Stage Browser -Project chemistryaudit2
```

For selected cases, pass comma-separated spec paths through `-SpecPattern`.
`-Build` copies the current QA source into the runner. The dedicated official
Playwright base is version/digest pinned to match the project's lockfile.
Do not overlap browser journeys with fault injection, storage restoration,
or load/large-upload measurements. Single-worker execution retains real rate
limits; the shared fixture waits for existing rolling windows, not deletes them.
Source-review cases additionally mount `apps/api/tests/fixtures` read-only at
`/api/tests/fixtures`; this supplies the original image input and does not replace
the API extraction pipeline or mark deferred Biology accuracy work as passed.

The three large-catalog cases call `scripts.seed_qa_enrollments` inside the
rebuilt API image. The fixture refuses any project other than `chemistryaudit2`
and requires `QA_ISOLATED=true`. It only adds missing synthetic, backdated
course/enrollment rows for the existing demo institution and `student03` until
at least152 published active/completed enrollments exist. It is idempotent,
does not change credentials, and creates no photos, files or messages. Build the
API before these cases; an old image missing the fixture is a failing prerequisite,
not permission to skip the tests. Existing QA rows are retained.

The selected-course gate asserts one distinct assessment course at a time and
bounded paginated enrollment metadata reads, not a successful152-request fan-out.
Its429/503 scenarios inject a failed transport response, then require visible
contextual failure, no timed replay after Retry-After, usable authentication and
successful manual retry against the real API. Successful assessment data is
never fabricated.

Run the non-browser gates serially on the same rebuilt application images:

```powershell
pwsh -NoProfile -File scripts/qa/run-video.ps1 -Stage Backend -Project chemistryaudit2
pwsh -NoProfile -File scripts/qa/run-video.ps1 -Stage Integration -Project chemistryaudit2
```

The complete Integration command includes
`tests/integration/test_assignment_publication_live.py`: blank homework creation
must return422 without insertion; two barrier-released HTTP clients must both
reject a historically invalid draft with400 while PostgreSQL retains its state.
The test creates and modifies only its own new synthetic row, then verifies
valid publication200. It does not alter existing content or erase real limits.
Integration also contains service-fault and multi-GiB boundary tests; never run
it alongside the browser, storage drill, encoder recovery or load stage. Its
controller restores initially running QA services in a finally block even when
a test fails; successful restoration alone is not a passing test suite.

The runner installs **only the public QA certificate**, in a temporary container's
NSS trust database and Node additional CA list. No private TLS key is mounted;
Windows and the user's normal browser trust stores are unchanged. Localhost DNS
is routed to Docker Desktop's host gateway while retaining the URL hostname
and certificate validation. Tests use Africa/Cairo for dates and scheduling.

The `trusted-tls.spec.ts` gate checks both a successful browser/API connection
and rejection of a separate untrusted synthetic certificate by both clients.
A successful positive connection alone is not enough.

## Evidence and boundaries

### Small-phone, landscape and zoom reading matrix

Run the additional matrix serially, without storage/fault/load/scanner stages:

```powershell
pwsh -NoProfile -File scripts/qa/run-trusted-browser.ps1 -Build -SpecPattern qa/reading-matrix.spec.ts
```

To rerun only newly failing cases after their repair, pass an explicit name
filter; `command.json` retains it rather than describing a filtered run as full:

```powershell
pwsh -NoProfile -File scripts/qa/run-trusted-browser.ps1 -Build -SpecPattern qa/reading-matrix.spec.ts -Grep 'teacher editor reading in light|student study/video/quiz/homework'
```

This is targeted regression selection, not removal of any tests or weakening
of the default complete CI run.

`reading-matrix.spec.ts` adds six light/dark cases covering the two registration
steps, reset request, teacher editor stages, student course/video/essay/homework.
Each reading checkpoint verifies320×720 and640×360 CSS layouts without page
overflow and with horizontally contained critical controls, Cairo/RTL and
enabled zoom. It captures100% and Chromium **page/pinch scale200%**, checking
`visualViewport.scale` and the primary control's actual DOM hit target after
scrolling the zoomed page. It does not claim a submitted action at200%. This is not
deviceScaleFactor/CSS zoom, desktop-toolbar zoom, a physical-device trial or a
blanket WCAG claim. Native desktop browser zoom remains a separate boundary.
Video playback and essay submission reach the actual QA API/PostgreSQL and
encoder; successful responses are not mocked. It creates new synthetic
content/accounts only, and revokes its student session at cleanup. Existing
complete functional results are separate; adding this suite does not relabel
earlier93-case evidence as covering these new checkpoints.

Use the emitted JUnit/command manifest for actual outcomes; the list above is
test scope, not a claim of success. Reading metrics are local attachments and
screenshots do not include personal photos or storage/session credentials.

Raw browser JUnit, screenshots and `command.json` are saved under
`.qa/audit2/trusted-browser-<UTC stamp>/`. The command manifest records the
immutable runner and actual API/web/proxy/Redis image identities, current Git
HEAD, the public certificate PEM hash and exit code. A working tree is explicitly
identified as such, not claimed to be a committed or uploaded release.
Changed application image identities during a run fail the gate.

The runner needs the Docker socket for existing isolated fixtures (synthetic
teacher seeding and scoped fault checks). A Docker socket is powerful access,
not a read-only security boundary: use this trusted test code only on a local
QA machine, never expose it on a public server or run untrusted specs. The
scripts validate the exact target project/container labels before testing.

Failure traces can contain session/request data. Keep them local; do not publish
raw traces, cookies, signed playback/upload URLs, inbox contents or private keys.
Share sanitized result counts, screenshots without private data, and hashes.
This does not remove warnings in the user's ordinary browser or prove a real
domain's trusted certificate, CDN or DRM integration.

For a separate stable/security installed-vs-candidate check on actual API and
encoder images, run `scripts/qa/check-stable-security.ps1`. It queries indexes
in disposable containers, not in the running application. Its result is not a
replacement for the fresh per-image Scout/Trivy CVE gates.

For a read-only inventory of specific affected encoder capabilities, use:

```powershell
$docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
Get-Content -Raw scripts/qa/inspect-native-video.py | & $docker exec -i chemistryaudit2-video-worker-1 python -
```

First confirm the container belongs to the isolated `chemistryaudit2` project.
The output is binary capability metadata, not a crafted exploit regression or
scanner waiver. Native provenance/security regressions remain separate gates.
# Targeted handoff without repeating successful suites

After an explicitly reviewed index, `scripts/qa/check-clean.ps1 -BuildOnly`
exports only indexed sources, scans secrets, performs a clean dependency install,
builds frontend/API and compares frontend asset hashes. It does **not** execute
lint or whole frontend/backend unit suites; its command manifest records those
as `not_run: true` with no exit code. It is not a replacement for the default
full clean gate or remote CI, whose behavior is unchanged.

`scripts/qa/video-storage-drill.ps1 -Project chemistryaudit2 -DatabaseOnly`
freezes local QA writers, snapshots the current schema/data, restores into a
fresh uniquely named PostgreSQL volume and compares every public table/row.
It recovers the original writers/readiness in `finally` and preserves the new
restore volume. It does not repeat S3 copying or video/browser journeys. Use
the default full drill when those components actually change; retain previous
full-drill evidence at its original image IDs instead of relabelling it.
