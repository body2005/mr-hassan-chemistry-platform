# QA continuation — 7 October 2026

Not a release approval. Branch `fix/queen-p0-handoff`; starting local/remote
HEAD429848608834c7c012e3b2c9e7fcc4eb71f93ac0. At the start of this round,
changes were local/uncommitted; delivery commit/remote presence must be verified
separately, not inferred from this report. No merge/deployment. The detailed21-item before/after ledger is
[QA_REMAINING_REVIEW_2026-10-06.md](QA_REMAINING_REVIEW_2026-10-06.md).

## Interrupted work is not passed work

The6October19:17 Browser restart did not produce a complete JUnit/result exit;
only partial successful progress is retained, not a78-case pass. The19:25
clean export completed source export and redacted secret scan (bothExit0),
then was interrupted; remaining commands are unexecuted, not skipped/passed.
On7October Docker's engine was closed. A normal hidden Docker Desktop startup
restored29.8.1 and the existing QA containers/volumes; no factory reset, socket
deletion, data-volume removal or history rewrite.

## Earlier built/tested scope (before shared-budget correction)

The preceding runs used immutable B3 images:

- API `sha256:b4bbc0e0767568b936916b5af116362f158926a3fc55364258571160f7688f98`.
- Encoder `sha256:d3de48f473a91abce97cfb5fc3d055f2abd05038940fae9756974ab79aa82513`.
- New web `sha256:5b35474432b6ddeb9c5b7b6b0beb8ce8db9e3b3cad237be3bb3fe71cee6e0f69`.

The web alone was rebuilt/recreated, health-checked and proxy reloaded, each
Exit0. Its explicit Tailwind sources generate the exact prior88 web assets,
not a different palette/layout. Registration has TWO steps, no SMS/third review:
personal details, then contact/password/create; Arabic sign-in right/signup left.
The same API/encoder images already passed321/0/0 unit and53/0/0 live integration
on6October (1700.714s). The shared-budget runtime correction described below
follows that gate; B3 results must not be presented as its final validation.
Full78-case browser, fresh nine-command clean gate and final asset/source
checks have separate completion records below, not inferred from build success.

The first fresh clean gate (`clean-results-20261007-033149`) completed six
commands with Exit0, including all88 asset SHA-256 comparisons (zero mismatch).
Its frontend unit command then exited1: three assertions passed, but11 files
never started because Vitest forks timed out while two independent jsdom
groups competed with Docker for host memory. This is NOT65 passed, nor11
failed assertions. The regular frontend group independently passed65/0/0,
but took100.74s. Vitest now bounds its worker pool to two; per-file isolation,
all test files/assertions and application rate limits remain unchanged. A
fresh complete nine-command clean gate is required, not a waiver/retry claim.

Fresh `clean-results-20261007-033929` completed ALL nine commands, Exit0,
at03:41:43UTC: export, redacted Gitleaks (no findings), npm ci (no known
audit findings), lint (zero errors/three Fast Refresh warnings), build,
88 asset SHA checks (zero mismatch), frontend65/0/0 in7.68s, clean API
build (not deployed), API321/0/0 in67.109s. Worker concurrency alone was
changed; no isolation/assertion removal or runtime-limit relaxation.

After adding the reusable stable-package probe and revised reports, a second
complete indexed clean run `clean-results-20261007-034718` also passed all
nine commands, Exit0: frontend65/0/0, API321/0/0 in61.227s,88 identical assets
and no Gitleaks findings. It completed03:49:55UTC. Reports appended after that
run do not change application/test code; additional QA-only OCR tool is
checked separately before publication.

## Strict Extract repeat and rejected experiment

Current immutable API image, network disabled,1CPU/1GiB, fixtures mounted
read-only and fresh tmpfs OCR cache: `python -m scripts.qa_extract_fidelity
--output /qa/extract-fidelity-20261007-final.json`, Exit1, **6/1/0 files**.
All source SHA values and complete differences are retained. Biology has
10/10 question count but only7/10 fully matching; CER0.008645533141210375.
Its three differences (Q3 oxygen option suffix, Q6 tatweel/punctuation and
Q7 two word errors) were checked against both rendered original PDF pages
using the PDF visual-review skill. Review flags remain mandatory; neither
reference nor parser was edited to memorize these questions.

Strict CI now runs this unrelaxed comparator and scans actual image identities
even if another functional step fails (unless the run was cancelled). YAML
parsed successfully with js-yaml; npm audit Exit0/no known findings. Workflow
configuration is NOT a verified GitHub Actions run.

## Browser resource failure is retained, not relabelled

`video-browser-Browser-20261007-033215.xml`: **77/1/0**,1324.175s, Browser
and wrapperExit1. JUnit records the single issue as an error, not a failed
application assertion: Chromium `page.goto` ERR_NO_BUFFER_SPACE before the
calendar scenario made a request. All other77 cases completed, including
actual upload interruption/reload, decode failure/play/seek/token protection,
two-step signup light/dark/mobile/keyboard/error/loading axe, reset/password,
payment/entitlement, notification retry, real CSRF/CORS and SSE rotation.

Read-only Windows diagnostics AFTER the event found about2.3GiB available
RAM and173 TIME_WAIT connections against16384 dynamic ports. This does not
prove exhaustion at the moment of failure or establish its cause. No personal
browser/process, system network setting, service limit or production volume
was changed. Fresh targeted complete calendar repeats:
`calendar-buffer-repeat-20261007b.xml`, Exit0, **3/0/0**,14.4s, actual201
notification creation each time. The first selection diagnostic used an
incorrect fully anchored title and exited1/no tests collected; not a pass.
The focused repeats do NOT turn the failed78-case run into a full success.
A new complete Browser→Assets→source verification→Load sequence is running
serially; append its actual results only on completion.

That B3 repeat completed: `video-browser-Browser-20261007-035952.xml`,
**78/0/0**,1287.284s, Browser's eight recorded commands allExit0, npm audit
zero known findings. AssetsExit0 verified five45,835,131-byte originals and
their SHA/output existence, anonymousS3GET403 each. Source verification
then correctly failedExit1 for the three changed auth files; Load did NOT
run. This is valid historical UI/storage evidence, not final corrected-API
acceptance, and does not erase the earlier77/1/0 resource failure.

Intermediate7October source proof `runtime-source-20261007T035840Z.json`,
Exit0:114API +114encoder +89web/config SHA comparisons, zero mismatches.
Both full `git diff --check` and `git diff --cached --check` Exit0. Original
runtime inventory recheck Exit0: all1281 files remain and match their hashes.

`scripts/qa/ocr-native-image.py` is a new QA-only experiment, not runtime code.
It tries the actual embedded1547×2190 images on unrotated text-free pages
with one image covering98% of the page/no annotations. It returnedExit1,
6/1/0 files, but biology degraded to8 questions/3 fully matching and
CER0.7319587628865979. Rejected; image count alone is not fidelity.
Two initial import diagnostics exited1 because pypdf is not installed in
either deliberately minimal production/QA image; the experiment was changed
to existing PyMuPDF, not installed into either image. The complete candidate
and baseline ran on the actual API identity stated above without DB/network
secrets; offline fallback messages are not claims of production Redis bypass.

## Security refresh

### Shared authentication budget correction (7 October)

A final policy comparison against starting HEAD found a real regression in
this round's refresh classification: the new `auth_refresh` default60/min
separated refresh from the original shared `auth`15/min middleware budget.
The pre-existing route literal60/min did NOT justify relaxing that effective
shared ceiling. Earlier functional success does not close this policy gate.

Restored the original shared `auth` category for refresh and its route guard,
removed the special relaxed default, and retained exact-policy deduplication
so the route60/min check cannot hide the stricter middleware15/min check.
The independent login IP/account/short account+IP budgets are unchanged.
`test_rate_limit_classification.py`: **20/0/0**, Exit0 on7October, including
new shared15-request mixed-mutation and no-relaxed-default regressions.
New `integration/test_shared_auth_budget.py` exercises actual HTTPS from one
real client IP:15 allowed unauthenticated refresh/logout calls, sixteenth429,
another mutation429, profile read401 (not auth-budget blocked), actual window
expiry recovery401. The final B4 live result is recorded below.
No live key deletion, limit increase, server-side sleep or test exclusion.

Corrected B4 Build `video-commands-Build-20261007-042300.json` completed
all four commandsExit0, selected runtime recreated with volumes retained:

- API `sha256:16f3809bff288f16559950991d72f903ec2f732d3c552a738c643d4cd66f16e8`.
- Encoder `sha256:d6edb9feeb20b9b5d7774b842c276b2b5dc1bfeac29b0639c436895fc339f54e`.
- Web `sha256:6035b61722da3099319e7d93add9ee3933f760e66b181775428e0623a1d59c49`.

All three were healthy on inspection. B4 Backend→Integration→Browser→Assets
→source→Load→clean-checkout is running serially; record actual completion,
not a build-implied pass. New reset timing case uses twelve simultaneously
allocated real Docker client IPs, five requests/IP (original5/300s policy),
thirty existing/thirty missing samples, identical200 bodies and thirty durable
mail jobs. All recipients are synthetic at the isolated mail sink. It reports
raw measurements/quantiles/bootstrap interval, not universal timing equality.

The completed78-case B3 repeat above used the earlier image and is explicitly
historical. Source verification rejected the changed source before Load.
The new serial B4 sequence uses the corrected identities listed here.

7October raw Trivy: API91High+1Critical, encoder108High+1Critical, eachExit1.
Scout: API5High/encoder7High,0Critical, eachExit2; both scanner wrappersExit1.
Current56-ID union assessed in the preserved57-ID historical review:
[native ledger](NATIVE_CVE_REVIEW_2026-10-06.md). No suppression, severity
override or false Debian package revision. Native risk, strict OCR, full
cross-tab transport/accessibility matrix and external provider/staging evidence
remain separate OPEN boundaries; no public TLS/CDN/DRM/capacity claim.

## Contract documentation correction

A final direct comparison with the mounted routers found stale sections still
in `docs/API.md`: three-step signup, removed `/ai/jobs` and generic `/files`,
nonexistent attempt-answer PUT/telemetry batch/resume/risk/archive routes,
automatic certificate issuance and generic header-based idempotency claims.
Corrected to the actual route decorators and payload-based idempotency,
two-step signup, teacher manual grading, POST certificate request, real
telemetry/video-events and public ready versus admin-only details. Explicitly
documents the actual resumable multipart contract, not tus or external DRM.
`docs/SECURITY.md` now states shared auth15/60 and stacked reset5/300 policies.
No removed AI service was reintroduced; no runtime code changed for these edits.

## Multipart session and stale-account regression

Further review found a real gap in `uploadWithProgress`: a multipart401
immediately called clearStaleSession without attempting refresh, and a late
old-account response could resolve old data or log out the new account.
New regression `uploadRecovery.test.ts` reproduced **0/5/0**, Exit1,
`upload-before-repro-20261007.xml`. The initial restricted attempt exited1
with EPERM/no tests collected; it is not the reproduction or a five-test run.

`apiClient.ts` now checks/renews identity before sending bytes, registers
uploads for auth-generation cancellation, guards late progress/response,
and cleans up request controllers. Temporary refresh failure preserves the
account/draft. A late upload401 can renew identity but requires explicit
retry; it never automatically replays a non-idempotent multipart POST. Only
definitive refresh401 invalidates the account. Raw upload error response bodies
are no longer dumped to console. `uploadManager.ts` prevents an owner-cancelled
task from transferring after preflight and avoids redundant owner preflight.

After correction, original five regressions plus seven additional transfer,
refresh-outage/invalid/retry and pre-send cancellation cases passed with the
seven existing refresh tests: **19/0/0**, Exit0,1.30s,
`upload-after-complete-20261007.xml`; lintExit0, zero errors/three pre-existing
Fast Refresh warnings. The earlier focused post-fix12/0/0 is a subset run,
not additional tests in that19 total.

The existing manual-grading browser journey is extended, not replaced: choose
the actual homework file, remove access cookie, inject refresh503, assert no
file POST/account loss/file-selection loss or retry storm for11s, then remove
fault and explicitly retry one real POST, followed by original teacher grading
checks. Its live result is pending the final Browser stage. Browser now builds
and recreates only web/proxy before running, so changed frontend source cannot
silently test an older served image. API/encoder B4 identities are unchanged;
the intermediate web source proof predates this frontend edit.

## B4 completed PostgreSQL/Redis integration (7 October)

`run-video.ps1 -Stage Integration`, command ledger
`video-commands-Integration-20261007-042556.json`: Exit0.
`api-integration-video-20261007-042556.xml`: **55/0/0**,2029.280s,
completed04:59:49UTC. The original53 cases remain and two real-client
regressions were added; none were excluded, weakened or relabelled.
API and encoder are the immutable B4 identities above. Browser web was
subsequently rebuilt for the multipart fix; frontend completion is separate.

Shared authentication budget: first15 alternating refresh/logout requests
returned401/204, sixteenth429, another auth mutation429, profile read401,
Retry-After60 and after real expiry refresh401. No live Redis key was cleared,
no forwarded client identity spoofed, and no real limit was increased.

Reset timing: twelve distinct real Docker client IPs, five requests/IP,
thirty samples per class; all60 replies had the identical200 body, and all30
synthetic-account encrypted outbox jobs completed with ciphertext erased.
Existing median11.5715ms/p9561.802ms; missing median8.5685ms/p9553.742ms;
bootstrap95% median-difference interval **[1.6445,4.1745]ms**. This interval
excludes zero: a small measurable local timing difference remains. Moving
SMTP out of the HTTP path fixed delivery/failure coupling, **not universal
enumeration resistance**. The timing boundary stays OPEN; no fixed sleep,
random delay or weakened comparator was used to make it appear closed.

Login measurements retained all30 samples/class and verified identical
production Argon2 costs3/65536KiB/4/32/16. Existing median1201.2985ms,
p951502.717ms; missing median1202.418ms,p951500.065ms; bootstrap95%
median-difference interval[-166.5,102.828]ms. Local scheduling observations
are not proof of production timing indistinguishability.

Browser's frontend rebuild produced actual healthy web identity
`sha256:1972c13cbf3ff3f804a4c2c3c4fb2e4b6ac2bfc06138301d5b46c9eeb0dcb51b`.
Its current-source TypeScript/build and lint commands Exit0; lint has zero
errors and three existing Fast Refresh warnings. Full frontend unit group
completed **77/0/0**,19.00s,14 files; this includes the12 new upload tests,
not19 additional tests on top of77. The complete78-case browser gate is still
running at that checkpoint; partial progress was not a passed suite. Native/OCR/source/load/clean
completion must be recorded separately after their actual commands finish.

## B4 browser completion and truthful source failure

Full `video-browser-Browser-20261007-045949.xml`: **78/0/0**, Exit0,
1399.27756s; Browser's ten commands all Exit0, including lint/build,77 frontend
units and dependency audit. The real multipart503 recovery/manual grading and
current TWO-step light/dark/mobile/keyboard/error/loading registration ran.
Assets Exit0, five original hashes/output sets/private-S3 checks unchanged.
The following source gate correctly exited1 for EIGHT API file differences
from the new uniform reset implementation. Consequently this B4 chain did
NOT execute load/clean. Prior B3 load/clean evidence is not a B4/B5 result.

## Uniform reset admission: fix the measured account-dependent HTTP work

The3ms B4 difference was not written off as a successful timing test. Public
HTTP formerly looked up a tenant/account and only minted a token/mail job for
an existing user. It now inserts a fixed4096-byte padded/encrypted identity
envelope for every validated identity, including unknown tenants. No HTTP
account SELECT, SMTP, broker task, artificial sleep or random jitter.
`f3e5a7c9b1d3` adds reset_request_outbox and a nullable UTC credential epoch;
new users record birth in UTC independently of legacy naive created_at.
Migrated users remain NULL until their next password change.

Bounded25-job SKIP LOCKED DB consumers expire admission after5min. An active
account and credential-epoch check precede atomic token/mail creation,
identity-job completion and ciphertext erasure. Requests preceding account
registration or password change cannot create a new link. Consumer rollback
cannot leave a token/mail without completed admission. Mail still has the
documented at-least-once SMTP boundary. Drain BOTH queues on SECRET_KEY rotation.
Shared auth15/60, reset5/300, real Redis counters and crypto costs unchanged.

Files: routes/auth.py; models/mail_outbox.py,user.py,__init__.py;
services/auth_service.py,session_maintenance.py; migrationf3;
scripts/ci_migrations.py,seed_teacher.py; two regression modules and the live
delivery wait. UTC-final source-mounted Docker repeat:
`reset-uniform-utc-20261007.xml`, **68/0/0**, Exit0,23.022s:
13 admission regressions,36 existing security,14 seed,5 actual PostgreSQL.
SQL observer proves no users/institutions SELECT in admission; identical200
and ciphertext length; absent/inactive/deleted/expired/corrupt/pre-registration
discard/erase; both credential-change paths; uniform DB503; commit-loss retry.
Four real PostgreSQL consumers claim20 requests once,20 unique tokens/mail;
lost commit rolls all effects back then produces exactly one on retry.
Source-mounted evidence is NOT a rebuilt API/timing gate; B5 runs separately.

## Playback stale-response defects and fabricated metadata

New tests render the ACTUAL VideoLessonPage with controlled pending requests.
`playback-race-before-real-20261007.xml`: **0/5/0**, Exit1. Late manual renewal
success overwrote the new lesson URL; late failure showed its old error on
the new lesson; late unlock also changed URL/toast; changing account on the
same lesson did not reacquire playback; metadata invented16.3k views and
24January2024 without server data. The restricted attempt before this exited1
with EPERM and NO tests collected; it is not the reproduction.

Fix: scoped request lifetime, account-change reacquisition, stale success,
error/finally/unlock guards. Extracted useHlsTransport owns native/HLS media
lifetime and discards disposed callbacks. Old native src is removed while
admission is pending. HLS401/403/429 stop loading, retries remain NULL; token
renew cooldown and4min timer unchanged. Removed fabricated views/date;
missing/invalid publication date explicitly says unavailable.
`playback-transport-after-20261007.xml`: **10/0/0**, Exit0,2.05s; five original
component regressions plus five transport lifetime/status checks. Full local
frontend `frontend-before-b5-20261007.xml`: **87/0/0**, Exit0,9.55s,16 files;
lint/build Exit0, zero errors/three retained Fast Refresh warnings. Live browser
after rebuilding B5 is separate; this unit mock is not real network evidence.

The existing full essay/homework browser journey is extended with TWO real
tabs, blob download, multipart admission, JSON bootstrap and SSE while sharing
cookies under refresh503. Original exact one-refresh/no-transfer/retained-file
checks remain. Recovery uses explicit download/upload and real identity reload;
full B5 result must establish this, not source inspection alone. Combined
video cross-tab outage matrix is still distinct from single-video HLS proof.

## Additional bounded Extract candidates — all rejected

QA-only `scripts/qa/ocr-render-candidate.py` runs all seven original-SHA inputs
with the unchanged strict comparator in a fresh offline1CPU/1GiB container.
No source answer dictionary, comparison relaxation or production parser change.
Each row individually exited1, **6/1/0 files**; shell loop Exit0 is NOT a pass.

| Candidate | Biology questions / fully matching | CER |
|---|---:|---:|
| Baseline1.5 ara+eng | 10 / 7 | 0.008645533141210375 |
| Scale1.75 | 10 / 7 | 0.33285302593659943 |
| Scale2.0 | 8 / 5 | 0.3745704467353952 |
| Scale2.5 | 6 / 0 | 1.2141057934508817 |
| Scale1.5 retain RGB | 8 / 4 | 0.48947368421052634 |
| Scale1.5 Arabic only | 8 / 4 | 0.4020618556701031 |
| Scale1.5 eng+ara | 10 / 7 | 0.008645533141210375 |

Artifacts are the scale/color/language JSON reports under private .qa/audit2,
including complete per-question differences and unchanged source hashes.
Higher resolution/color did not reliably fix Arabic source fidelity; every
candidate was rejected, preserving mandatory teacher review and source words.
Strict OCR remains OPEN; synthetic DOCX tests do not prove unavailable real
user Word-document fidelity.

## B5 rebuilt runtime and full backend gate

Build `video-commands-Build-20261007-053851.json`: four commands Exit0;
selected QA runtime recreated with named data volumes retained, healthy:

- API `sha256:12bae960230c9574e32a21fa09b252be5905e1525f7c886666769eabcd9d85fd`.
- Encoder `sha256:a16e1664906673375b299c288ba4fe816245318f0a56a9cfa579905eab77517a`.
- Web `sha256:987593b85d01f683af755239e17b91467491635dc1c3fe3331d17ad88d55a1d9`.

First Backend `api-unit-video-20261007-054015.xml`: **335/1/0**, Exit1,
58.759s. Old session-security mail test called delivery without consuming the
new identity queue; no mail was minted yet. Fixed the test to require two
pending encrypted requests, actual process_reset_requests=2 then0, both erased,
followed by the ORIGINAL one-mail/TLS/fragment-link/confirm/idempotence checks.
No assertion removed or production code/limit changed for this test repair.
Later stages in that failed command chain did NOT execute.

Full Backend repeat `video-commands-Backend-20261007-054836.json`: five commands
Exit0, **336/0/0** API units,63.358s; actual native Expat4/0/0 per image, fresh and
previous-head PostgreSQL migrations to SINGLE headf3e5a7c9b1d3, and actual
lost-multipart200expired/409/201/204 with no500. This supersedes, but does not
erase, the preceding335/1/0. Full live Integration/Browser/source/load/clean,
raw scans and final backup/restore are separate gates, not implied by units.

The HLS live journey now additionally opens a second real tab, observes an
actual connected SSE, denies segment transport403, expires shared access and
injects refresh503 during manual renewal and other-tab JSON/SSE recovery. It
retains both account caches, observes11s bounded retries, restores identity,
requires SSE connected again and continues original decode/play/seek/403 after
logout/revoke assertions. This extension is unverified until B5 Browser runs.

## Question-editor separation (current frontend, pending full browser)

Extracted McqOptionsEditor and QuestionSourceReview from QuizGeneratorView.
Display/editing callbacks retain historical option keys and call the SAME
add/remove/answer services;26 max/two min and explicit source-fingerprint
approval unchanged. Named answer buttons expose aria-pressed, inputs/delete
buttons have per-question names, native input focus outline is retained, and
text follows light/dark tokens. Pure presentation does not invent an answer
or acknowledge OCR. No bundle/render performance benefit is claimed.

First lint after extraction exited1 for the now-unused formatChemicalFormula
import; removed only that moved import. The first new component-unit attempt
could not start its fork and exited1, NO tests collected (60s worker-start
timeout), not a failed assertion or5 passes. A readonly host-memory diagnostic
reported873.9MiB available out of16175.2MiB while live integration ran. An
isolated thread-pool diagnostic retained the same tests and file isolation,
but also exited1 before collection after60s. Neither attempt ran the five
assertion cases: the JUnit error is a worker-start error, not five failures
or five passes. No permanent pool/timeout change was adopted.

Read-only host diagnostics at06:02:43Z:16175.2MiB total,965.8MiB available;
vmmemWSL5415.1MiB and multiple browser/desktop processes. This does not prove
the user's YouTube tab or memory alone caused the startup failure. No user
program or unrelated Docker project was stopped. Retry frontend separately
after live integration, preserving the default pool and all assertions.

Full B5 Integration started05:50:03Z; one failure indicator appeared while
the suite continued. Until pytest finishes and its actual traceback/JUnit
are inspected this is NOT a passed integration gate, nor a diagnosed cause.
The command chain stops at nonzero: subsequent Browser/Assets/source/Load
stages cannot be inferred to have executed.

After removing the moved import, `npm run lint` and `npx tsc -b` both exited0
at06:08Z. ESLint: zero errors, three retained Fast Refresh organization
warnings (ConfirmWizard, ToastProvider, i18nContext). No warning suppression.
This TypeScript check is not the Vite build, component-test or browser gate.

Separate default-forks retry `question-editor-quiet-20261007.xml`: **5/0/0**,
Exit0,13.08s, on the unchanged tests with one worker. Memory had recovered to
2427.6MiB free. The running uncapped QA runner accounted for142884864 anonymous
bytes and2813153280 file-cache bytes. This is correlation, not proof of a
single cause for the preceding startup failures. Added `mem_limit:1024m` to
the test-only qa-tests overlay for NEXT runners; application/upload limits
unchanged, no running process stopped. Full defaults/browser still separate.

Full default-pool `npm test -- --reporter=default --reporter=junit
--outputFile=.../frontend-b5-20261007.xml`: **92/0/0**, Exit0,17files,14.46s.
No file isolation/pool/timeout relaxation; includes all five new editor tests
and ten playback lifetime/status regressions. `VITE_API_URL=/api/v1 npm run
build`: Exit0,25.43s; video chunk634.19kB warning retained, not hidden or called
an improvement. Current question-editor chunk112.73kB is a build measurement,
not an initial-render latency or total-download improvement claim.

## B5 integration failure and actual cancellation diagnosis

Full `api-integration-video-20261007-055003.xml`: **56/1/0**, Exit1,
2644.796s. `test_exact_upload_byte_boundaries[material-1]` uploaded1GiB+1
and received plain500 instead of413,161.090s. The chain stopped; no subsequent
Browser/Assets/source/Load ran. Read-only API Docker logs retain BOTH
reservation-loss messages at05:59:52.269Z and ASGI CancelledError at05:59:58.563Z,
inside this case's timestamp/elapsed boundary. Distributed lease renewal
failed closed by cancelling its owner, but outer ASGI wrappers did not classify
that intentional cancellation. The reason for the original renewal failure
(expired/missing versus backend error) was not logged; memory pressure is NOT
established as its sole cause.

Unmodified live case repeated alone with the1GiB QA runner cap:
`material-overflow-repro-20261007.xml`, **1/0/0**, Exit0,113.134s. This repeat is
NOT a fix or replacement for the failed full suite.

Actual ASGI cancellation reproduction before runtime edits:
`lease-loss-before-20261007.xml`, **2/3/0**, Exit1. Admission alone, upload alone
and nested reservations propagated CancelledError before headers; existing
client-cancel/started-stream conditions passed. Added explicit lease-loss state,
sanitized reason class (never backend exception text), and one503/Retry-After2
only for OUR cancellation before headers. Already-started streams close;
client cancellations propagate. Reservation120s/renewal30s, concurrency and
rate limits unchanged. Known parsed material size now rejects overflow before
a second staging copy/provider access; unknown size retains streaming count.
Compensation only begins when remote transfer may have created bytes.

Source-mounted focused attempt `lease-loss-after-20261007.xml`: **7/2/0**,
Exit1, two NameErrors in the new test because response assertions were inserted
into the renewal-only case. Moved ALL those assertions back to their response
case; no assertion removed. `lease-loss-after-v2-20261007.xml`: **9/0/0**, Exit0.
Includes actual renewal0/error behavior, secret-free diagnostics, unrelated
cancel, already-started stream and known/unknown file-size rejection. These
tests are source-mounted, NOT B5 immutable-image acceptance. New API/encoder
build and full backend/live/browser/load/scan/source/restore/clean repeats are
required after these four runtime-file changes.

## B6 actual rebuilt services (after lease fix)

`video-commands-Build-20261007-064605.json`: all four commands Exit0, completed
06:51:02.721Z. Selected services healthy; named volumes retained, no other
project stopped. Runtime identities read with Docker inspect at06:51Z:

- API `sha256:fc8aa9ef04839d1e1f80a295f627e19ff1bdea0dd6d8b194b6d64bf60cc4c2e0`.
- Encoder `sha256:8b857eab12fd6425a7a75939fb03513f41755b2ff26bda71c79ed9bd38615d11`.
- Web `sha256:0451fa07c54cb3814950cf69d94ca9d1cf8680618c2a5e8531474af4294de9fb`.

Both actual native Expat4/0/0 checks Exit0. Full API unit gate is running,
not yet a345-case pass. New `integration/test_upload_lease_loss.py` pauses a
real multipart stream, observes the actual Redis reservation, stops ONLY QA
Redis, requires actual API reservation-loss diagnostics, expects503/Retry-After2
and security headers with no LessonAsset, restores Redis/readiness before
closing the identity. No lease/rate counter is erased. This live case is NOT
verified until executed; full integration will now include it.

B6 Backend `video-commands-Backend-20261007-065102.json`: all five commands
Exit0. `api-unit-video-20261007-065102.xml`: **345/0/0**,89.561s. Both actual
Expat4/0/0, fresh and previous-head PostgreSQL migrations, and actual missing
multipart200expired/409/201/204 with zero500 also0. This replaces B5 for those
specific gates, not full live/browser/scanner/restore acceptance.

B6 focused live acceptance `lease-live-b6-20261007.xml`: **3/0/0**, Exit0,
66.900s. Actual Redis interruption during a paused multipart upload returned
503/Retry-After2 and left no LessonAsset (50.883s); an actual material upload of
1GiB+1 returned413 (14.278s); a real PostgreSQL commit failure compensated the
stored SeaweedFS object (0.530s). Full58-case Integration, then Browser, Assets,
source parity and Load are running sequentially; their results remain pending.

## Native dependency reduction candidate — not installed

07:06Z read-only B6 candidate assessment: `apt-get -s purge --auto-remove
poppler-utils curl` in a128MiB/.25CPU/no-network disposable container proposed
24 removals, including unused Poppler/GPG dependencies. Tracked-source grep
found no application Poppler call (only installer/workflow and diagnostic
inventory). Actual Tesseract ldd still links libarchive/libcurl/libxml2, so
removing Poppler alone would NOT close the XML findings. No package was
removed from B6 or a running service; full Integration is still in progress.

The stable official Tesseract5.5.3 release has supported DISABLE_CURL and
DISABLE_ARCHIVE switches. Its GitHub tag object
6951ffe10ce031374bcd04fe400811da1e7e04ad points to
db0ec62f81b0737fbbe184d8fea40af5738f8eef; GitHub verification reports valid.
The official tag archive downloaded to private QA has SHA256
9218e62793116d42a9f6d14cd9348518b27f382096eea3d0f2d1a24616bb5884.
`scripts/qa/build-ocr-candidate.sh` prepares a bounded, single-build-thread,
disposable-container experiment with network/archive/debugging disabled and
the existing image codecs retained. POSIX syntax check Exit0. Build, actual
dependency removal and ALL original strict OCR comparison are PENDING; no
OCR accuracy/security success or production upgrade is inferred from options.
Heavy compilation will not overlap the functional/browser/load/restore gates.
Any later runtime replacement needs rebuild, tests and fresh raw scans.

## Explicit pause and resume — 7 October

The user explicitly paused work. Only the verified active
`chemistryaudit2/qa-tests` runner was stopped; the wrapper returned1 because
the interrupted Integration command returned137. No final JUnit/58-case
success is inferred, and the chain did NOT run Browser/Assets/source/Load.
All nine selected persistent runtime services were healthy at pause; no
synthetic reset timing probe remained running. No commit/push/deploy occurred.
The pause is an interrupted run, not an application regression or a skip.

On explicit resume at08:30Z, branch/local HEAD remained
fix/queen-p0-handoff/429848608834c7c012e3b2c9e7fcc4eb71f93ac0; existing indexed
and unstaged changes and unrelated pc_builder_3d_cases were retained. Docker
Desktop was no longer running and Linux engine pipe was absent; about5404MiB
host memory was available. Normal Desktop startup was requested without
factory reset, volume deletion or changes to other projects. Recheck engine,
runtime identities and health before repeating any final gate.

Resume frontend: lint0 (zero errors/three Fast Refresh warnings), tsc0.
`frontend-resume-20261007-083323.xml` failed during resolution with EPERM
realpath errors in17 suites, **zero actual tests executed**; not17 failed
functional assertions and not a proved RAM failure. Same unchanged test
configuration under permitted child-process execution:
`frontend-resume-permission-20261007.xml`, **92/0/0**, Exit0,12.40s;
VITE_API_URL=/api/v1 production build0,34.87s. No isolation/timeout/assertion
relaxation. Existing634.19kB video chunk warning remains visible.

Readiness after Docker restart correctly returned503: DB/Redis/storage/broker
were ok, Celery worker/ingestion unavailable. The existing QA worker was
stopped (Exit137). Its B6 image is
sha256:5ff95a8041fa35cb090a1b70aa28dbbbb2caeb0af7f5799a2b83fd3cce380533,
created06:46:38Z with API/migration in the completed B6 build, and matches
its current tag; it is NOT required to equal the API's separate manifest ID.
An initial exact-API-image guard correctly refused to start it until this
separate identity was checked. It was then started without recreation/data
changes. The final source-parity gate now additionally hashes actual Celery
worker source, not just API/encoder/web. No other Docker project was stopped.

## Resume: controller recovery and rejected native upgrade

`scripts/qa/runtime-recovery.ps1` records the ten exact initially-running QA
containers and image IDs before the Integration runner starts. Its controller
finally can start only the same allowlisted, unchanged container; it never
recreates a missing/replaced service, resets data or touches another project.
The original failed/interrupted test record is retained separately; recovery
does not turn it into a pass. `test-runtime-recovery.ps1`: **9/0/0**, Exit0
(controller mocks only). `test-runtime-recovery-live.ps1`: **1/0/0**, Exit0;
actual HTTPS200 at08:58:42Z, worker stopped, actual503 at08:58:50Z, ONLY that
same B6 worker restarted, actual200/ready at08:58:57Z. Private result:
`runtime-recovery-live-20261007-085837.json`. Running-state recovery alone is
not readiness proof; this separate actual request is. Full Integration remains
uncompleted since the explicit pause.

Tesseract5.5.3 disposable build completed Exit0, OOM=false,768MiB/1CPU cap.
Actual ldd contains no libarchive/libcurl/libxml2, not just disabled options.
`compare-ocr-runtime.ps1` ran the UNCHANGED strict comparator against the B6
immutable baseline and candidate, offline, read-only source fixtures, bounded
non-root processes and new private temporary storage. Fixture SHA/parser scope
match. `ocr-runtime-20261007-085151/`: baseline **6/1/0**, Exit1; candidate
**5/2/0**, Exit1; wrapper1. Biology PDF still10/7 matching with the same CER;
PNG regressed5/5→5/4 (التنفسي→التنفكسي), CER0.0025906735751295338. Both original
biology PDF pages were visually reviewed again. This candidate is REJECTED,
not installed in the site, despite dependency reduction. Upstream unit tests
were not executed in that candidate build; no hidden claim of their success.

The comparator now also supplies a fresh64MiB `/srv/storage` tmpfs in each
container; the earlier B6 baseline was read-only and its Docker context excludes
storage, so no old cache was supplied. A second QA-only experiment rebuilds
the CURRENT Debian stable5.5.0 source with its help-text patch and hardening
flags, disabling only optional URL/archive/debug support. Source/debian archive
hashes match the official HTTPS DSC; maintainer PGP signature has not been
independently verified. Build/strict comparison are pending. No source words,
models, expected answers, limits or production image were changed. Reproducible
tools are in `scripts/qa`, not solely scratch; private binaries/sources stay `.qa`.

## Additional video keyboard/layout regression

The existing course breadcrumb was a pointer-only span with role=button and no
key handler. Its navigation also had a fixed-346px right offset, independent of
viewport. `video-navigation-before-20261007.xml`: **5/2/0**, Exit1 (actual
SPAN versus native-button and negative-offset assertions). New focused
`VideoLessonNavigation.tsx` owns navigation layout/native buttons only; it uses
the existing light/dark text variables and keeps playback/auth outside it.
`video-navigation-after-20261007.xml`: **7/0/0**, Exit0,2.13s. Lint0/zero errors,
same three Fast Refresh warnings; TypeScript0. No assertion was removed.

The full real-video Playwright case additionally checks390px RTL bounds, axe,
Enter and Space closing/reopening the lesson. Those browser assertions are
PENDING on the rebuilt web image, not proved by the jsdom native-tag test.
Current full frontend94-case gate/build/served-source parity must be repeated
after this UI change; the earlier92-case result is not its final acceptance.
No bundle/render speed claim follows from moving the navigation into a module.

## B7 stable OCR dependency reduction — build in progress

Same-version disposable build completed Exit0/OOM=false, with768MiB/1CPU cap;
actual ldd has no archive/curl/XML. Fresh64MiB-cache strict comparison
`ocr-runtime-20261007-091025/`: baseline **6/1/0** and candidate **6/1/0**,
each Exit1, wrapper1. ALL seven parsed outputs and source SHA values are
identical, including ordered options/science symbols. Biology remains10/7,
CER0.008645533141210375; strict gate remains OPEN, not6/1 relabelled as pass.

`apps/api/scripts/build_native_tesseract.sh` converts that source/configuration
into two explicitly local packages, version5.5.0-1+chemistry1 and Source=tesseract
(5.5.0-1); it does NOT pretend to be a newer engine/official Debian security
package. Official DSC/upstream/Debian SHA pins and Debian-keyring signer check
fail closed. Arabic/English/OSD models and image codecs remain; no training,
URL-image/archive/debug libraries enter runtime. `infra/Dockerfile.api` removes
unused curl/Poppler, installs these packages, verifies actual ldd/package
absence and model paths, retains stable trixie/OpenSSL/Expat/non-root limits.
The signature/package build and final runtime gates are PENDING, not inferred
from the disposable comparison. Runtime inventory reports missing packages
explicitly rather than assuming pdftotext/libxml2 exist or are patched.

B7 Build started09:14Z, while B6 serves the site until selected-service startup.
No functional/browser/load/restore suite runs during this heavy image build.
09:15Z `git ls-remote` still429848608834c7c012e3b2c9e7fcc4eb71f93ac0, equal
to local HEAD. All this round's changes are local/uncommitted; no push/merge/
deployment has happened. Fresh B7 IDs and full backend/live/browser/source/
scanner/backup/clean results must supersede B6 only once actually completed.

09:26Z read-only runtime-asset verification repeated: `archive-runtime-assets.ps1
-VerifyOnly -Manifest .qa/runtime-assets/20261006-121936/inventory.json`, Exit0,
ALL1281 original hashes match. Controller mock suite repeated9/0/0, Exit0.
An initial invocation used paths relative to apps/web and did not execute either
PowerShell script; the subsequent absolute-path invocation is the evidence,
not its unrelated successful YAML parse. Workflow YAML parses successfully.
The CI job controller budget is now150min: known full live integration/browser
alone exceed60min, plus cold signed-native builds, media preparation and scans.
No application timeout, test assertion or rate budget was reduced. GitHub CI
has not run on these unpushed changes.

09:26Z host available memory622MiB of16175MiB; no frontend/browser/load suite
launched during the native build. Read-only Docker samples: B6 API331.2MiB,
encoder91.34MiB and Celery60.16MiB; these are instantaneous idle observations,
NOT load peaks or capacity evidence. C:42.82GiB/D:236.30GiB free. User programs,
other Docker projects, original assets and prior backups remain untouched.

## B7 actual image gates — 7 October,09:35–09:51UTC

The signed same-version OCR rebuild completed. First code refresh at09:32
failed in disposable QA tooling: pip timed out downloading from
files.pythonhosted.org (pipExit2/buildExit1). `infra/Dockerfile.qa` now uses
the pinned pip26.2.1 plus bounded3 retries/60-second download timeout; no
production rate limit or test assertion changed. Retried Build
`video-commands-Build-20261007-093428.json`: all4stepsExit0, startup09:35:51Z.
Earlier successful Build and failed refresh artifacts are retained.

| Service | Actual immutable B7 image |
|---|---|
| API | `sha256:dfb1939048e78ee4a7520a2c88a636b00a702c2873c7b25638be9cd9f7d29884` |
| Celery | `sha256:2236d8c6a6934e16a67ccdaa10e3e28d099575f139d5d4a319915823badf7ba6` |
| Encoder | `sha256:5a5cc7470cec835993825698a5c06c2a60678ab5f28741ac29ec804fadb31c40` |
| Web | `sha256:a107ec35aa2205518be4e1f19b512f10611c5dc5665fe00b5d406bfb595b51f4` |

| Executed command/gate | Exit | Passed / Failed / Skipped | Evidence/scope |
|---|---:|---|---|
| npm run lint | 0 | zero errors/3 Fast Refresh warnings | `frontend-b7-lint-20261007.log` |
| VITE_API_URL=/api/v1 npm run build | 0 | build, not test cases | `frontend-b7-build-20261007.log`; player634.46kB warning retained |
| npm test -- --maxWorkers=1 --reporter=default --reporter=junit | 0 | 94 / 0 / 0,17 suites,32.21s | `frontend-b7-20261007.xml`, BEFORE the subsequent publication module change |
| npm audit --audit-level=high | 0 | 0 known findings | `frontend-b7-audit-20261007.log` |
| run-video.ps1 -Stage Backend | 0 | API345 / 0 / 0,60.539s | `api-unit-video-20261007-093844.xml`; all5command steps0 |
| Actual native Expat regressions, each image | 0 each | 4 / 0 / 0 EACH API/encoder | Same Backend command artifact, not inferred version-only |
| Fresh/previous-head PostgreSQL migrations | 0 each | 2 migration commands, not test counts | Head f3e5a7c9b1d3 |
| Actual missing S3 MPU recovery | 0 | expired200, complete409, new intent201; zero500 | Backend command; synthetic session cleanup204 |
| Runtime inventory and Linux64 nothrow aligned-new | 0 each | aligned-new10 / 0 / 0 EACH | `security-b7-20261007-0941/`, inventory not a per-CVE exploit proof |
| verify-runtime-source.ps1 | 0 | 115 files EACH API/Celery/encoder +89web/config,0 mismatches | `runtime-source-20261007T094209Z.json`, BEFORE subsequent UI/build-script edits |
| Trivy pinned0.69.3, fresh DB, actual image IDs | 1 each | API62High/0Critical; encoder79High/0Critical | `trivy-20261007-094251/`, no ignores |
| Docker Scout, actual image IDs | 2 each | API3High/0Critical; encoder5High/0Critical | `scout-video-*-20261007-094408.sarif`, wrapper1 |
| Strict seven ORIGINAL Extract fixtures | 1 | 6 / 1 / 0 | `extract-fidelity-b7-20261007.json`; biology10 questions/7 fully matching, CER0.008645533141210375 |

Actual runtime inventory: OpenSSL3.5.7-1~deb13u3, OS/Python Expat2.8.5,
Tesseract5.5.0-1+chemistry1/CLI5.5.0. Removed OS libxml2/curl/Poppler/archive
are actually absent, not relabelled patched. Actual ldd has no optional OCR
URL/archive/XML/graphics integration. Root-owned source/signature files
verify the exact Debian signer406220C8B8552802378CCE411F5C7A8B45564314.
Bundled lxml/libxml2.14.6 is independent and remains a separate assessment.
The strict biology failure was NOT fixed by dependency reduction.

Full58-case integration started09:51UTC on B7 and is still RUNNING as this
entry is written. No final JUnit exists yet; no passed count is inferred from
container uptime/CPU or the345 unit cases. Browser/load/storage/clean-index
gates are still pending. Heavy gates run sequentially, without stopping the
user's applications or other Docker project.

## In-progress follow-up and explicit deferred scope — 7 October,10:13UTC

The user explicitly deferred improving Extract in BIOLOGY until later.
Keep the failing strict result and original comparison; do not remove cases,
memorize corrected words, reduce tolerances or claim perfect OCR. No subsequent
biology/model/parser change is planned in this round.

`QuizPublishConfirmation.tsx`/CSS isolates display from the unchanged API/draft
publication lifecycle, keeps green light/dark theming, native focus containment
and close locking, wraps long/mobile summary rows, and retains18px12-hour date
labels. Ten new component tests and one additional real-browser scenario cover
summary/type/grade, escaped title/error, busy/close callbacks, focus restoration,
dark mobile/error/loading plus a real PostgreSQL retry. They are PENDING, not
part of the earlier94-case result. Full frontend and served-source gates must
repeat; module extraction alone is not a speed claim.

Fresh [official FFmpeg release page](https://ffmpeg.org/download.html) identifies
9.0.2 as a STABLE upstream release, not an unstable distribution. The official
12,040,788-byte archive SHA256 is
`8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e`;
actual GPG verification Exit0/VALIDSIG
`FCF986EA15E6E293A5644F10B4322F04D67658D8` is retained under
`ffmpeg-9.0.2-source-20261007/`. The initial Git-GPG Windows path invocation
failedExit2; using the proper MSYS path passed. Unknown owner-trust is not
silently treated as Web-of-Trust validation: exact published key fingerprint
and signature are checked independently.

The native builder now pins that real release and honest local package version,
retaining stable Debian13, disabled network/devices/autodetection, x264/AAC/HLS,
non-root resources and actual encoding/decoding smoke checks. Encoder source
and signature provenance are retained outside slim doc exclusions. New major
release compatibility, rebuild, BOTH raw scanners, runtime/native regressions
and all final functional gates remain PENDING before adoption. B7 scan/unit/
source evidence above must not be represented as acceptance of this B8 change.
No commit/push/merge/deployment has happened in this resumed round.

## B7 completed integration / B8 retained failures and safety checks

At10:29:54UTC, the B7 full PostgreSQL/storage/fault integration command
completed Exit0: **58 passed /0 failed /0 skipped /0 errors**,2298.973s,
`api-integration-video-20261007-095128.xml`. The controller's finally recovery
also completedExit0 at10:29:56; this only proves restoration of the initially
running services, not independent readiness. New B8 source was not part of
this result and requires its own complete repeat.

Actual B7 timing artifacts verify production Argon2 costs3/65536/4/32/16:
30 samples/class, existing-wrong median1196.002ms/p951805.988ms versus missing
median1206.527ms/p951597.949ms; bootstrap median-difference95% interval
[-244.189,187.637]ms. Uniform reset admission now measures30 samples/class:
existing median9.796ms/p9563.94ms versus missing median9.948ms/p9574.082ms;
interval[-2.683,2.248]ms includes zero, and30 actual durable jobs completed
with ciphertext erased. This closes the observed B4 local timing gap for
this tested version, not a proof of universal production timing equality.

Actual OLD encoder checks failedExit1, **3/3/0**: actual7.1.5 instead of9.0.2,
no disabled RASC and no external provenance files; network/hardware/common-
codec checks passed. Retain `native-video-before-b8-20261007.log` and its
immutable image identity. The first B8 Build failedExit1 at frontend TypeScript
because the new presentation prop excluded the existing `number | ''` duration
state. The component now accurately models that state; a unit case proves it
does not invent a duration. No API validation/publication mutation changed.
`build-b8-20261007.log` remains the failure; retry is a separate artifact.

Mixed load adds a pure safety controller. It stops new requests/prevents the
next stage on a rolling100-request error rate above1%, interactive browse/video
p95 above2000ms, a whole large upload above15000ms, or three consecutive actual
samples above90% cgroupCPU/RAM,80% PostgreSQL max_connections, or50 queued/
processing video jobs. In-flight requests finish within existing timeouts.
Actual limits, queue depth, stop reason and completed/planned stages are saved.
429 is a single failed request, never automatically retried; errors below the
stop threshold still fail the final gate. These are safety bounds, not changed
production limits, application-pool utilization estimates or capacity proof.
Ten pure controller tests and the actual mixed load remain pending.

## B8 actual build/native/backend — 7 October,10:49UTC

`video-commands-Build-20261007-103737.json`:4 commandsExit0, actual startup
10:46:55UTC. This is a real rebuilt/recreated QA project with named data volumes
retained, not `config -q` alone. Every required service reports healthy. The
first frontend type failure remains in its separate earlier artifact.

| Service | Actual B8 immutable image after Build |
|---|---|
| API | `sha256:e6e210a8e4862568af94dafc689fdd2ff841b6cf29b263726740582810750ea0` |
| Celery | `sha256:01880e9a8597739c28b5922c06864bd62e43413af1eccb47a8ccd4e9fad5cefd` |
| Encoder | `sha256:8ecf7fd48f2eec39a1cccc97257d515559e037d87a9cd145de6a0505b3ba706c` |
| Web | `sha256:077e64308cace0773d758de3d1f7abccb34acbafd40bd40dfba56402a396435d` |

Actual encoder9.0.2 native proof completedExit0, **6/0/0**:
`native-video-20261007T104750Z.json`. Authentic source/signature ownership,
disabled RASC and runtime decoder absence, no network/hardware paths and
retained common codec/HLS registration are tested, not inferred from package
names. Builder's real2-second H264/AAC HLS encode/decode/probe smoke passed.
These are not crafted exploit cases or blanket vulnerability waivers.

`video-commands-Backend-20261007-104747.json`: all6commandsExit0, completed
10:49:06UTC. API **355/0/0**,61.591s,
`api-unit-video-20261007-104747.xml`; this includes the ten new pure load-policy
cases. The separate local tool-only run also10/0/0,0.251s,Exit0, using
`--noconftest` ONLY for that standalone pure module, never for the full API
gate. Native Expat4/0/0 EACH, fresh/previous PostgreSQL migrations2commands0,
actual S3 missing-MPU expired200/complete409/newintent201/logout204,zero500.
Current lintExit0,zeroerrors/three retained Fast Refresh warnings.

Full79-case Browser is started next; its counts, final served source, BOTH
scans,58-case B8 Integration, HLS/playback/recovery/assets/load/restore and
indexed-clean gates are still pending. No source/image identity is silently
substituted by a successful historical B7 test.

B8 Browser's preflight lint/build completedExit0. All frontend unit cases
actually passed **105/0/0**,18 suites,37.78s,
`frontend-video-20261007-104946.xml`. The unchanged native-dialog lifecycle and
new confirmation module include eleven new presentation cases; these are not
a substitute for native browser accessibility/publication evidence.
`verify-runtime-source.ps1` completedExit0 at10:52UTC:116 source files EACH
API/Celery/encoder and90web assets/config, **zero mismatches**. Browser's web
rebuild/recreation now actually runs
`sha256:4aabcb57e2e325b83cbc3c78f078c19431f8e60bfdddd02ea82fa3eef235498f`;
do not use the earlier Build web identity for the forthcoming browser result.

At10:59UTC explicit task files were staged for clean-index QA; **no commit or
push**.148 project-source/tools entries plus1281 index-only runtime removals;
zero `pc_builder_3d_cases` entries. Originals and private archive remain on disk.
The first cached `git diff --check` caught a new-file trailing blank line in
`qa_load_policy.py`, Exit2, which the earlier unstaged check could not see.
Removing that final blank and restaging the one file gave cached and working
checksExit0. This QA-only whitespace change does not alter application behavior,
but the strict116-file runtime byte gate is now superseded until a cached
rebuild adopts it. Do not claim the10:52 whole-tree byte proof as final.
The full current Browser run remains meaningful for the unchanged application
payload; final same-source rebuild/backend/browser gates will repeat afterward.
Controller-only regressions independently passed9/0/0,Exit0; they do not prove
live service readiness.

### B8 full-browser outcome and B9/B10 follow-up (7 October, local only)

B8 full Browser completed Exit1, **77/2/0**, 79 collected,
`video-browser-Browser-20261007-104946.xml`,1473.15992s. The two failing cases
were student avatar automatic reload and protected WebM playback/seek recovery.
They are NOT counted as fixed by earlier unit/build successes. The video trace
showed initial valid HLS/ranges and processing, then an actual access-cookie
refresh200 followed by video-token429: admission counted access JWT jti rotations
as extra devices. The new actual HTTPS/PostgreSQL/Redis regression reproduced
this on B8: `video-slot-live-before-b9.xml`, **0/1/0**, Exit1 (expected200,
actual429 after refresh). No device ledger or rate counter was erased.

`platform.py` now counts the validated refresh family while retaining strict
current-jti nonce binding on every stream request. Family logout removes only
its family slot and the current legacy jti. Existing legacy jti slots are NOT
reset on upgrade; they expire normally within the old token's300s+ledger margin.
Unit proof `video-slot-unit-b9.xml`, **6/0/0**, Exit0, tests quota retention,
rotation, legacy coexistence, normal expiry and scoped revocation. Full live
after-build proof is pending, including eight real concurrent token requests,
old-link403 and an actually blocked third device.

The first focused rerun failed before the site because Docker Desktop was
stopped. `docker desktop start` returned0 and resumed existing containers;
no factory reset, data deletion or unrelated-project stop. The next diagnostic
avatar run had a harness error (starting already-enabled Playwright tracing),
which was removed. The original student avatar case then passed alone **1/0/0**,
Exit0; this does NOT establish the cause of its earlier full-suite timeout.
A separate delayed-bootstrap regression reproduced account actions available
from cached identity before server hydration, **0/1/0**, Exit1. `App.tsx` now
gates profile changes until the matching real bootstrap has arrived.

The enhanced dark/mobile publication retry case reproduced a previous-attempt
error still displayed while a held retry was busy, Exit1. Explicit screenshots
are retained in `b8-focused-before-live`. `QuizGeneratorView.tsx` now clears that
old error only after local validation and before entering the new attempt.
Current post-edit lintExit0, zero errors/three Fast Refresh warnings; no rate
limit changes. B9 Build completed all four stepsExit0, but is superseded by the
following user-requested product change and B10 rebuild.

**User decision,7October: no personal photos for students, teachers or other
account roles.** Removed profile photo/file controls, avatar mapping/types and
the unused legacy auth modal's ID-photo controls. Auth responses no longer emit
`avatar_url`; authenticated legacy GET/POST return410 without reading/processing
or writing storage. Existing private object keys/data are preserved, not deleted.
The old upload-avatar test contract is intentionally superseded by this explicit
feature removal, NOT deleted to hide B8's failure. API and browser regressions
now assert no controls/photo requests (including stale cached URLs), closed legacy
endpoints, normal CSRF/auth checks, preserved stored keys, and password-action
hydration. Their final B10 results are pending; no photo upload test is run further.
Biology Extract improvement remains deferred by the user; its recorded strict
fixture failure is not converted into a pass or silently skipped.

### B10 completed focused gates (7October,12:22UTC)

Initial B10 Build Exit1 was a pip-wheel HTTPS read timeout from
files.pythonhosted.org, not a successful build or application failure. The
unchanged retry completed all four stepsExit0 (`build-b10-retry-20261007.log`,
`video-commands-Build-20261007-121451.json`); no pinned version, source check,
TLS verification or test gate was removed to bypass it.
Actual runtime identities after startup:

- API `sha256:57dc02694b7ea45f591dc7e295b0255c8369fe101cba6a599576ad115d48e7ed`
- Celery `sha256:f504512229c4e5e79be3fd6a1a3d494ee347939d92566398a49f0385071abb9a`
- encoder `sha256:e295c4156111fd45f4d2f17ecc82f164196cd68736afb61fb9e6724bced797f7`
- web `sha256:c0f91c63a329d42e42abf997bb8d209e131e06dd98a63a2e0c03a5d08ba68655`

Backend's six stepsExit0. `api-unit-video-20261007-121641.xml`, **361/0/0**,57.460s;
native Expat4/0/0 EACH API/encoder, native FFmpeg6/0/0 on the above encoder,
fresh/previous-head PG migrationsExit0 and real missing-MPU recoveryExit0.
Independent full frontend units **105/0/0**,18files,33.11s wall,
`frontend-no-photos-b10.xml`,Exit0. Lint0,zero errors/three Fast Refresh warnings.

Actual PG/HTTPS/Redis after-fix regression `video-slot-live-after-b10.xml`,
**1/0/0**,1.739s,Exit0: two rotations change the real access credential but retain
one device; eight simultaneous token requests200; a third device429/RetryAfter30;
old/current-other-device URLs403; logout releases only its own family. No mock
clock, waiver or counter erasure. This is admission evidence, not itself media.

Focused native-browser journeys `b10-focused-after.xml`, **5/0/0**,Exit0,
2.9min: teacher/student no-photo UI and closed legacy410; no photo request from
a stale cached URL; delayed identity hydration blocks account actions until the
real bootstrap; dark/mobile publication clears an old error during busy retry,
then publishes via actual PG; actual WebM/HLS playback, byte ranges, seek,
bounded injected segment403/refresh503 recovery and keyboard lesson navigation.
The former automatic-avatar-upload test is superseded by the explicit product
removal; its historical failure remains recorded above, not claimed diagnosed
or passed after an image-upload fix. Full B10 Browser/Integration and all final
scan/load/restore/clean/source gates remain pending; no commit/push yet.

### User pause and resumed full Browser (7October,18:48UTC)

The previous B10 full Browser was explicitly interrupted at the user's request
at12:31UTC, wrapper Exit1. Its log records25 completed successful cases out of80
collected, but no completed browser JUnit was produced. The other55 are
unfinished, NOT counted as passes, failures or skips. Its preflight frontend
JUnit `frontend-video-20261007-122305.xml` independently records105/0/0, Exit0.
No application containers, user programs or data volumes were removed on pause.

B10 source-byte verification before pause returnedExit0:116 files EACH in
API/Celery/encoder and89 web assets/config, zero mismatches. Browser's served web
identity was `sha256:86041d7df8a7196100a3cb4a9ed339998c6356ae9b501bed18c0379984e52fb2`,
not the earlier Build web identity. Original1281 runtime-asset hashes verified
again with zero discrepancies (`original-assets-b10-20261007.log`, Exit0).

On user resume, Docker's engine pipe was missing. `docker desktop start`
returnedExit0 and restarted existing services; no reset, volume deletion or
unrelated-project stop. Actual remote `git ls-remote` still returns
`429848608834c7c012e3b2c9e7fcc4eb71f93ac0` for `fix/queen-p0-handoff`.
Both working and cached diff checksExit0. Current changes remain local/staged,
with no new commit/push. The independent full80-case Browser starts again,
`browser-b10-resume-20261007.log`; its final outcome must be recorded only after
completion. Personal photos remain removed; biology Extract stays deferred.

### Resumed full Browser result and hydration correction (7October,19:23UTC)

The full80-case B10 Browser completed **76/4/0, Exit1,30.5min**,
`video-browser-Browser-20261007-184724.xml`. This is a FAILED release gate.
The JUnit root incorrectly reports3 failures; direct counting of its80
`testcase` nodes shows4 failed cases/0 skips, agreeing with the console.
Report the actual case count, not the inconsistent aggregate attribute.
Student journey failed in the QA preflight's5s synchronous Docker-CLI probe
before navigating the app. Manual grading's cleanup received503 and replaced
the original journey error; the following bootstrap/login-abuse journeys also
received actual503. The API logged Redis-query/release failures at19:08:03UTC;
read-only Redis SLOWLOG metadata showed an EVALSHA lasting209633us, exceeding
the application's200ms socket deadline. Redis had no restart, OOM, rejected
connections or evictions in the subsequent snapshot. That snapshot alone does
not prove why the host stalled or that every503 is fixed. Raw failed traces,
logs and assertions remain; no security counter was erased or limit changed.

A distinct frontend bug was reproduced with the actual client: a150-read
hydration queue kept draining after429/503. Before-fix regression
`hydration-breaker-before-retry-20261007.xml`: **14/2/0, Exit1**, both cases
made150 HTTP calls instead of at most4. The first sandboxed invocation failed
EPERM during Vite realpath resolution, with0 collected tests; it is not included
as an application failure or pass. The authorized unchanged retry collected16.
After-fix `hydration-breaker-after-20261007.xml`: **16/0/0, Exit0**. Expanded
network-outage/account-isolation regression
`hydration-breaker-expanded-20261007.xml`: **18/0/0, Exit0**.

Current local apiClient honors Retry-After, fails queued reads without sending
or automatically replaying them, preserves identity/foreground mutations,
and separates cooldown by auth generation. App displays an explicit partial
course-data warning and manual retry rather than silently presenting missing
assessments as an empty course. The QA Docker probe is one bounded async15s
operation, not a retry/bypass; cleanup's soft204 assertion still FAILS the test
but no longer hides the original journey error. No production Redis timeout,
admission quota, cookie security or real rate limit was weakened.

The initial standalone web build command lacked required
VIDEO_UPLOAD_PUBLIC_ENDPOINT and returnedExit1 before mutation. The retry with
the normal three QA upload-origin variables built/recreated only web/proxy,
Exit0. The subsequent warning-UI build and live expanded browser regressions
must be recorded after completion. Source/clean/full Browser evidence for the
earlier frontend is not reused as proof of the newly changed served frontend.
The resumed original-asset hash check also completedExit0:1281 originals
retained, all hashes match (`original-assets-b10-resume-20261007.log`).

### Focused live retry and a distinct grading race (7October,19:35UTC)

`hydration-live-after-20261007.xml`: **5/3/0, Exit1,2.1min**. Student/teacher
navigation, bootstrap recovery and REAL login429/no-auto-retry all passed.
The new429/503 catalog scenarios collided with the reused student's real
600-read/minute budget across successive152-course runs: traces include actual
additional429, not only the injected response. No counter was cleared or real
429 assertion dropped. These large-account cases now wait the existing READ
window to expire before starting (bounded61s read-only probe); successful
recovery still requires all actual responses, without accepting extra429.

Manual grading exposed a DISTINCT application race rather than a Redis failure:
the cached teacher identity rendered the grader before bootstrap established
the client auth generation. The real grade POST was cancelled as late bootstrap
finished (trace POST19:29:40.479UTC, status-1; bootstrap began19:29:39.314UTC,
1283.703ms duration); the UI showed `Request cancelled` and did not close.
No500 or unsuccessful-grade status was silently accepted. App now gates all
authenticated content/mutations and initial SSE/background widgets until the
matching server bootstrap. A prior verified identity/draft stays mounted during
later temporary refresh outages. The grading harness now creates a separate
synthetic student per run, preserving earlier test/user data; an additional
held-bootstrap case proves no grading action can appear before hydration, then
requires successful real quiz AND homework grade persistence after release.
The rebuilt frontend and nine-case live repeat are pending. No API/native
image, rate-limit policy or PostgreSQL record was reset.

### Nine-case live regression completed (7October,19:50UTC)

The intermediate `identity-grading-live-after-20261007.xml` completed
**5/4/0, Exit1**. Its four failures were QA preparation/instrumentation defects:
the injected course-detail429/503 was not counted by a handler that counted only
assessment responses, and two fresh student registrations used the reserved
`example.invalid` domain rejected by EmailStr (422). The raw failures remain.
The response handler now counts BOTH detail and assessment errors; fresh
synthetic students use `@demo.com`, with the registration response included in
the assertion. No app validation, security quota or success assertion changed.

The corrected full focused repeat `identity-grading-live-retry-20261007.xml`
completed **9/0/0, Exit0,304.670756s**. Each real catalog run had152 enrolled
courses and peak4 assessment requests. Baseline completed152 with no failures;
429/503 scenarios each recorded exactly the single injected failure, sent at
most4 initial hydration requests, did not replay after Retry-After expired,
then completed all152 after the manual retry with auth/me200. Real student and
teacher navigation, bootstrap-outage recovery and actual login429/no-auto-retry
passed. BOTH normal and held-bootstrap UI grading passed, including real essay
and file-homework submission, temporary refresh failure preserving input,
and quiz/homework scores and feedback read back from PostgreSQL.

Served frontend was rebuilt/recreated at the all-content identity guard;
`web/proxy` build/start Exit0. API, encoder, PostgreSQL, S3, original runtime
files and production security/rate-limit configuration remained unchanged.
This nine-case success does NOT replace the failed full80-case gate: the final
full suite now contains83 cases and must still run on the final code/images.
No new commit, push or external deployment has occurred.

### Continuation on8October: native candidate and bounded bootstrap

Docker's Linux pipe was unavailable after the session interruption. Normal
`docker desktop start` returnedExit0; the existing API/encoder/web are running
healthy on their previous immutable images. No reset/deletion/recovery from a
different data source occurred. The previously launched native candidate
completed at19:57:34UTC on7October, **Build Exit2**, no native tests collected:
an additional old5.5.0 `AmbigClassifier` call still expected a pointer after the
upstream security change made `Class` a value-initialized std::array. The
failed source/log and command result are retained, OOM=false.

`tesseract-stable-callsite.patch` preserves that pointer contract via `.data()`;
it does not change any added count/size guards, capacities or deserialization
checks. The exact6-line-context patch is SHA-pinned at
1646a66c1e340b6f71fa4852945b77d42c91189d8599a6e1746128cd4869ceab,
applied by `git apply --check`, alongside the six official upstream patches.
The NEW bounded candidate Build is in progress; no application image or
recognition model has been replaced. Signed stable indexes now offer xz/liblzma
5.8.1-1+deb13u2 and installed it ONLY inside that disposable builder. Current
application-package update assessment must be repeated independently.

A separate code review found bootstrap's temporary-unavailable effect retried
forever, including429. `bootstrapRecovery.ts` now permits at most three timed
probes for classified transport/408/502/503/504 failures, respects Retry-After
without shortening a long cooldown, and never timer-replays429/policy errors.
App waits for the previous bootstrap to finish before scheduling a retry,
preserves cached identity and data, and keeps explicit manual recovery.
`bootstrap-recovery-unit-20261008.xml`: **6/0/0, Exit0**. The new persistent429
and503 browser regressions must first reproduce on the OLD served frontend,
then run after rebuilding the changed frontend. These local edits are NOT yet
served-browser proof or a replacement for the final full suite (now85 cases).

###8October completed focused evidence and security intake (04:18UTC)

The candidate's library/CLI compiled after the pointer port, but Build returned
Exit1 during QA compilation: `fileio.h` was missing from includes, so0 native
tests were collected. The first test-only repeat still failed before collection:
the real header is in `src/training/unicharset`, not just `training/common`.
Both raw failures remain. Correcting only the runner include path produced
**26/0/0, Exit0**, `tesseract-native-tests-20261008-040955-443516/`.
Moving the exact manifest/context port/native controls into shared application
build assets and repeating against the SAME library also produced26/0/0,
Exit0, `tesseract-native-tests-20261008-041546-836167/`. No test body/assertion
was removed, skipped, or weakened; these are actual compiled-library tests,
NOT an ASAN run. Shared patch applicability/signature Prepare returnedExit0,
`tesseract-backport-20261008-041658-060acb/`; Prepare is not a build.

`ocr-runtime-20261008-041158/`: unchanged original SHA/model/parser/reference
comparison, ALL7 parsed outputs identical. Baseline and candidate EACH6/1/0,
Exit1; biology still10 questions/7fully-matching/CER0.008645533141210375.
This proves no measured regression on those fixtures, not perfect OCR.

Full frontend units **115/0/0, Exit0,19files,30.07s**; full lintExit0 with
0errors/3reviewed Fast Refresh warnings; full host buildExit0 with video634.65kB
chunk warning retained; npm auditExit0,0known alerts/353dependencies.
OLD served frontend strengthened20s persistent-bootstrap proof completed
0/2/0, Exit1:429 made4 requests and503 a fifth automatic attempt. A shorter
15s503 observation had falsely passed during backoff; that raw run is retained,
not closure evidence. After web/proxy rebuild/startExit0, all network/role
focused tests completed **6/0/0, Exit0,118.017382s**:
`bootstrap-policy-live-after-20261008.xml`. Persistent429 now1 request,
503 now initial+3 bounded probes then stop, both recover through one explicit
manual request200. Real login429/no timer replay, transient bootstrap recovery
and both role journeys pass. Same-account logout cleanup is a defensive
improvement: that extended journey ALREADY passed on the OLD served image,
so no reproduced logout-scope vulnerability is claimed.

Fresh signed stable package assessmentExit0 at04:11UTC found exactly one
runtime upgrade: liblzma5u1→5.8.1-1+deb13u2; OpenSSL remains authenticu3.
Shared production security-backport build and reviewed apt-index refresh are
now in progress. Models' original SHA256 were recorded before it. Application
adoption, full Browser85/Integration59/load/restore/fresh scans/source/clean
evidence are NOT inferred from these focused results. No commit/push/deploy.

###8October discussion repair and application native build

Actual Docker HTTP unit reproduction of lesson comments completed5/10/0,
Exit1: unpaid/enrolled students and unrelated same-institution teachers were
not rejected; non-string bodies and invalid parent UUIDs could produce500;
grandchildren were accepted but hidden. Strict typed requests, existing lesson
entitlement/owner checks with the preserved same-institution boundary and
top-level-parent validation now pass expanded21/0/0, Exit0. This repeat mounts
current application source read-only; final built-image/live PostgreSQL proof
must run separately. The new integration case checks cookie/CSRF, genuine
entitlement grant/revocation and saved parent UUID/count directly in PostgreSQL.

Frontend rejected-write/fake-ID reproduction completed7/2/0, Exit1. The new
`LessonDiscussion` component owns loading, drafts, sorting and persistence;
it only displays success after an actual saved UUID, retains failed drafts,
allows manual retry, prevents duplicate pending writes, ignores stale lesson/
account outcomes and reports GET failure rather than inventing an empty list.
Unsupported fake like counts were removed. No personal portrait feature added.
Expanded component repeat13/0/0, Exit0; current lintExit0 (0errors/3 retained
reviewed Fast Refresh warnings); TS/Vite buildExit0,17.09s,630.74kB video chunk
warning retained. Those are focused/current host results, not the complete
frontend or served-browser acceptance gate. The protected real-video browser
journey now also tests failed POST retention, explicit retry, actual parent/
reply UUIDs, navigation read-back and axe in failed/saved discussion states.

The first actual API/encoder pipeline Build completedExit0. The production
builder independently compiled the genuine5.5.0-1+chemistry2 backport and ran
its mandatory26/0/0 native security tests; signed stable runtime refresh
installed liblzma5u2. Application/discussion source changed while that first
build was running, so a complete second Build is running with expensive native
layers cached. No mixed-image final acceptance or fresh-scan success claimed.
Original strict biology failure remains deferred, not relabelled passed.
