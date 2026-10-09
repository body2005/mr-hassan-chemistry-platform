# Local review progress — 9 October 2026

Checkpoint, **not release approval**. Branch `fix/queen-p0-handoff`, code now
committed/pushed at `6796750664151e180054018ea4fdc97242d46bcb`, independently
matched by remote Git and GitHub API (Exit0). The next local continuation below
is prepared for a normal push with `[skip ci]`, explicitly requested by the user. The older
`chemistryprodlocal` runtime is stopped. Work and tests target `chemistryaudit2`.
Do not use earlier reports as evidence for this code or GitHub upload.

## Latest checkpoint (read this before historical entries)

### Local-only continuation; no new GitHub execution requested

User excluded Vercel management and authorized normal pushes, then explicitly
asked for local work and upload only, with no GitHub execution. No Vercel
settings/deployment/rollback actions. Requested cancellation of existing run
37928630587 (Exit0); no dispatch/rerun. Next commit uses `[skip ci]`; required
checks are not bypassed/declared passing and may remain Pending.

Read-only evidence from that earlier run: frontend/secrets succeeded. Backend
JUnit469 cases:468P/1F/0E/0S,69.706s,Exit1. Native security regression rejected
host Expat2.6.1/Python bundled2.8.5. Repaired workflow builds production API and
its existing QA-only layer instead of using host Python. Every original test,
migration and audit remains; production runtime does not gain test tools.
Local raw-config-ID `FROM` attempt failed Exit1, correctly reproduced before
acceptance. Corrected reference is a job-local tag with immutable-ID checks
both sides; Docker RUN uses recorded IDs. Local QA-layer buildExit0 on existing
clean API42adb4da… (no native rebuild). Targeted native/CI guards4P/0F/0E/0S,
0.628s,Exit0, `ci-backend-environment-20261009.xml`; no full suite repeated.

Added safe upstream address/connect/header/response timings to3 Nginx configs;
error_log remains disabled because raw errors can expose playback queries.
New isolated real-Nginx cases200/503/premature-close502:3P/0F/0E/0S,2.592s,
Exit0, `proxy-diagnostics-20261009.xml`. Query/cookie/Authorization sentinels
absent from logs. UUID fixture containers/network removed, no app service stop
or data volume removal. Original sporadic logout502 remains undiagnosed; this
is observability plus a reproduced fixture cause, not proof of its repair.
Web-only build/up and web/proxy nginx validation/reloadExit0; existing JS assets
were cached identical. Handoff HTTPS200, synthetic teacher/student each login200,
identity200,logout204 with trusted CA. No token logging/reset. Native API/encoder
unchanged, previous latest CVE scans retained, not repeated for config-only work.
Instructions and before/after table: `QA_HANDOFF_2026-10-09.md`.

### Post-push verification / unexpected existing Vercel automation

Push advanced remote4298486 to6796750 (the two existing local commits plus the
new111-file repair/evidence commit). Current checkout/index secret scan0;
separate network-disabled Gitleaks of exactly the3 unpublished commits0,
no leaks, `clean-results-20261009-115723/gitleaks-unpublished.json`.
`push-verification-20261009.json` records independent Git/API SHA equality.
Remote Actions run37928630587 began automatically; secrets job succeeded,
other jobs in_progress at inspection, not declared green.

The pre-push statement "no deployment" must not be used as post-push evidence:
the repository's EXISTING `vercel[bot]` integration automatically created
deployment6960376648 for this SHA, state success, named environment Production,
BUT GitHub `production_environment=false`. This is not proof the production
domain was changed and not proof of external functional correctness. Recorded
URL `https://mr-hassan-chemistry-platform-ptgtyo6db-body19.vercel.app`.
No independent deploy/merge/rollback/settings change was requested by this
agent. Further pushes were initially stopped pending user direction. The user
subsequently excluded Vercel management and authorized ordinary GitHub uploads;
the newer local-only/skip-ci instruction above governs this continuation.

### Targeted-only continuation — user clarification, 9 October

Clean BuildOnly controller completed Exit0. Its9 records comprise6 successful
command/check steps and3 explicit NOT RUN records (whole lint/frontend/backend
unit suites), NOT pytest skips. Evidence `clean-results-20261009-115723/commands.json`.
API clean-build image `sha256:42adb4da5f99ace5bb4cc99f6f7eab21ca864c69fc4253047547ce03c54a4f5c`,
runtime UID10001:10001, was not deployed or substituted for the scanned/tested
API659e1c3f…. Current API remains healthy. Latest ESLint on the final new
reading-matrix file returned0; no whole lint/functional suite repeated.
Only report documentation was edited after the clean export; application and
QA source files remain the exported revision. New raw scan evidence below
continues to block release, independently of the successful clean build.

Clean export `clean-gate-20261009-115723` / result folder
`clean-results-20261009-115723`: index export0, redacted Gitleaks0/no leaks,
npm ci0 (automatic audit0 vulnerabilities), frontend build0 and90 built asset
hashes match the working output exactly. API clean build is still running;
do not mark it passed yet. No complete lint/unit suite was rerun. Additional
read-only source check `clean-api-text-equivalence-20261009.json` compared124
app/script text files:107 raw byte differences are ONLY CRLF versus LF from
Windows checkout policy, zero other content differences. This is canonical
text equivalence, not raw API byte identity or a new functional-suite pass.

Fresh actual-image scans completed after the final selected browser cases:
Scout3High/0Critical each, rawExit2/controller1,
`scout-video-{api,video-worker}-20261009-115314.sarif`;
Trivy63High API/79High encoder,21/37 unique IDs, rawExit1/controller1,
`trivy-20261009-115547/`. Combined union38 unchanged reviewed CVEs, no new ID.
Current API659e1c3f… and encoderb566cdcd… identities are in the scan manifests.
No findings suppressed. Raw image gates remain OPEN, not a deployment approval.
The Windows Scout temporary archive lock warnings did not prevent the reports.

User subsequently granted workflow scope. The actual read-only auth check now
shows gist/read:org/repo/workflow; no token is recorded. Permission is no longer
the known upload blocker. A commit/push and independent remote-SHA check are
still required before describing this working tree as uploaded.

`trusted-browser-20261009-114742/browser.xml` and `command.json`: Exit0,
2 passed/0 failed/0 errors/0 skipped,172.893215s.
Only the two failed student cases were selected. Actual browser batched video
responses202, essay16px, course/video/quiz/homework readings at320x720 and
640x360, Cairo/RTL, scale2 and real visible hit targets all passed in both
themes. The helper now scrolls the nearest real overflow container rather than
the underlying window when homework is in a fixed independently scrollable
page. This was a harness error, not a waived layout failure. Four earlier
passing guest/teacher cases were not repeated. The six-case reading scope is
covered across recorded selected runs, not a claimed fresh full99-case run.

Database-only new-schema restore completed Exit0:
`video-storage-20261009t115157z-d18ba302.json`,12 command steps all0.
Fresh PostgreSQL volume `chemistryaudit2_restore_pg_20261009t115157z-d18ba302`,
restore into an empty database,53 public tables/54,192 rows compared exactly,
zero mismatches, restored head `f4a6c8e0b2d4`. Original writers were restarted,
actual trusted HTTPS readiness recovered, restore server stopped and volume
preserved. Original and historical restore volumes were not deleted. This is
new-schema database evidence, NOT a repeat/new claim of full S3/application
disaster recovery. The earlier25-step full storage proof keeps its old version.

Continuation after the user's explicit no-repeat clarification:

- `trusted-browser-20261009-113249/browser.xml`: selected3 cases only,
  Exit1,1 passed/2 failed/0 skipped. Light teacher now passed, including
  logout204; the earlier isolated502 still has no proven root cause.
- Light student reached homework but its test aligned a control under a sticky
  header during pinch zoom. Keep this distinct from an application layout bug;
  the helper now scrolls to the visual viewport centre and records actual bounds,
  hit target and the200% screenshot before asserting, without CSS mutation.
- Dark student exposed a second real telemetry500: first events may have no
  video duration. SQLAlchemy's INSERT default had not yet populated pending
  `completion_percent`, so comparison with100 raised TypeError. Explicitly
  initialize the new row to0.0. A single new regression reproduced500,
  `telemetry-no-duration-before-20261009.xml` (0/1/0, Exit1), then passed
  `telemetry-no-duration-after-20261009.xml` (1/0/0, Exit0). Previous passing
  unit/integration suites were not rerun.
- Rebuild `video-commands-Build-20261009-114123.json`: all four controller
  steps Exit0. Source identity check matches127 files each API/worker/encoder
  and91 served web/config files, zero mismatches. Only the two still-failing
  student reading cases are selected for the next browser run; all four passing
  guest/teacher reading cases are excluded, not marked skipped or rerun.
- Retain the completed25-step full S3/database/application restore from
  `video-storage-20261006t152750z-fd458cec.json` (all Exit0), and completed
  1/5/10x180s load `load-20261006T160047Z.json` as historical evidence only.
  Do not repeat them automatically on an unrelated telemetry/style change.
  New `video-storage-drill.ps1 -DatabaseOnly` isolates the new schema/data
  restore proof without another S3 copy or browser/encoder journey. Default
  full restore behavior remains unchanged.
- `check-clean.ps1 -BuildOnly` is an explicitly limited index export, secret
  scan, fresh install/build and asset-equivalence check. It records lint and
  whole unit suites as NOT RUN, not passing or pytest-skipped. Default full
  mode and CI gates remain unchanged. This accommodates the user's no-repeat
  instruction without claiming a fresh complete clean-checkout test gate.
- GitHub read-only check still sees remote4298486 and scopes gist/read:org/repo
  only. Workflow scope is missing. Do not change account permissions, delete
  the workflow, or claim a push; user was asked to grant it themselves.

Latest runtime after the duration repair:

| Service | Actual image ID |
|---|---|
| API | `sha256:659e1c3f204d3b0b080ba48072cc310e20a23061954a3273b88dadd338f06d14` |
| Celery worker | `sha256:dd573cef3785d5278d934eaf40d1cea43db8a03ca966b5e11dcfb20814f824cb` |
| Encoder | `sha256:b566cdcd0f4d5e499b2a40356c1acca7148cd03d2e274d4cbbe30b0f8bebe8e2` |
| Web | `sha256:e9a0edb94c55ae7e81b71630493127ac615939ab14188d7f9250f0f4d63d018e` |

Older full-suite counts below stay attached to their original images. The new
image is not automatically a464/213/93-pass image. Native assertions embedded
in Docker build still execute as part of constructing the image; no separate
repeat native/functional suite was requested or launched.

After rebuilding (`video-commands-Build-20261009-112802.json`, Exit0), the new
PostgreSQL cases passed3/0/0, Exit0 (`telemetry-postgres-after-20261009.xml`):
concurrent distinct batches202/202, duplicate replay202/202 with exactly one
accepted batch, and explicit completion202/200. Each retained one progress row,
exact event counts/watch-time totals and completion100 when applicable.
Targeted lint of `MyCoursesView.tsx` and `reading-matrix.spec.ts` returned0.
No complete suite was rerun.

The first post-build byte check passed127 files each API/worker/encoder but
failed web equivalence because host `apps/web/dist` still contained the prior
build. It correctly stopped before browser testing. Regenerate the host output
from the new16px source before rechecking served asset equivalence; this is
not evidence that old unit/browser counts apply to the new web image.

The user clarified: test new/previously unverified cases and the parts affected
by actual new repairs, not repeated whole passing suites. Do not rerun the93
browser/213 frontend/464 backend suites or the60-case historical integration
suite without a demonstrated new dependency. Existing counts remain associated
with their actual images, not relabelled onto a later build. The user authorized
resuming the previously interrupted six-case reading matrix.

`trusted-browser-20261009-111748/browser.xml`: Exit1,3 passed/3 failed/0 skipped.
Both guest themes and dark teacher passed. Light teacher reading itself passed,
but real logout cleanup returned502 once (web and proxy privacy logs confirm
upstream502,5.8s). Later logouts204 do not establish its root cause or fix it.
Both student cases found the essay input14px instead of the requested16px.
Browser video traffic additionally exposed a real telemetry500; server logs
identified `uq_lesson_progress_student_lesson`, not an upload/decoder failure.

New `test_telemetry_batch_review.py` initially had short client-event identifiers
(fixture error,4 failures, preserved `telemetry-batch-before-20261009.xml`).
After correcting only the fixture, old code reproduced3 failures/1 pass with
500 for multi-event batches (`telemetry-batch-before-valid-fixture-20261009.xml`).
`SessionLocal.autoflush=False` meant repeated events inserted multiple pending
progress rows. The repair reuses a per-lesson pending row within each batch and
locks the existing student user row across telemetry and explicit completion.
This also serializes first inserts/deduplication across PostgreSQL API workers.
Source-mounted targeted checks passed10/0/0, Exit0,
`telemetry-batch-after-20261009.xml`:4 new tests plus6 directly affected existing
telemetry/completion cases, not a full Backend rerun.

New PostgreSQL `test_telemetry_batch_live.py` reproduced3/3 failures before the
runtime repair: distinct batches500/500, same-batch replay500/500, completion
overlap500/200 (`telemetry-postgres-before-20261009.xml`). Post-build outcomes
are pending. The essay input now16px/line-height1.6, preserving Cairo/theme/RTL.

An earlier reading-runner failure was a test-coordinate issue: Playwright trial
click kept trying desktop-coordinate scrolling inside a pinch viewport. That
attempt was stopped (raw143), not accepted as application failure/success.
The helper now verifies actual visualViewport scale2 and a visible DOM hit
target after actual scrolling, without CSS mutation or a claimed submitted
action at200%. No physical-device/desktop-toolbar-zoom equivalence is claimed.
The new runner `-Grep` option records selection in its manifest so only failed
new cases can be rerun. The three newly passing cases will not be repeated.

### Resumption and user test-stop instruction — 14:10 Cairo

The300-minute allowance renewed (initially0% used). A later live reading was
6% used/94% remaining; weekly16% used/84% remaining. Stop at5% remaining as
previously requested; these percentages are account-wide, not elapsed hours.

Docker Desktop was initially stopped, so the first reading runner build exited1
before tests. Starting Docker Desktop without resetting data brought back the
existing QA services. A new test-only file `reading-matrix.spec.ts` and its
run instructions were added; no application image/source was changed. The QA
browser runner built and announced six cases. The user then requested an ETA
and no further repeated tests. Its exact container
`chemistryaudit2-browser-20261009-110826` was stopped explicitly (stop Exit0);
raw runner Exit143/controller Exit1, recorded under
`trusted-browser-20261009-110826/command.json`. No final JUnit totals were
accepted; these additional reading cases remain UNVERIFIED, not passing.
The separate test-file lint process was also interrupted (Exit1), not classified
as an application lint defect. Existing completed gates below are retained;
do not rerun them or start additional test workloads without resolving the
user's latest test constraint. Stopping this runner did not stop the application
or delete data. Runtime API/web/proxy/Redis identities matched the preceding
completed browser run throughout this interrupted attempt.

GitHub authenticated successfully in the authorized read-only check, still
with gist/read:org/repo scopes only, without workflow. The earlier sandboxed
auth check was not evidence of an invalid real token. No account permission
change, commit, push or deployment was performed.

The sections below form an append-only investigation history; earlier pending
or failing statuses are not silently erased. Latest rebuilt application images
and source/hash equivalence are recorded under **Rebuilt current runtime**.

| Completed preceding-image gate (retained, NOT rerun) | Exit | Passed / Failed / Skipped | Evidence boundary |
|---|---:|---|---|
| Backend unit/protection | 0 | 464 / 0 / 0 | `api-unit-video-20261009-055527.xml`,73.321s, additional assignment repair included |
| Native Expat, API + encoder | 0 each | 20 / 0 / 0 each | Same Backend command manifest |
| Native FFmpeg provenance/config | 0 | 6 / 0 / 0 | Same Backend command manifest |
| Actual PostgreSQL migrations + lost S3 multipart | 0 | Script checks, not pytest counts | `video-commands-Backend-20261009-055527.json` |
| Real PostgreSQL concurrent legacy assignment publication | 0 | 1 / 0 / 0 | `assignment-publication-live-20261009-055718.xml`,4.167s |
| Ten affected browser journeys before additional assignment repair | 0 | 10 / 0 / 0 | Historical `trusted-browser-20261009-052620/browser.xml`,512.952s; not transferred to new API image |
| Complete frontend unit suite | 0 | 213 / 0 / 0 | `frontend-video-20261009-055740.xml`,32 files,38.49s terminal duration |
| Current frontend lint + build | 0 each | 0 lint errors,4 development Fast Refresh warnings | `video-commands-Browser-20261009-055740.json`; video chunk warning retained |
| Previous complete93-case browser attempt | Interrupted: raw143/controller1 | 37 completed cases observed; no final suite counts | `trusted-browser-20261009-053845/command.json`; stopped deliberately to repair newly reproduced assignment validation defect below, not a passing gate |
| Complete browser gate after assignment repair | 0 | 93 / 0 / 0 | `trusted-browser-20261009-055915/browser.xml`,1891.627s; same API98dfff50/web90cae3d9 throughout |
| npm audit after complete browser run | 0 | 0 vulnerabilities | `video-commands-Browser-20261009-055740.json` |
| Encoder outage/crash recovery | 0 | Script checks, not pytest counts | `video-commands-Recovery-20261009-063259.json`; original bytes match, range206, one ready generation |
| Final security/integration/storage/load/clean export | Pending | Do not transfer historical counts | Release remains NOT READY |

No fixes in this checkpoint are newly committed or uploaded. Remote
`fix/queen-p0-handoff` was verified at `429848608834c7c012e3b2c9e7fcc4eb71f93ac0`;
local HEAD is still `0c24a2f` with two existing unpushed commits plus uncommitted
repairs. Local Docker testing is not external-server testing or deployment.

### Additional assignment publication repair (supersedes previous runtime)

The preceding completed Backend/browser results used API `ebeb4c6` and encoder
`90c409b`, before this additional repair; they are historical, not the final
gate for the new application image. The full93-case browser run was stopped
after37 completed successes to avoid presenting a known-invalid build as final.

`AssignmentCreateRequest` accepted whitespace because its minimum length was
checked before service trimming. Legacy publication also lacked stored-content
validation. Reproduction on the old runtime accepted a two-space prompt with
trimmed length0. New tests reproduced12 failures before the repair.

`schemas.py` now trims before validation. `platform_service.py` validates title,
prompt, finite positive score, date ordering and course/lesson scope before
publishing a locked draft; invalid drafts retain their state and fields.

| Assignment regression command/evidence | Exit | Passed / Failed / Errors / Skipped |
|---|---:|---|
| Old QA image + new regression tests; `assignment-publication-before-20261009.xml` | 1 | 1 / 12 / 0 / 0 |
| Source-mounted repair + existing review suites; `assignment-publication-after-20261009.xml` | 1 | 61 / 1 / 0 / 0; fixture timezone comparison defect, retained evidence |
| Correct persisted-value fixture comparison; `assignment-publication-after-fixed-fixture-20261009.xml` | 0 | 62 / 0 / 0 / 0; 6.699s; not deployed-image proof |
| `run-video.ps1 -Stage Build -Project chemistryaudit2`; `video-commands-Build-20261009-055206.json` | 0 | Build/startup, not pytest counts; named data volumes retained |
| `verify-runtime-source.ps1`; `runtime-source-20261009T055516Z.json` | 0 | 127 files per API/worker/encoder and91 served web files; zero mismatches |

Actual rebuilt API `sha256:98dfff500c6c91f93307b5b2d8d96beae4f2effbe0c593687003afdff33a1ab4`,
worker `sha256:ababbab217561636096a65abeca67ecf015597172bfb3b83669fc33d74c72cce`,
encoder `sha256:df79b906bc9891f5371b5bba69570a6996c5472a87d1bd53dc99ae844ac80d7c`,
web `sha256:cbef9d7cd8d6b16871a4d8da7c1428edd114b7f4b7cc3dfacb979cf99c822e0a`.
Backend completed Exit0: `video-commands-Backend-20261009-055527.json`,
464 passed /0 failed /0 errors /0 skipped,73.321s. Native Expat20/0/0 per API
and encoder, FFmpeg provenance/config6/0/0, all Exit0. Fresh/e8/f3 PostgreSQL
migrations preserve9 historical rows at headf4a6c8e0b2d4. Lost multipart recovery
again returned missing200/expired,completion409,newintent201,logout204,zero500.

The new live PostgreSQL regression completed1/0/0 Exit0,4.167s,
`assignment-publication-live-20261009-055718.xml` with its command/image manifest.
Blank creation returned422 without insertion. Two independent HTTP clients
released by a barrier concurrently requested publication of the test's invalid
legacy draft: both400, unchangedDRAFT/prompt, no500. Correcting only that test
row then published200 with unchanged meaningful content. No existing user
content was modified and no authentication counter cleared. The final complete
browser gate has now started; prior ten-case success is historical.

The Browser controller's frontend presteps all passed on the current source:
lint0 errors/4 Fast Refresh warnings, buildExit0,213 unit cases32files with no
failures/skips. Its web recreation changed the attestation identity to
`sha256:90cae3d97a4d766ae463192b3cebcd1ba12d4fc5465d132ed5619fb3bb340d10`.
`runtime-source-20261009T060112Z.json` Exit0 verifies127 files per API/worker/
encoder and91 served web assets/configs with zero mismatches. No application
source is being edited during this full93-case run.

`gh auth status` rechecked Exit0: account authenticated, but scope `workflow`
still absent. This is the previously observed upload blocker, not a new push
attempt. The user was asked to complete the required authorization themselves;
no token was printed, no auth scope changed by the agent, and no workflow
removed to bypass the restriction.

### CI evidence retention repair during the browser run

Application/QA-browser source and its images remained unchanged. Read-only CI
inspection found that `quality.yml` uploaded only the former browser folders,
not `trusted-browser-*/browser.xml`, its immutable-image command manifest, or
the current screenshots. These three narrow paths were added, without uploading
trace ZIPs, session/header state, inbox data or keys. A new offline regression
`scripts/qa/tests/test_ci_evidence_paths.py` also runs in CI and accounts for
recursive directory selection, not just exact filename matches.

Against the preserved pre-repair workflow:1 passed/2 failed/0 skipped, Exit1,
`ci-evidence-paths-before-20261009.log` and its SHA-bound command manifest.
Repaired workflow:3/0/0 Exit0; the additional recursive-directory/header guard
rerun also3/0/0 Exit0,0.005s,
`ci-evidence-paths-after-directory-guard-20261009.log`. These are offline
configuration regressions, not proof of a remote Actions run. `gh run list`
returned an empty list Exit0 for this branch. Upload remains blocked by the
missing `workflow` authorization; no account permissions were changed.

`source-snapshot-20261009-062108.json` records469 scoped source/QA/infra files
after this harness-only repair, excluding runtime/data/docs/unrelated projects.
Its eventual verification must not be described as covering time before the
snapshot. Application/source equivalence before the browser was separately
verified by the runtime manifests above.

### Complete current-image browser gate completed — 09:31 Cairo

`run-video.ps1 -Stage Browser -Project chemistryaudit2` completed Exit0, all
controller steps0 including npm audit0 vulnerabilities and diff check.
`trusted-browser-20261009-055915/browser.xml`:93 passed/0 failed/0 errors/0 skipped,
1891.627s. `command.json` binds API98dfff50,web90cae3d9,proxy32463212,Redisff02b58f
and runner6721cedf; all application image identities remained unchanged.
This closes the six earlier browser failures on the current application image;
the earlier transient admission503 was not reproduced, not assigned a proven
cause. Real limits/timeouts were not relaxed and counters were never erased.

Passed include the real direct/resumable video pipeline, malformed replacement
rejection, HLS/play/seek/ranges/private-link revocation, multitab401/network/
429/503 recovery, persisted comment/reply, manual grading, registration/reset,
receipt approval/ownership, source-review publication, dark/mobile loading/error
states and185-enrollment bounded hydration. Normal hydration used3 metadata/
assessment reads;429/503 recovery used4,peak1 assessment request and explicit
manual retry after a visible failure, without automatic replay after Retry-After.

`source-verification-20261009-063121.json` Exit0:469 scoped source files unchanged
since the06:21 snapshot, HEAD unchanged; this does not claim a whole-run host
source snapshot taken before06:21. Runtime byte checks cover the application
images separately. No application source changed during the93-case run.

Reading coverage still needs explicit landscape/200% evidence; the93-case suite
must not be presented as already covering that matrix. Encoder recovery now
starts serially, after the browser exited. Final full integration/restore/load/
fresh scans/clean export/remote CI remain open.

### User-requested usage checkpoint — 09:41 Cairo

Work is paused at the user's requested safety threshold. The account usage tool
reported the300-minute window95% used (5% remaining), resetting9 October2026
at12:51:41 Cairo; the weekly window was15% used (85% remaining). These are
account-wide percentages, not guaranteed minutes/messages of remaining work.
On resumption, check live usage before starting another substantial gate and
stop again at5% or less remaining, preserving a report/checkpoint margin.

The last completed QA command was
`run-video.ps1 -Stage Recovery -Project chemistryaudit2`, Exit0,
`video-commands-Recovery-20261009-063259.json`. Its output reported actual encoder
outage queueing and a hard stop after FFmpeg was observed: crash retry attempts2,
one ready generation, prior generation playable during outage/crash, range206,
original SHA256 matching, recovery63.441s. The45,835,131-byte fixture was uploaded
privately to S3; this is not upload-gateway load/capacity evidence. These are
script assertions, not an invented pytest Passed/Failed/Skipped total.

Read-only `docker ps` after completion returned Exit0: all ten chemistryaudit2
services running and healthy, including the recovered encoder. An initial
sandboxed Docker query was denied; the authorized read-only retry succeeded.
No additional QA gate, application edit, staging, commit or push started for
this checkpoint. All existing local changes and unrelated files are preserved.

Resume with the missing explicit landscape/200% reading tests, then isolated
storage backup/restore, complete integration on the current image (including
the new concurrent assignment regression), realistic staged load, fresh raw
security scans and clean-index export verification. Keep these workloads
serial. The prior full browser gate93/0/0 and frontend213/0/0 remain completed;
do not rerun or relabel historical gates unnecessarily. GitHub workflow-scope
authorization/remote CI, external-server TLS/CDN/DRM and remaining unaccepted
scanner findings are not cleared. No release readiness claim or deployment.

## Repairs reproduced and tested in this continuation

| Defect | Before | Repair / source | After |
|---|---|---|---|
| Blocking synchronous storage SDK on async upload routes | Two failing material-upload regressions: no heartbeat during SDK transfer; cancellation committed instead of aborting | `core/storage_async.py`, `services/lesson_materials.py`, `api/routes/platform.py`: offload file transfer, shield/drain it on cancellation before compensation or staging deletion; material, video and assignment upload paths | Three storage regressions pass, including repeated cancellation and SDK failure. Complete API unit suite433/0/0 and full unchanged-size live integration60/0/0 pass; warm-process/final-load recheck remains. |
| Empty/stale toast announcement competes with page status | Toast suite 3 passed / 1 failed | `components/ToastProvider.tsx`: keep the live region, expose status only with a message; clear it on final dismissal or action unmount | 4 passed / 0 failed / 0 skipped |
| Manual editor's Arabic choice labels rejected by publication validation | Publication validation 9 passed / 1 failed; serializer 4 passed / 1 failed | `services/assessmentPublication.ts`, `mcqOptions.ts`, `lmsService.ts`: validate canonical Arabic/Latin aliases, avoid allocating aliases twice, serialize A–Z API keys without modifying editor/OCR evidence | Selected validation/serialization/option suite 19 passed / 0 failed / 0 skipped. Actual browser publication still pending. |
| Duplicate publication warning implies ancillary work succeeded | Duplicate toast plus persistent banner visible in source; live reproduction pending | `views/QuizGeneratorView.tsx`: one persistent/dismissible result near publication, no duplicate toast; dismissal only says the assessment was published, not that calendar/mail succeeded | Full frontend units and build pass. Existing browser notification-outage case strengthened to require one warning and no retry upon dismissal; not run yet on final frontend image. |
| QA request client resolves localhost inside its own container | Trusted TLS case: 0 passed / 1 failed, API connection refused although browser accepted the installed CA | `tests/qa/localhost-routing.cjs`: route both callback and Promise DNS APIs to the Docker Desktop gateway, retaining localhost URL/hostname validation | Trusted TLS case 1 passed / 0 failed / 0 skipped, including separate untrusted-certificate rejection in both browser and API client. No Windows trust-store or ordinary-browser warning bypass. |

## Commands and raw evidence

All paths below are local evidence under `.qa/audit2`; do not commit private
traces, inbox data, session cookies, signed URLs, keys or synthetic passwords.

| Command / gate | Exit | Passed / Failed / Skipped | Evidence |
|---|---:|---|---|
| `run-video.ps1 -Stage Build -Project chemistryaudit2` | 0 | Build/startup gate, not test count | `video-commands-Build-*.json` |
| `run-video.ps1 -Stage Backend -Project chemistryaudit2` | 0 | API **433 / 0 / 0**; native Expat **20 / 0 / 0 each image**; actual FFmpeg provenance/config **6 / 0 / 0** | `api-unit-video-20261009-032406.xml`, `video-commands-Backend-20261009-032406.json` |
| Fresh / previous PostgreSQL migrations in Backend gate | 0 | Single head; fresh + e8 review head + f3 previous head pass; 9 historical rows remain unchanged and new evidence columns NULL | Same Backend command manifest |
| Actual PostgreSQL/S3 missing multipart recovery in Backend gate | 0 | missing 200/expired; completion 409; new intent 201; logout 204; server 500 count 0 | Same Backend command manifest |
| `npm run test -- --maxWorkers=1 ... frontend-review-batch4.xml` | 0 | **191 / 0 / 0**, 29 files; 31.26s | `frontend-review-batch4.xml` |
| `npm run build` after Arabic serialization / publication-feedback repairs | 0 | Build gate, not test count | Terminal output; chunk-size warning remains, not suppressed |
| `npm run lint` after latest application repair | 0 | 0 errors, 4 Fast Refresh export warnings | ConfirmWizard, ToastProvider (2), i18nContext; development reload warnings, not runtime failure proof |
| `run-trusted-browser.ps1 -Build -SpecPattern tests/qa/trusted-tls.spec.ts` | 0 | **1 / 0 / 0** | `trusted-browser-20261009-032952/browser.xml`; later runner metadata enhanced to capture actual target images |
| `check-stable-security.ps1` | 0 | Package-query gate, NOT CVE scan | `stable-security-20261009-034902.json`: actual API and encoder IDs, refreshed official stable/security candidate metadata |
| Current QA browser image, `playwright test --config playwright.qa.config.ts --list` | 0 | 92 cases collected before the additional manual-Arabic publication case; collection is NOT execution | Container collection output; rebuild runner after later spec edits |
| Current frontend Docker build (without runtime replacement yet) | 0 | Build gate, not test count | Built image `sha256:c6706132005546ea5f43b16b0a9d49e0cb90c8108a46c95c0bf23389f6c9b0f7`; runtime still awaiting controlled recreation after integration |
| `run-video.ps1 -Stage Scan -Project chemistryaudit2 -ApproveScout` | Wrapper 1; EACH scan 2 | EACH API/encoder **3 High / 0 Critical**, 2 vulnerable packages; NOT a passing gate | `scout-video-{api,video-worker}-20261009-040022.sarif`, `video-commands-Scan-20261009-040022.json`; exact tested API/encoder IDs below |
| `git -c core.safecrlf=false diff --check` | 0 | Whitespace gate, not test count | Recheck again after final changes |
| PowerShell parsing of browser/video/production/role/storage controllers | 0 | All five scripts parse | Terminal output; parsing is not proof of execution |
| `run-video.ps1 -Stage Integration -Project chemistryaudit2` | 0 | **60 / 0 / 0**, 2298.351s; controller service recovery also 0 | `api-integration-video-20261009-032650.xml`, `video-commands-Integration-20261009-032650.json` |
| `run-trivy.ps1` with fresh vulnerability DB, both immutable current images | Wrapper 1; EACH scan 1 | API **63 High / 0 Critical package findings, 21 unique CVEs**; encoder **79 High / 0 Critical, 37 unique** | `trivy-20261009-040329/{api,video-worker}.sarif`, same-folder `commands.json`; union with Scout **38** unique IDs |

Actual API image in the completed Backend gate:
`sha256:de544cb64dc1f7508f42b4b15542a774bf7c789452851d1fe6a93a46c7796582`.
Encoder:
`sha256:1a114fd71689b87e081aa3572c8b64896555cfc6fe53574a18f0dd291a52b309`.
The frontend application was changed afterwards and has now been rebuilt and
recreated by the complete Browser controller; its live gate is running, not
declared passed. Read the final browser command manifest for its actual served
image identity. These are not final release IDs.

Fresh official apt indexes showed installed = candidate for OpenSSL/libssl
`3.5.7-1~deb13u3`, TIFF `4.7.0-3+deb13u3`, ACL `2.3.2-2+b1`, systemd
`257.13-1~deb13u1`, zlib `1:1.3.dfsg+really1.3.1-1+b1`, ncurses
`6.5+20250216-2`, PCRE2 `10.46-1~deb13u3`, and liblzma `5.8.1-1+deb13u2`.
This proves only the queried stable/security candidates at that time, not
absence of CVEs or approval of custom native builds. Raw scanner gates remain open.

The fresh Scout results at 04:01–04:02 UTC retain all three IDs:
`CVE-2026-77214`, `CVE-2026-93990` (Expat) and `CVE-2026-85091` (zlib).
Scout's Windows temporary-archive cleanup warnings did not prevent both SARIF
reports; the recorded raw exits are 2, not converted to success. No user/Docker
data was deleted to hide the warning. Fresh Trivy now completed with the counts
above. Compared with 8 October, it additionally reports Expat77214 in BOTH
images; Scout already reported this ID, so the combined union remains38.
The new raw results supersede the older62/78 package-finding counts.

Primary tracker pages rechecked on 9 October still show official trixie Expat
2.8.3 vulnerable, while identifying upstream 2.9.0 for
[77214](https://security-tracker.debian.org/tracker/CVE-2026-77214) and the
2.8.5 UTF-16 fixing commits for
[93990](https://security-tracker.debian.org/tracker/CVE-2026-93990).
The application uses genuine pinned upstream 2.9.0 on stable Debian, with the
20 native/Python cases above; it is not a fictitious official Debian fixed
revision. The [zlib tracker](https://security-tracker.debian.org/tracker/CVE-2026-85091)
still lists stable as vulnerable/unfixed despite describing a newer introduced
nonblocking helper. The existing authenticated packaged-source reconciliation
supports a narrowly scoped inference, not scanner clearance or a new exploit
test. Independent review of custom fixes/range disagreement remains required.

## Complete live large-file gate

The full60-case integration suite passed without exclusions or reduced sizes,
fixed anonymous-memory budget512MiB, or increased API memory cap1.5GiB.
The uploaded/downloaded1GiB material and5GiB valid padded WebM matched their
full SHA256/byte counts; one-byte-over cases returned413 and no object. These
are byte-limit fixtures, not5GiB of representative lesson content or a capacity
test. The source change fixes independently reproduced SDK event-loop blocking
and cancellation ordering; it is not proof that this alone explains every
historical warm-process memory failure. Recheck after final browser/load work.

| Case | Bytes | HTTP | Peak anonymous bytes | Peak total bytes | cgroup max events | OOM / API restart |
|---|---:|---:|---:|---:|---:|---|
| Material at limit | 1073741824 | 201 | 346894336 | 1610424320 | 5824 | 0 / unchanged |
| Material +1 byte | 1073741825 | 413 | 347430912 | 1366663168 | 0 | 0 / unchanged |
| Video at limit | 5368709120 | 200 | 360886272 | 1610600448 | 123367 | 0 / unchanged |
| Video +1 byte | 5368709121 | 413 | 323149824 | 1610608640 | 86331 | 0 / unchanged |

Raw file-cache/total peaks and kernel limit-pressure events are retained in
JUnit, not smoothed away. Maximum working-set bytes were1413963776(material)
and1476243456(video), below the unchanged1610612736-byte API cap. The cgroup
reclaimed page cache; that pressure still matters for latency under load.
The subsequent complete browser gate was started only AFTER this suite exited
and restored the original running service set. No restore/load fault drill
overlaps browser journeys.

## Current disposition of all 21 requested items

| # | Disposition at this checkpoint |
|---:|---|
| 1 | Percentage/unit/latest-graded-attempt analytics repair passed in the recorded464-case Backend gate; explicit numerator/denominator/zero-total tests retained. No repeat on an unrelated telemetry patch; clean-source build is a separate pending packaging check. |
| 2 | Frozen quiz/attempt/answer evidence and explicit unverified legacy behavior passed Backend and real PostgreSQL migration checks. Actual grading journeys passed in the recorded93-case browser gate. New schema/database restore remains separate. |
| 3 | Shared create/merged-version/publish question policy covered by current API tests; editor's Arabic label serialization regression additionally repaired above. |
| 4 | Known deployment secret rejected in real Uvicorn startup regressions; insecure old Compose retired fail-closed, not made compatible by weakening TLS. |
| 5 | Full unchanged-size/unchanged-memory live suite60/0/0 passed on its recorded image, including byte boundaries, lease loss and storage/fault cases; subsequent browser93/0/0 also completed. SDK unchanged by the telemetry/style repair, so these suites are not repeated. Representative staging/load evidence and the historical memory-cause boundary remain separate. |
| 6 | Open: both actual new images scanned by Scout/Trivy; raw gates nonzero, union38 unique IDs. Stable candidates and the three Scout tracker pages rechecked; final per-CVE independent acceptance remains pending. |
| 7 | Encoder crash/retry completed Exit0 (`video-commands-Recovery-20261009-063259.json`); unaffected behavior not rerun. Historical full S3/DB restore25 steps passed6 October. New f4 database-only restore12 steps Exit0,53 tables/54,192 rows identical, original readiness recovered; no new full-S3 claim. |
| 8 | Needs representative dedicated staging; this constrained laptop does not prove 25/100/250/500 users for 10 minutes or production capacity. |
| 9 | Clean indexed BuildOnly gate Exit0:6 successful checks,3 explicit NOT RUN whole lint/unit suites per user; no fresh full-suite claim. Workflow scope now granted/verified. Commit/push/remote-SHA and remote Actions results are separate from local build success. |
| 10 | Complete93-case browser gate passed on the recorded pre-telemetry-repair image, including actual multi-tab/auth/network/revocation journeys. Retained, not repeated. A later reading-run cleanup502 remains an isolated unresolved operational observation. |
| 11 | Publication validation/journey and protected-playback responsibilities extracted; affected units and real publication/playback journeys passed in the recorded complete browser gate. No performance claim from line-count reduction. |
| 12 | Local trusted positive/negative TLS gate passes; real-domain TLS/CDN/DRM require external environment/providers and are not proven. |
| 13 | Guest/public catalogue filtering, persisted intent, empty/reset and mouse/touch journeys passed in the completed93-case browser gate; retain its screenshots and image manifest. |
| 14 | Selected-course progress, inline mobile placement and actual50/67% journeys passed in the completed93-case gate; existing DOM regressions retained. |
| 15 | Actual dark navigation/computed-color/hover contrast browser cases passed in the completed93-case gate; not merely a count of ARIA attributes. |
| 16 | Heading is static with no typing/deleting timers; DOM regression passes. |
| 17 | Scoped persistent feedback/deduplication and mobile publication/recovery journeys passed in the completed93-case gate; no repeated full browser run. |
| 18 | Real Mailpit reset/email and two-step registration journeys passed in the completed93-case gate. New guest reading light/dark also passed; SMS remains intentionally absent. |
| 19 | Actual mobile Setup/Review/Publish draft/retry cases passed in the93-case gate; new small-phone/landscape/actual200% teacher reading light/dark also passed across the recorded selected runs. |
| 20 | New reading matrix all6 cases passed across selected runs (3+1+2), without repeating passing cases. Student final selected2/0/0 Exit0 on659e1c3f…/e9a0edb9…; actual Chromium pinch200%, not desktop-toolbar zoom or physical-device certification. |
| 21 | Truthful registration CTA, persisted public course intent and actual through-auth enrollment passed in the completed93-case gate; no premature success indication. |

No external deployment or merge. Biology OCR remains user-deferred, not
declared complete. No SMS, captions/transcripts or user photos added.
The requested frontend skills guided in-flow feedback, mouse/touch navigation,
theme-aware readability and one primary action; the user's green/Cairo/RTL
requirements and keyboard-work boundary take precedence over generic guidance.

## User-requested pause — 2026-10-09, approximately 07:22 Africa/Cairo

Paused implementation and the full browser gate at the user's explicit request.
The Browser controller was interrupted (Exit1); its remaining Docker browser
runner was separately stopped. This is an interrupted run, NOT a completed
93-test gate and NOT evidence of readiness. Keep the existing artifacts in
`.qa/audit2/trusted-browser-20261009-040755` and rerun after repairs.

The observed output through case37 showed six failures: the mouse/touch public
catalog journeys (21,22), active-navigation contrast harness (23), segmented
time editing/publication (31), and source-review guards for quiz/assignment
(33,34). Case29, manual Arabic MCQ creation/publication/student grading, passed;
video recovery after teacher reload (32) and assignment choices/score/future
start cases (35–37) also passed. No result is assigned to unexecuted cases.

Reproduced root cause for the guest catalog: the anonymous landing page never
requests public courses and displays an empty catalog despite published server
data. No fix for this discovery has been applied yet. The contrast test attempts
to hover an offscreen, closed sidebar; open the sidebar through its actual menu
button before measuring. Investigate31/33/34 before classifying their causes.
Next resume: repair anonymous catalog loading with public-only data and truthful
loading/error/pagination states, repair the navigation test without bypassing
interaction, investigate the remaining failures, then rebuild and rerun affected
gates on the same final source. Latest completed backend433/0/0, integration
60/0/0 and frontend191/0/0 remain historical evidence, not final sign-off.

No application or data was deleted, no commit/push/deployment was performed at
this pause. The current `chemistryaudit2` site is retained; the retired
`chemistryprodlocal` project is not started. Local source changes are preserved.

## Resumed after the explicit pause — 9 October, 07:30–07:42 Cairo

The pause above is historical. Public catalog loading was actually repaired,
not merely documented: guests now request a published-only endpoint, with
grade/search filtering before count/pagination, stable ordering and public
serialization even when a teacher cookie is present. Private drafts, lesson
materials and video links are not returned. The landing page fetches only the
requested page, aborts stale searches, distinguishes loading/empty/error states,
and offers manual retry on429 without automatic loops. Existing authenticated
course queries keep their previous scope. Sources: `api/routes/courses.py`,
`services/course_service.py`, `services/lmsService.ts`, `usePublicCatalog.ts`,
`catalogState.ts`, `LandingPageView.tsx`, `App.tsx`, and their regression tests.

Before repair: the new public-catalog API cases were1 passed/3 failed/0 skipped
against the old image; three new frontend cases failed. After rebuilding:

| Command / gate | Exit | Passed / Failed / Skipped | Raw local evidence |
|---|---:|---|---|
| `run-video.ps1 -Stage Build -Project chemistryaudit2` | 0 | All requested images built; services healthy; volumes retained | `video-commands-Build-20261009-043024.json` |
| `run-video.ps1 -Stage Backend -Project chemistryaudit2` | 0 | **437 / 0 / 0** API; Expat20/0/0 each; encoder config6/0/0; migration and missing-upload recovery pass | `api-unit-video-20261009-043232.xml`, matching command manifest |
| Frontend suite before the subsequent auth-tab repair | 0 | **195 / 0 / 0**,29 files | `frontend-catalog-20261009.xml` |
| `npm run lint`; production-relative-API build | 0 each | 0 lint errors,4 existing Fast Refresh warnings; large video chunk warning retained | Terminal output; no suppressions or local env-file edits |
| `verify-runtime-source.ps1` before the subsequent auth-tab repair | 0 | API/worker/encoder126 source files and web91 assets/configs match | `runtime-source-20261009T043527Z.json` |
| Seven affected actual trusted browser regressions | **1** | **5 / 2 / 0**,2.8 minutes | `trusted-browser-20261009-043500/browser.xml`, `command.json` |

Those five passes cover real navigation contrast, Arabic segmented publication
time, BOTH source-review guards (quiz/assignment), and an invalid publish request
reaching the backend422 before a successful201 retry. The latter leaves zero
questions after rejection and exactly two after retry, not duplicate orphans.
The test's first request is corrupted in transit, not replaced with a mocked
success. The source-review fixture is mounted read-only in the runner; this is
NOT completion of the user-deferred Biology extraction accuracy work.

Both catalog mouse/touch journeys now load/filter/reset the actual public
catalog successfully, but expose another genuine bug: after selecting a course,
refreshing the registration page returns to sign-in. Enrollment intent survives;
the auth-tab choice does not. Two new DOM regressions reproduced this failure
(2 failed/3 passed). `authNavigation.ts`, `App.tsx`, `AuthView.tsx` now preserve
ONLY `#auth?tab=register` or `signin`, not form data/passwords. Back/forward and
reset-token priority are covered. Five DOM cases subsequently pass; additional
pure navigation cases are included in the next full gate. A complete Browser
controller has started on the rebuilt frontend; **its result is pending**, not
inferred from the seven-case run or the earlier interrupted93-case run.

Actual API and encoder images in the437-case gate:
`sha256:097d7cb60a80f68601a67ab39f4db351f051040353669eacd2903f8c7a6dcf3d`
and
`sha256:e77017f1c2abe37108cda0d75c50dfb41d5f618d656ffd9eebe704fc9b135a20`.
These supersede the earlier images for application QA, but fresh scans of these
identities are still required. The60-case integration result above is historical
until rerun on this final source. No commit, push, merge or external deployment
has been performed during this continuation. Release gates remain OPEN.

### Remaining eleven encoder tracker pages rechecked on9October

The previously reviewed27 shared/encoder IDs plus these11 account for the
38-ID union of the earlier raw Scout/Trivy scans. Each Debian primary tracker
page below still marks the official trixie7.1.x package vulnerable/postponed;
it identifies the fixing upstream9.x branch separately. The installed restricted
encoder is genuine signed upstream9.0.2 built on stable Debian, **not sid**, and
is not being relabelled as an official fixed Debian package. Raw scanner gates
remain open, and none of these rows constitutes a crafted exploit regression.

| CVE / primary tracker | Upstream fixing branch / commit | Actual application path and residual boundary |
|---|---|---|
| [64835](https://security-tracker.debian.org/tracker/CVE-2026-64835) | n9.0; `c10e7f5dc12367d0dfcc52983d427c6766425fa8` | ADX midstream channel state. Actual `adpcm_adx` decoder exists; standalone AAX excluded, embedded decoding not generally excluded. Newer fixing source is the primary evidence. |
| [66036](https://security-tracker.debian.org/tracker/CVE-2026-66036) | n9.0; `62294b6a8ad2370e1435bb9985ebe6b53be14c2b` | `hqdn3d` exists, but application commands use only scale/setsar, never that filter or `reinit_filter 0`. Do not claim it was compiled out. |
| [66039](https://security-tracker.debian.org/tracker/CVE-2026-66039) | n9.0; `947c57d9e68800dd4d39f110140f8f6c34cedf80` | MACE6 packet-size overflow. Decoder exists; CAF demuxing excluded, codec-in-other-container paths not generally excluded. |
| [66040](https://security-tracker.debian.org/tracker/CVE-2026-66040) | n9.0; `5185caaeb8e2c05f7369cbedf0f616601bd82d5c` | PNG/APNG EXIF encoding. Application strips input metadata and encodes H264/AAC HLS, not PNG/APNG. This is not a blanket image-decoder exclusion. |
| [66041](https://security-tracker.debian.org/tracker/CVE-2026-66041) | n9.0; `c20d78c6838ae62e9954163833d24fc0ed1b74a3` | QUIRC filter/PGS dimension copy. Actual quirc filter absent; no external-library autodetection or app subtitle/quirc filter. |
| [70628](https://security-tracker.debian.org/tracker/CVE-2026-70628) | n9.0; `02fc47e13f903768b75f7985a2706a6223ab4506` | DVB subtitle parser, WTV trigger. WTV excluded and subtitles not mapped; probe parsing cannot be ruled out merely because output subtitles are disabled. |
| [70632](https://security-tracker.debian.org/tracker/CVE-2026-70632) | n9.0; `16b2049d4d5222db6cd7c031409058571c94f6a9` | CFHD width invariant. Actual CFHD decoder exists; MOV can contain CFHD although AVI is excluded. Treat as reachable, rely on fixing source and bounded worker, not extension-based exclusion. |
| [75142](https://security-tracker.debian.org/tracker/CVE-2026-75142) | n9.0.1; `b274f0d21ba684446fd59b49e00f3f8e9ed954df` | MPEG-PS mux stream counts. Actual mpeg muxer exists; application maps at most one video and one audio stream into fixed HLS output, not PS. |
| [75143](https://security-tracker.debian.org/tracker/CVE-2026-75143) | n9.0.1; `8880a174d08131f94f58a0492d1c8c6d68b74f67` | Async RIST reader URL buffer. Actual restricted binary has no RIST/HTTP/HTTPS/TCP/UDP/TLS protocol; file-only application whitelist retained. Other listed wrappers/prompeg are not claimed absent. |
| [75144](https://security-tracker.debian.org/tracker/CVE-2026-75144) | n9.0.1; `1afd5c3ddafda4209e0881cd30684b919e99de7c` | VC2/Dirac RTP packetizer. RTP muxer exists; tested TCP/UDP transport protocols are absent and the application outputs fixed file-based HLS, not RTP. |
| [75146](https://security-tracker.debian.org/tracker/CVE-2026-75146) | n9.0.1; `999f8ba75ce0bf1167677de7e11a5af678fdb866` | Live DASH refresh negative fragment index. No application live-DASH/network-input workflow; do not confuse present `webm_dash_manifest` demuxer with proof all DASH-related code is absent. |

Actual commands in `app/services/video_processing.py` whitelist
`mov,matroska,webm` and file protocol for both ffprobe/ffmpeg, discard metadata,
map fixed video/audio streams and select fixed H264/AAC/HLS output. The worker
has bounded CPU/time/address-space/output and container limits. These reduce
exposure/impact but do not replace security updates or independent custom-build
review. The six runtime checks in `verify-native-video.py` prove actual version,
signed/hash-pinned provenance, absent RASC and the specifically tested transport/
hardware capabilities and
retained required codecs/HLS only. No claim of11 exploit tests or scannerExit0.

Reproducible read-only capability inventory:
`scripts/qa/inspect-native-video.py`, run in the actual encoder as its normal
runtime user, Exit0, evidence `native-video-capabilities-20261009.json`. CFHD,
ADX, MACE6, hqdn3d and MPEG/RTP/SPDIF muxers are **present**, while RASC and
QUIRC are absent. CAF/WTV demuxers also exist in the binary: they are excluded
by the application's explicit format whitelist, not compiled out. Network
protocol conclusions refer to HTTP/HTTPS/TCP/UDP/TLS/RIST absence and the file-only
application whitelist; wrappers such as async/concat and the listed prompeg
protocol must not be described as all absent. This evidence is deliberately
separate from the native6-case gate and the raw CVE scans.

## Continuation checkpoint — 9 October, 08:04 Cairo

The93-case trusted browser run `trusted-browser-20261009-044314` is still running
on its fixed earlier runtime. Observed failures20 and21 remain failures: no
final pass is inferred from later local source edits. Case20 reproduced a real
many-enrollment defect: the account had177 retained enrollments and151 distinct
assessment requests had already returned200, including the expected quiz, but
the application waited for the entire fan-out before committing assessment
state. Case21 failed before its catalog interaction: lesson creation returned
503 in206.432ms from admission control. Redis timeout/resource contention is
suspected, not proven. The touch registration/reload/enrollment journey22 passed.

Local repairs awaiting an image rebuild and browser verification:

- Student enrollment metadata is now paginated through a student-only,
  institution-scoped `enrolled_only` course query. Active/completed ownership is
  filtered before count/pagination; guest, teacher and public/enrolled mixing
  are rejected. Open-course assessment reads are independent of other courses.
- `useCourseAssessments` aborts obsolete course/account reads, exposes an honest
  contextual error and manual retry, and does not replay429 on an SSE reconnect.
  Real access-revision changes reconcile missed approval events. The course
  switch browser case now asserts only the two selected course IDs are read.
- Admission failures log only the exception class, never its message, Redis key
  or connection string. Socket budgets, rate limits and fail-closed503 behavior
  were not weakened. A new timed serial reproduction is still required.
- A guarded, idempotent152-enrollment fixture makes the three catalog hydration
  scenarios reproducible from clean synthetic data. All three existing cases
  remain; they now require bounded selected-course reads, visible429/503 and
  real manual recovery rather than accepting a152-course fan-out.

| Command / gate | Exit | Passed / Failed / Skipped | Evidence / qualification |
|---|---:|---|---|
| New enrollment query tests before repair, corrected fixture | 1 | 4 / 2 / 0 | `enrolled-catalog-before-20261009-corrected.xml`; original fixture-error artifact retained separately |
| Public/enrolled catalog and safe admission diagnostics, mounted current source | 0 | 16 / 0 / 0 | `course-admission-mounted-source-20261009.xml`; NOT a rebuilt deployed image |
| Guarded large-catalog fixture, mounted current source | 0 | 4 / 0 / 0 | `enrollment-fixture-20261009.xml`; NOT a deployed-image check |
| Full frontend before subsequent access-revision/fifth hook regression | 0 | 204 / 0 / 0 | `frontend-selected-course-20261009.xml`; historical within this continuation |
| Latest selected-course hook and request-storm regressions | 0 | 23 / 0 / 0 | Terminal result; selected tests only, not the full suite |
| Latest `npm run lint`; `git -c core.safecrlf=false diff --check` | 0 each | 0 lint errors,4 existing Fast Refresh warnings | No suppression; not a runtime verification |

Fresh security results on the actual earlier API/encoder identities097d7cb/e77017f:
Scout **3 High/0 Critical each**, rawExit2 each, controllerExit1, evidence
`scout-video-{api,video-worker}-20261009-044252.sarif`. Trivy **63 High/0 Critical
API**, **79 High/0 Critical encoder**, rawExit1 each, controllerExit1, evidence
`trivy-20261009-044837/`. The union is38 unique IDs, not142 independent CVEs.
No alert, severity or scanner evidence was suppressed. Installed stable/security
candidate comparison Exit0 (`stable-security-20261009-044717.json`) still finds
OpenSSL/libssl3.5.7-1~deb13u3 installed from trixie-security and no newer stable
candidate among the checked packages. This is not a zero-CVE clearance.

No commit, push, deployment, deleted application data or restarted retired
project during this continuation. Current local source is newer than the
running images; runtime/source equivalence and all final gates must be rerun
after rebuilding. Release status remains NOT READY.

### Additional progress accounting and browser harness repairs, same continuation

While checking consumers of the on-demand assessment repair, found that the
inline progress control still read the old parent course's assessment refs.
Wiring the selected refs exposed two pre-existing accounting defects: merely
starting an official quiz counted as completion, and homework completion was
never returned/mapped. The API now returns explicit `completed` booleans from
the current student's official submitted quiz attempts and homework submissions.
Expired/in-progress/practice attempts and other students/courses do not count.
Consumed-attempt policy remains separate and unchanged. Two set queries avoid
per-assessment N+1; no answer, score or another student's submission is exposed.

`FloatingProgressFab` receives selected-course refs and their loading/error state.
It displays an unknown overall percentage, not a misleading100%, until those
reads succeed; failures offer explicit retry. Quiz/file submission refreshes
those refs only after the actual successful response. Live course-switch and
manual homework cases now assert50%/67% from their actual fixture submissions;
these new browser assertions are pending a rebuilt runtime.

| Regression | Before | After / boundary |
|---|---|---|
| Loading/failed assessment progress | 2 passed / 2 failed / 0 skipped, Exit1 | 4/0/0 in the selected27-case frontend gate, Exit0; then additional consumed-but-unsubmitted case added, full suite pending |
| Server-confirmed quiz/homework completion | 0 passed / 5 failed / 0 skipped, Exit1 | Completion plus existing follow-up/query-budget suite **22/0/0**, Exit0, `course-completion-after-20261009.xml`; mounted current source, NOT deployed-image evidence |
| Full frontend before this progress repair | **205/0/0**, Exit0 | `frontend-selected-course-final-20261009.xml`; filename does not imply final release sign-off |

The earlier fixed-image93-case browser run additionally failed both manual
grading variants63/64 and payment69 on strict text-locator ambiguity: each notice
has one visible contextual message plus a deliberate screen-reader announcement.
The assertions now explicitly verify both distinct elements; neither message
nor the underlying grading/payment/security assertions was removed. These are
test-harness repairs pending rerun, not evidence that the entire journeys pass.

### Earlier-runtime browser gate completed; final repair build started

The fixed earlier-runtime run `trusted-browser-20261009-044314` completed with
**87 passed / 6 failed / 0 skipped**,36.2 minutes, raw/controller Exit1. The six
failures are course-switch20, admission during mouse catalog21, both manual
grading63/64, payment69, and video playback93. Preserve `browser.xml` and
`command.json`; this run is neither interrupted nor a passing release gate.

Playback93 reached the real temporary refresh outage but expected obsolete
generic text. The current playback controller renders the explicit network/
service error instead, as the failing snapshot confirms. The revised test must
observe the actual `/auth/refresh`503 and the corresponding visible player
alert, then retain its existing multi-tab, bounded-retry, recovery, playback,
seek, private-link and comment assertions. No application error is waived by
changing expected wording. An explicit503 hook regression was also added;
the full frontend count212 below predates that one additional case.

Source review of the ambiguous manual-grading failures also found missing
contextual message hosts in the full-page student homework/quiz overlays.
`MyCoursesView` now mounts named `ToastRegion` hosts in the course, solver and
submission confirmation, retaining site colors and document-flow feedback.
The homework browser case now asserts the error is in its named region, in the
viewport, and topmost at its center—not merely present behind the overlay.
This visual behavior still requires the rebuilt browser run. The provider's
multi-region regression went from4/1/0 Exit1 to5/0/0 Exit0, with both artifacts
`contextual-overlay-notice-{before,after}-20261009.xml` retained.

Latest complete frontend before the additional503-only test: **212/0/0**,
32 files,87.70s, Exit0, `frontend-contextual-completion-20261009.xml`; lint/build
also Exit0,0 errors/4 Fast Refresh warnings, unchanged video chunk-size warning.
New API/source changes and213-case frontend still require the final image/
browser gates. A complete QA image Build has now started after the93-case run
exited. It preserves existing volumes/data and does not start the retired stack.

### Rebuilt current runtime — 9 October, 08:24 Cairo

Build Exit0: `video-commands-Build-20261009-052141.json`. All requested runtime
services healthy; existing volumes retained. `verify-runtime-source.ps1` Exit0,
`runtime-source-20261009T052345Z.json`:127 application/script files for each
API/worker/encoder and91 frontend assets/configs match the current checkout,
with zero mismatches. These are actual running image identities:

| Service | Actual image |
|---|---|
| API | `sha256:ebeb4c6e9739cf07b024e53952b2940af3ad7ff3b9a5076c898fd4ec0edb137c` |
| Worker | `sha256:474a05780cd88b0cb8be4ec94482101862eca11b8d4e631b3979ee32adac247a` |
| Encoder | `sha256:90c409bea5ff23227f09b209b41725503c0a81595728ab0e4a119b006919f8d0` |
| Web | `sha256:33ba676931a6f1d390916176307cc99481d25e8ad764daf50151da1e652f0d8a` |

Backend, affected browser journeys and final full/security/storage/load gates
are pending on these identities. Earlier437/60/87 browser/API counts and raw
image scans are explicitly historical, not transferred to these new images.

`git ls-remote origin refs/heads/fix/queen-p0-handoff`, Exit0, reverified the
actual remote at `429848608834c7c012e3b2c9e7fcc4eb71f93ac0`. Local HEAD remains
`0c24a2f7e06a14c03f76c6609b6a45f9a03f6c5f`: two existing unpushed commits
(`d165dc1`, `0c24a2f`) plus current uncommitted repairs. No new staging, commit,
push, merge or external deployment. The unrelated `pc_builder_3d_cases` directory
is preserved and outside this task's staging scope.

### Current-image backend gates completed — 9 October, 08:26 Cairo

`run-video.ps1 -Stage Backend -Project chemistryaudit2` completed Exit0 on
the rebuilt identities above; command manifest
`video-commands-Backend-20261009-052349.json`. API unit/protection tests:
**451 passed / 0 failed / 0 errors / 0 skipped**,110.868s,
`api-unit-video-20261009-052349.xml`. Native Expat verification:
**20/0/0 per API and encoder**; signed FFmpeg/config/provenance verification:
**6/0/0**, all Exit0. These counts are separate suites, not browser results.

Actual PostgreSQL migration checks passed fresh-to-head, previous e8-to-head
and f3-to-head; nine historical rows remained unchanged at the single current
head `f4a6c8e0b2d4`. Real PostgreSQL/S3 lost-multipart recovery passed:
missing session read200, persisted expired state, obsolete completion409,
fresh intent201 and logout204; zero server500 responses. No production data
was substituted or rate-limit counter erased.

Affected ten-case browser rerun completed Exit0 under
`trusted-browser-20261009-052620`: **10 passed / 0 failed / 0 skipped**,
512.952s. Actual source/image identities and unchanged-image checks are in
`command.json`; runner identity
`sha256:cfc89d1959c02b5045d2bb6391381e07511a8ad00d308ddb2af538e535309975`.
Passed: course switching/real quiz/progress50%, mouse and touch guest catalog
through registration/enrollment, all three180-enrollment hydration scenarios,
both real essay/homework manual-grading variants with contextual notices and
progress67%, receipt review/ownership/notifications, and protected video
upload/validation/HLS/playback/seek/auth recovery/revocation/persisted discussion.

Hydration observed3 course/assessment GETs normally,4 with each injected429
or503, peak1 assessment request; only the selected course was read. Beyond
Retry-After there was no timed replay, auth remained usable and explicit manual
retry recovered. The earlier isolated mouse-catalog admission503 did not recur
in this serial run; this alone does NOT prove its cause or eliminate a transient
dependency failure. Fail-closed limits/timeouts were not relaxed.

The complete Browser controller has now started serially after this runner
exited. Fresh image scans, full integration/storage/encoder recovery/load and
the final complete browser gate remain open. Earlier results are not copied to
these image identities.

Primary security trackers were reread live during this rerun (9 October):
[OpenSSL84782](https://security-tracker.debian.org/tracker/CVE-2026-84782)
still explicitly identifies trixie-security3.5.7-1~deb13u3 as fixed;
[Expat77214](https://security-tracker.debian.org/tracker/CVE-2026-77214)
identifies upstream2.9.0 but stable2.8.3 remains vulnerable;
[zlib85091](https://security-tracker.debian.org/tracker/CVE-2026-85091)
still marks stable unfixed while retaining the upstream affected-range
discussion. This does not change raw scanner exits or independently clear
custom builds. The package-query/scanner reruns on the rebuilt identities
will run only after browser activity exits, not concurrently.

The complete Browser controller's pre-browser lint/build/unit steps completed
Exit0; **213/0/0**,32 test files. Its web recreation generated the new actual
identity `sha256:e75b105caf3eda88317657175b5b790ffddfb0734a71f22d92b9138a818884fc`.
`runtime-source-20261009T053905Z.json`, Exit0, again compared127 files per
API/worker/encoder and91 served web assets/configs with zero mismatches. API,
worker and encoder identities remain those in the rebuilt-runtime table;
the ten-case browser result refers to the previous immutable web identity,
not silently relabelled as a test of this one. The complete93-case run is
active under `trusted-browser-20261009-053845`, with its own identity manifest
to be saved at completion. No application edits while it runs.
