# Remaining-review evidence ledger — 6 October 2026

8October user-authorized CURRENT WIP push and outstanding gates are summarized
in [QA_PUSH_CHECKPOINT_2026-10-08.md](QA_PUSH_CHECKPOINT_2026-10-08.md).
Historical no-push-until-finished instructions below are superseded ONLY for
this requested checkpoint, not for merging, deployment or release approval.

Not a deployment approval. Starting branch `fix/queen-p0-handoff`, local and
remote HEAD both `429848608834c7c012e3b2c9e7fcc4eb71f93ac0` (checked again this
round with `git ls-remote`). Everything described here was initially a local,
uncommitted change; the eventual commit/push must be verified independently.
No merge, deployment, history rewrite, real-user email, or paid account setup.
Unrelated `pc_builder_3d_cases/` is preserved and excluded.

## 8October evidence boundary (read this before the historical rows)

See [QA_2026-10-08.md](QA_2026-10-08.md) for the current immutable images,
commands and incomplete gates. Current API full units388/0/0; current complete
frontend units141/0/0, lint/build0. The11:57UTC complete88-case Browser gate
finished81/7/0, Exit1 (5 failures plus2 errors); source428 and runtime bytes
verified unchanged after it. Deterministic identity-fixture before1/2/0,
after4/0/0 includes the calendar retry. Four genuine upload/material/resume/
playback cases then passed4/0/0 with unchanged deadlines/limits/app images,
after the user-approved temporary pause of7 old chemistryprodlocal services
(NO data/container deletion). The12:55UTC complete88-case Browser repeat on
the new428-file frozen manifest completed88/0/0, Exit0,1797.131209s. Same428
sources/HEAD and actual API/Celery/encoder123 files each plus web90 assets/config
matched after the run, Exit0. Old dependency/Docker delay cause is not declared
fixed by isolation. Fresh approved npm audit353 dependencies/0 findings;
PyPI audit81 actual-image/lock-matched dependencies/0 findings/0 skips,
bothExit0; these do NOT clear native image alerts below.
Full60-case Integration completed57/3/0, Exit1,2210.031s. Exact1GiB material
and rejected5GiB+1 video exceeded the unchanged512MiB anonymous-RAM budget;
exact5GiB video returned503 Admission service temporarily unavailable.
All60 executed, no skips; same frozen sources and runtime bytes verified
unchanged after it, Exit0. These failures remain OPEN. Final recovery/load/
restore/clean-index evidence is still pending.
Subsequent unchanged standalone five-file-case diagnostic5/0/0 and prefix
concurrency/session/SSE plus five-file-case diagnostic18/0/0 both exited0.
Neither reproduces/repairs the full-run failure or replaces the full gate.
No GitHub push, external deployment or successful remote CI is inferred.

Fresh actual-image raw findings: Scout3High/0Critical EACH API/encoder,
rawExit2 each; Trivy62High API/78High encoder,0Critical, rawExit1 each.
Current union38 unique CVEs, not the historical41/56/57 counts below.
All38 are reviewed individually in `NATIVE_CVE_REVIEW_2026-10-06.md`;
custom signed source fixes/configuration restrictions are not scan suppression,
an official stable-package fix, or independent security sign-off.

Biology accuracy remains explicitly deferred; exact final API/native change
comparison retains all7 inputs with identical raw/parsed outputs and trusted
models. Both baseline and candidate are6/1/0, Exit1, same biology PDF7/10
fully matching. This is dependency parity, not a closed fidelity gate.
Retired operator backup/restore scripts now refuse with64 without filesystem,
credential or Docker operations; offline guard tests4/0/0, Exit0. Actual
SeaweedFS backup/NEW-store restore must still execute independently.

8October explicit product override: the user does NOT want video captions/
subtitles. No caption feature, transcript generation or caption control will
be added; the historical item16 caption request below is superseded and
NOT_APPLICABLE in this round. Keyboard/focus/labels/contrast/RTL checks remain
in scope. This does not claim captioned-media WCAG conformance for the product.

## Status rules

`FIXED_WITH_EVIDENCE` applies only to the explicitly tested behavior, never to
all possible security/production conditions. `OPEN` includes an improvement
with incomplete requested acceptance evidence. `NEEDS_EXTERNAL_EVIDENCE` needs
an actual provider/staging environment, not a local Compose run. Historical
results in the earlier reports are not added to this round's test totals.

Counts below are Passed / Failed / Skipped. B1 is the earlier API unit run:
`scripts/qa/run-video.ps1 -Stage Backend`, Exit **0**, **306/0/0**,
`.qa/audit2/api-unit-video-20261006-142157.xml`. Test names identify subsets of
that total, not additional runs. B1 also ran actual native Expat regressions,
**4/0/0 in each image**, two isolated PostgreSQL migration gates, and real
PostgreSQL/S3 missing-multipart recovery, all Exit0.

7October B5 supersedes earlier-source totals where explicitly recorded in
[QA_CONTINUATION_2026-10-07.md](QA_CONTINUATION_2026-10-07.md): rebuilt API units
336/0/0, current frontend units92/0/0, lint/build0. Item9 now additionally uses
uniform encrypted identity admission without account lookups, migrationf3,
UTC password epochs and actual PostgreSQL claim/rollback regressions. Item12
adds stale video-scope guards and two-tab blob/upload/HLS/SSE acceptance cases;
item16 separates transport, option editing and source review. Their FULL live
acceptance is still pending B5 Integration/Browser; no row is promoted from
OPEN merely because these local changes or their unit tests exist. Historical
timing/scanner/browser figures below retain their original source/image scope.

Runtime image identities are recorded in
[`NATIVE_CVE_REVIEW_2026-10-06.md`](NATIVE_CVE_REVIEW_2026-10-06.md).
Changing test mounts does not substitute runtime application code: API/encoder
application source is inside those built images. Web has a separate final
build. Raw JUnit/trace/SARIF, synthetic credentials and backups stay in ignored
`.qa`; only source, reproducible tools and non-secret summaries are committed.

### 7October current scope and pending B8 gates

The detailed B1–B5 figures below are historical. B7 actually passed API345/0/0,
frontend94/0/0 and actual-image native/source gates, as recorded in
`QA_CONTINUATION_2026-10-07.md`. Current B7 raw scans: TrivyAPI62High/encoder79High,
0Critical, Exit1 each; ScoutAPI3High/encoder5High,0Critical, Exit2 each; current
four-report union41IDs. Native dependency reduction removes unused OS XML/curl/
Poppler/archive integrations, not remaining engine findings or bundled XML risk.
Signed stable upstream FFmpeg9.0.2/RASC-removal is a further change IN PROGRESS;
it needs a real rebuild, binary proof and fresh scanners/tests before adoption.

Item16 additionally separates `VideoLessonNavigation` and
`QuizPublishConfirmation`, preserving playback/publication lifecycle. New unit
and real dark/mobile/error/loading acceptance must run; earlier94 frontend tests
do not cover the latter new module. Full B7 integration completed Exit0,
58/0/0,2298.973s; B8 repeat and final browser/load/restore/clean evidence remain
pending.
No status is promoted solely from a code edit, signed source or unit count.

**Item18 BIOLOGY improvement is explicitly DEFERRED BY THE USER on7October.**
Current strict original-fixture result6/1/0, Exit1, biology10count/7fully-matching,
remains recorded. Other six originals passed that comparator. Do not change
references, silently skip biology, invent scientific source words, or call all
Extract perfect. The user deferral narrows this round's work, not the test result.

## All 21 items (before → implementation → evidence/limits)

| # / final status | Trigger before / change and relevant files | Proof and remaining boundary |
|---|---|---|
| 1 FIXED_WITH_EVIDENCE | Student could read institution summary; teacher aggregates were institution-wide. `routes/analytics_report.py`: deny student; scope all counts, averages and top quizzes to owned courses/eligible students; preserve tenant/admin policy and exclude practice. | B1 `test_summary_scope_students_teachers_admins_and_other_tenant`: real API under unit DB checks all roles/tenants and aggregates. Live PostgreSQL teacher mastery/grades is separate; not claimed as full live summary aggregation coverage. |
| 2 FIXED_WITH_EVIDENCE | Logout with missing/expired access only cleared cookies. `routes/auth.py`: verified refresh-hash fallback, user/family row locks, revoke current family and related playback only, commit before clearing cookies. | B1 fallback parameter cases and session/video regressions. Live concurrent refresh/logout cases run on PostgreSQL, saved credential must remain401; no unverified JWT identity accepted. |
| 3 FIXED_WITH_EVIDENCE | Two outstanding reset links both worked. `services/auth_service.py`, `routes/auth.py`: serialize user password epoch; invalidate every outstanding reset token within password transaction; authentication rechecks hash after lock. | B1 reset/change-password regressions. Live two-token race requires exactly one204 and one400 on PostgreSQL; invalidates remaining links and families, not merely cookies. |
| 4 FIXED_WITH_EVIDENCE | production_like silently accepted insecure development defaults. `core/config.py`, `main.py`: explicit development/test versus deployment classes, secure origins/secrets/cookies/SMTP/rate-limit requirements. The shared deployment classifier also guards `scripts/seed_teacher.py`, including staging/production_like. | B1 three deployment-environment cases, production config/Render contracts and eight additional seeder rejection cases. Actual provider startup/configuration remains external; local HTTPS is self-signed. |
| 5 FIXED_WITH_EVIDENCE | General `?token=` was accepted. `api/dependencies.py`: remove general query credential; retain specialized scoped playback/preview tokens. | B1 auth/token-scope and access-log redaction regressions. Existing browser uses HttpOnly cookies; no session secret returned to JSON/localStorage. No blanket promise that every third-party log is audited. |
| 6 FIXED_WITH_EVIDENCE | Middleware deduplicated a whole category and skipped stricter route budget. `core/rate_limit.py`, `routes/auth.py`, `main.py`: deduplicate exact policy identity, independent route reset/login windows behind the original shared auth budget. Final7October comparison found this round's separate refresh60/min category relaxed the original shared15/min ceiling; it was restored, not accepted as QA isolation. | Final B4 live55/0/0 Exit0 includes actual shared15/min HTTPS/Redis:15 admitted, sixteenth429, another auth mutation429, Retry-After60 and real expiry recovery. Reset5/300s remains independently enforced. Classification/mixed-budget unit20/0/0 Exit0. QA waits for true windows, does not clear production counters. Full provenance in7October continuation. |
| 7 FIXED_WITH_EVIDENCE | Local provider trusted any existing path outside base. `core/storage.py`: one realpath/commonpath containment resolver for read/write/delete/exists/size; mixed traversal and symlink escapes rejected, legacy in-root absolute paths retained. | B1 traversal3, absolute1 and Unix symlink1. Windows junction-specific test not run; no remote arbitrary file-read/delete exploit claim. |
| 8 FIXED_WITH_EVIDENCE (local policy, not universal timing equality) | Missing account budget and inconsistent expensive verification. `core/rate_limit.py`, `routes/auth.py`, `core/config.py`: HMAC account+institution keys, normalized identity, bounded IP/account budgets, bounded local eviction, dummy hash for absent/inactive users; known CIDR XFF trust only. Latest revision also adds uniform account+IP4/10s short admission backoff before DB/hash and account-wide charging, without sleeping. | B3 unit and final53/0/0 real PostgreSQL/HTTPS gate passed. Two clients retain independent12 unauthorized then2 rate-limited requests, Retry-After/HSTS despite forged headers. Actual short backoff4×401 then429, real expiry recovery200 and another real IP200 during cooldown;30 production-cost timing samples/class verify six independent IPs and identical401 contracts. Provider proxy CIDRs and universal timing indistinguishability are NOT implied; external boundary remains item19. |
| 9 OPEN (delivery recovery evidenced; measurable timing difference remains) | Existing-account reset performed SMTP during HTTP and disclosed timing/failure. New `models/mail_outbox.py`, `services/session_maintenance.py`, `mail_service.py`, migration **f2d4a6c8e0b2**: encrypted durable DB outbox, stable Message-ID, bounded SKIP LOCKED claim/retry, erase token ciphertext on completion/cancel. | Final B4 live55/0/0 includes paused TLS SMTP and worker/broker-independent recovery, PostgreSQL multi-consumer/crash checks and ciphertext erasure. SMTP is explicitly **at-least-once**: acceptance before lost commit can duplicate. New30 timing samples/class: existing median11.5715ms versus missing8.5685ms, bootstrap95% difference[1.6445,4.1745]ms excludes zero. Uniform200 body and30 synthetic mail jobs completed/erased, but timing indistinguishability is NOT proved or claimed. No real recipients used. |
| 10 FIXED_WITH_EVIDENCE | Hard-coded grace/no cleanup. `core/config.py`, `auth_service.py`, `session_maintenance.py`: bounded1–30s configured grace from original revocation time; one security notice per family; batched expired-row cleanup with7-day post-expiry evidence retention. | B1 replay cannot extend grace or revive family, cleanup retains live/recent evidence; concurrent PostgreSQL maintenance and three actual two-tab outage cases passed. New live HTTP/PG configured-grace test: Exit0,1/0/0,32.891s, `grace-live-20261006.xml`: actual30s window, inside200 without changing original revoked_at; four simultaneous outside401 plus repeated401; no active family, exactly one notification and one audit. No mocked clock or aged DB rows. |
| 11 FIXED_WITH_EVIDENCE | Missing Fetch Metadata layer. `main.py`: reject unsafe cross-site cookie request without approved Origin; metadata never authenticates or replaces CSRF. CORS explicit methods/headers,600s cache, standalone Bearer policy preserved. | B1 metadata/CSRF/tenancy tests including exemptions and cookie/Bearer checks. No WebSocket added; current transport is SSE. Provider/browser-specific topology not implied. |
| 12 OPEN (transient logout defect fixed) | Network/5xx refresh looked like invalid auth and lost account/draft. `services/apiClient.ts`: success/invalid/transient/cancelled outcomes; preserve scope on outage, bounded cooldown/timeout, one shared pending refresh, epoch cancellation on account switch; `refreshRecovery.test.ts`. | Frontend unit regression exercises JSON/blob,503/429/network and stale account; no credentials in BroadcastChannel/localStorage. Earlier78-case gate passed actual two-tab shared-cookie503/429/network cases; all three independently passed again on7October with11-second observation and retained drafts, but the current full browser gate is not yet complete. SSE renewal and interrupted upload also passed separately. Combined two-tab blob/upload/SSE/video matrix remains incomplete. |
| 13 FIXED_WITH_EVIDENCE | SSE/concurrency literals drifted from configurable cookie names. `routes/realtime.py`, `core/concurrency.py`, `core/config.py`: Settings-consistent access and explicit fixed cookie-name contract (unsupported custom names rejected); `docs/API.md`. | B1 three custom-name rejection tests and realtime regressions; live logout/revoke/expiry/Redis-outage SSE tests check DB active-family revalidation without a held stream connection. No process-local marker alone used as distributed proof. |
| 14 FIXED_WITH_EVIDENCE | Public metrics/detailed dependencies and repeated expensive readiness; broken root Dockerfile. `routes/health.py`: platform-admin detail/metrics, generic public ready, bounded single future and cached positive/negative probes. Removed unused root `Dockerfile`; supported `infra/Dockerfile.api` remains non-root. | B1 readiness slow-probe/cache/privacy plus config tests, actual Build success and runtime health. No root reset of data; source removal is Git-recoverable. Clean-checkout proof recorded separately. |
| 15 OPEN | No tracked CI/full supply-chain gates. `.github/workflows/quality.yml`, `ci_migrations.py`, `run-trivy.ps1`, QA tooling: lint/build/unit/browser/PG migrations, audits/secret scans and both image scans, minimal permissions, artifacts. | Fresh+previous-head migrations2 gates Exit0, B1; pip-audit after installing QA tool Exit0/no known vulnerabilities. Latest7October Trivy API91High+1Critical, encoder108High+1Critical, bothExit1. Current Scout API5High/encoder7High, eachExit2;56distinct current IDs are covered by the preserved57-ID historical review. The reduced Scout count reflects scanner data, NOT a new package fix/suppression. Workflow has NOT yet run on GitHub; configuration is not successful CI evidence. |
| 16 OPEN (specific a11y fixes evidenced) | Large mixed-responsibility views and new axe defects. New `RegistrationWizard`, `mcqOptions`, `AccessibleDialog`; quiz select/date labels, native modal inert/focus/Escape; video slider labels and success text contrast. | Earlier78-case registration/quiz/video axe gate passed, including Escape/opener focus. That historical three-step UI is NOT proof of the current two-step acceptance; current light/dark/mobile/keyboard/error/loading wizard checks run separately in the7October full browser repeat. Initial failing runs retained. Full module separation, captions and all-resource accessibility matrix remain incomplete. Video chunk633.98kB; no performance claim from shorter files. |
| 17 FIXED_WITH_EVIDENCE (current-source scope only) | 1281 runtime files tracked, stale security/API claims. `docs/SECURITY.md`, `API.md`, `HANDOFF.md`, `AUDIT_REPORT.md`; `archive-runtime-assets.ps1`: archive then verify each SHA, `git rm --cached` ONLY. | **1281 originals /514231472 bytes remain on disk**; archive and recovered SHA all match, Exit0. `.qa/runtime-assets/20261006-121936/` retained privately. Latest indexed clean export `clean-results-20261007-033929/`: all nine commandsExit0; frontend65/0/0, backend321/0/0; lint/build/API build/redacted source secret scan and88 asset SHA parity allExit0. Previous failed/interrupted clean iterations retained. No history rewrite or history-wide secret-scan claim. Tools/fixtures kept; JWT families/four CSRF exemptions and bootstrap200 guest/401invalid/503outage documented. |
| 18 OPEN | Strict OCR older6/1/0 despite count/source-preservation successes. Parser deliberately does not invent source words/answers/marks. | B1 OCR/source tests passed, but not a strict-fidelity success. Re-run original-SHA seven-input strict comparator and full teacher-review publication separately; no comparison relaxation or image-specific answer memorization. |
| 19 NEEDS_EXTERNAL_EVIDENCE | Small local load cannot establish requested25/100/250/500×10min or5000 capacity. Existing isolated SeaweedFS/PG/Redis/HTTPS/HLS tools retained; `prepare-media.ps1` produces valid >32MiB fixture and checks size so resumed part2 is actually exercised. | Current local evidence must keep image/sample duration. No representative external staging/provider keys or public TLS/CDN/DRM available. Provider runbook in existing docs; no purchased service/deployment. Headless screenshots/local HTTPS do not certify public TLS. Absolute prevention of saving content/screen recording is not technically promised. |
| 20 FIXED_WITH_EVIDENCE | Objectives not unique; NULL/global code ambiguity. `models/extended.py`, `extended_service.py`, migration **f1c3e5a7b9d1**: scoped/global partial unique indexes; explicit course-first resolver, global fallback only without override. Conflicts abort, no random merge/delete/renumber of history. | B1 scoped/global duplicates and tenant/course distinction; live PostgreSQL NULL+scoped unique rejection and shared-student two-course explicit/global cases. Evidence belongs to actual quiz course, practice excluded. Migration head single and fresh/previous upgrade passed. |
| 21 FIXED_WITH_EVIDENCE | 27 text options became `[`; deletion could duplicate keys/change correct answer. API/draft/legacy validation caps26; frontend `mcqOptions.ts` allocates unused keys without altering historical snapshots and clears removed answer for review. | B1 four real-HTTP boundary parameter cases, bothaliases/draft/legacy;26 with Z accepted,27 rejected422/400not500. Frontend4 unit cases unique keys, answer preservation/clear, max26; historical snapshot keys untouched. |

## Registration acceptance

The latest user's screenshot is a **layout reference**, not a copied brand or
purple palette. `AuthView.tsx` retains the existing split-screen transition:
Arabic sign-in form on right, registration form on left. The shared switch has
sign-in on right and new-registration on left. `RegistrationWizard.css` uses
the platform's deep green/light/dark variables, not the reference purple.
**Two steps**, following the latest user request: personal details →
contact/password/create account. The earlier three-step result below is
historical evidence, not proof of the current two-step UI. Final submission
revalidates both steps; no hidden third review/OTP step remains.
SMS/OTP is removed at the user's request. Phone is explicitly unverified.
Email remains required for sign-in/reset, password minimum10 matches API, role
always student; no public teacher privilege chooser. Migrations persist contact
details; back/failed503 preserves form locally in memory, never password storage.

## Reproduction and command provenance

Use the repository instructions in `docs/QA_ROLE_REPRODUCTION.md`, then:

```powershell
./scripts/qa/prepare-production.ps1 -Project chemistryaudit2
./scripts/qa/run-video.ps1 -Stage Build
./scripts/qa/prepare-media.ps1 -Project chemistryaudit2
./scripts/qa/prepare-test-data.ps1 -Project chemistryaudit2
./scripts/qa/run-video.ps1 -Stage Backend
./scripts/qa/run-video.ps1 -Stage Integration
./scripts/qa/run-video.ps1 -Stage Browser
./scripts/qa/run-trivy.ps1
git -c core.safecrlf=false diff --check
```

Docker fault/integration, browser, load and restore suites must run
**sequentially**, not concurrently against the same project. Tests mount
current tests read-only; runtime app comes from rebuilt images. QA synthetic
credentials/certificates are private generated files, never source secrets.
Earlier failures remain evidence: unit286/6 (fixture issues), integration42/3
(one-off diagnostic wrongly counted as runtime API), focused browser2/2 (actual
axe defects). Harness now selects exactly one runtime by project/service and
`com.docker.compose.oneoff=False`, not arbitrarily the first match. No tests
removed or production rate limiting weakened to obtain a pass.

Final command results and remaining gates are appended only after execution.

## Executed results (this round only)

| Gate / exact command or repository entry point | Exit | Passed / Failed / Skipped | Local artifact / boundary |
|---|---|---|---|
| `run-video.ps1 -Stage Backend` | 0 | 293 / 0 / 0 | `api-unit-video-20261006-125114.xml`; API/encoder Expat4each, PostgreSQL fresh/previous migrations and missing-MPU recovery also0. |
| `run-video.ps1 -Stage Integration` | 0 | 45 / 0 / 0 | `api-integration-video-20261006-125513.xml`,1096.347s; actual PostgreSQL/Redis/private SeaweedFS/HTTPS/fault recovery. |
| `pytest tests/integration/test_session_maintenance_pg.py` via isolated qa-tests | 0 | 3 / 0 / 0 | `maintenance-pg-20261006.xml`,3.426s; private PostgreSQL schema, four delivery/cleanup consumers, crash rollback. Separate from the45-test collection, not one48-test run. |
| `run-video.ps1 -Stage Browser` initial full collection | 1 | 72 / 3 / 0 | `video-browser-Browser-20261006-131849.xml`,19.2min. Two legacy one-page signup selectors; one actual modal focus-restore bug. |
| Focused Playwright registration/security/reset/publication/two-tab cases | 1 | 4 / 1 / 0 | `browser-focused-final-20261006.xml`; original three failures corrected. New two-tab case incorrectly checked cached profile before hydration; trace shows probe401 at13:45:08.513Z then refresh200 and bootstrap200 at.538Z. |
| `playwright test ... tests/qa/auth-multitab.spec.ts` after waiting for actual bootstrap | 0 | 1 / 0 / 0 | `browser-multitab-20261006-v2.xml`; shared-cookie rotation,503/11s observation, bounded refresh, preserved account/draft, recovery. Does NOT certify every blob/upload/SSE/video two-tab matrix. |
| `check-clean.ps1` (reviewed index export) | 0 | frontend65 / 0 / 0; backend293 / 0 / 0 | `clean-results-20261006-134143/{commands.json,frontend.xml,backend.xml,gitleaks.json}`. npmci/lint/build/APIbuild/secret scan each0; clean image is NOT substituted for tested runtime. |
| `prepare-media.ps1` + `prepare-test-data.ps1` | 0 | n/a, assertions executed | Video45,835,131bytes/90s; PDF25,928,857bytes/8pages; new video/material/receipt checkpoint,3 byte ranges,0hash/permission failures,2843S3 objects. Existing objects retained. |
| `python -m pip_audit -r requirements.lock` | 0 | 80 dependencies / 0 known findings | `pip-audit-20261006.json`. First tool attempt missing pip-audit was fixed in the disposable QA image, not hidden. |
| `run-trivy.ps1` API + encoder | 1 each | API91High+1Critical; encoder108High+1Critical | `trivy-20261006-125754/{api.sarif,video-worker.sarif,commands.json}`,52distinctCVEs reviewed individually in native ledger. No suppressions. |
| Docker Scout fresh attempt | 1 | scan incomplete | Authentication blocked; neither zero nor older findings are reported as a current Scout success. |
| `python -m scripts.qa_extract_fidelity --output /qa/extract-fidelity-20261006-final.json` | 1 | 6 / 1 / 0 | All7original input SHA match fixtures. Biology10questions,7fullymatching,CER0.008645533: q3oxygen-word truncation; q6printed character/blank difference; q7two word corruptions. All flagged for teacher review. No invented words/answers or comparator relaxation. |

Clean-checkout failures are retained: mounting the export read-only caused20
collection errors because startup creates `uploads`; only the private export
mount was made writable. The next run292/1/0 saw an intermittent503 at the
MCQ boundary. No runtime change or relaxed assertion was made to hide that503;
the recorded sequential clean re-run293/0/0 passed. Its exact earlier cause
is not established, so this is not a claim that an admission-service defect
was diagnosed or fixed.

The current wizard passed site-green palette, left registration/right sign-in
geometry, unclipped switch, mobile RTL, light/dark axe and keyboard assertions.
`AccessibleDialog` now uses layout-effect close/focus restoration **before**
React detaches the native dialog. The focused quiz test proves Escape returns
focus to the opener. Reset-email polling waits up to30s for the actual durable
delivery loop's15s interval; it never substitutes a200 request for mail proof.
CI now prepares synthetic identities from APP_ENV=test, not by weakening the
production demo-account guard, and uses a current-media storage checkpoint.
CI uploads only JUnit/scanner identities/redacted results/synthetic screenshots,
not browser traces, cookies, secrets or backup payloads. Remote CI has not run.

### Mixed load before final seeder-guard rebuild

`run-video.ps1 -Stage Load` Exit0, completed13:59:27Z. This run uses the earlier
API/encoder identities in the first native ledger, not a claim that a later
rebuilt image was loaded. Valid45,835,131-byte/90s VP9+Opus video,25,928,857-byte
PDF; actual protected HLS512KiB ranges with changing offsets plus browsing and
one/two concurrent full PDF uploads. Video fixture reaches private S3 via QA
setup, so this is **not a direct public upload-gateway throughput test**.

| Sessions / actual seconds | Requests / throughput | Errors | p95 / p99 milliseconds | Browse p95 / video p95 / upload p95 |
|---|---|---|---|---|
| 1 /180.48 | 663 /3.67rps | 0 | 34.83 /47.03 | 38.42 /29.81 /2707.49 |
| 5 /180.54 | 3236 /17.92rps | 0 | 51.38 /111.25 | 49.84 /51.92 /4556.01 |
| 10 /180.54 | 6422 /35.57rps | 0 | 63.08 /167.15 | 57.35 /67.88 /3615.53 |

Peak cgroup memory bytes: API566284288,worker102469632,S3 1072939008,
PostgreSQL144076800,Redis11071488,encoder119107584,upload-gateway19628032.
Peak PostgreSQL connections19,active2. Peak API CPU73.4% of one CPU is close
to its0.75CPU cap; this is NOT headroom for a thousand users. Cgroup memory
includes cache and is not an application leak diagnosis. All errors including
429 would be recorded as one attempted request, never automatically retried.
No429 occurred in this run; the browser's deliberate429/no-loop test is
separate. Samples and precise per-run JSON retained under `.qa/audit2/load-*.json`.

Later inspection found the **seeder**, unlike Settings, only classified
`production` as deployment. `core/config.py:is_deployment_environment` is now
shared with `scripts/seed_teacher.py`; production_like/staging must also reject
demo-account creation/password resets and short bootstrap credentials. Eight
additional parameter cases were added, without enabling demos in production.
Final rebuilt-image results are recorded separately after actual execution.

### Final runtime rebuild / backend protection gate

`run-video.ps1 -Stage Build` Exit0; `-Stage Backend` Exit0:
**301/0/0**,45.689s, `api-unit-video-20261006-140230.xml`.
Expat4/0/0 in both runtime images, PostgreSQL fresh/previous upgrades2 gates,
and real missing-MPU recovery also Exit0. Missing part recovery returned200,
expired upload409, fresh replacement201, cleanup204; no server500.

Actual rebuilt identities (not mutable tags or the clean-export image):

- API `sha256:b89f26fa60dd681f2410252b17b2c631d74a08a4e2c248f08762a53dc1d6e015`.
- Encoder `sha256:056a126088a2fc5cae47719263de42b44bec1659aaf8ecfc05085c470e9f06ee`.
- Web `sha256:d2468afff0605bfbff4356808cd716bcdfb8501f00574f50c94631c86d8984ff`.

The new FFmpeg fixture uses a known-size WebM Segment whereas the older
canvas fixture used an unknown-size Segment. Boundary QA now updates that
Segment length when adding an EBML Void, preserving all real media bytes.
`tests/fixture_media.py` is test-only: upload limits and application validation
were not changed. Both exact5GiB acceptance and5GiB+1 rejection must be rerun;
the original failed fixture precondition is not treated as an upload result.

`run-video.ps1 -Stage Integration` initial final-image run Exit1,
**47/2/0**,1068.632s, `api-integration-video-20261006-140338.xml`.
Both failures are the old unknown-Segment-size fixture assertion, before an
HTTP upload; no actual accepted/rejected byte-boundary result is claimed for
those cases. All49 tests are retained for the complete repeat, including
the two failed video cases. The actual two-client proxy and concurrent
PostgreSQL maintenance cases passed in this run.

Final-image Trivy repeat Exit1 for each image:
`trivy-20261006-141841/`, API91High+1Critical, encoder108High+1Critical.
Full finding ID/message comparison with the prior scan has zero differences;
all52distinctCVEs remain covered by the individual native review. No ignore
or severity adjustment was applied. This is a failed release gate, not a pass.

Backend repeated after the QA fixture correction: Exit0, **306/0/0**,
56.940s, `api-unit-video-20261006-142157.xml`. The extra five cases verify
known/unknown Segment padding preserves original payload and exact declared
size, and reject malformed headers without creating output. Native Expat4each,
both PostgreSQL migration gates and missing-MPU recovery remain Exit0.

Docker Scout authentication was restored by the user's sign-in. Complete
repeat on the final images: `run-video.ps1 -Stage Scan -ApproveScout`, wrapper
Exit1, each scannerExit2; API6High/0Critical, encoder8High/0Critical.
SARIFs `scout-video-{api,video-worker}-20261006-142816.sarif`, command JSON
`video-commands-Scan-20261006-142816.json`. All8 findings have current per-CVE
assessment in the native ledger; scanner union57distinct IDs, not52.
Do not confuse resolved scanner authentication with a passed security gate.

`native-aligned-new.py` on each final image in128MiB/network-none/read-only
temporary containers: **10/0/0 each, Exit0**, actual libstdc++64-bit nothrow
aligned-new bounds. `native-aligned-{api,video-worker}-20261006-final.json`.
This does not test PBDS or every C++ consumer and does not waive raw GCC alerts.

Final runtime-original inventory verification: `archive-runtime-assets.ps1
-VerifyOnly -Manifest .qa/runtime-assets/20261006-121936/inventory.json`, Exit0;
all1281 original SHA match, zero runtime storage paths remain in Git's index.
Eight edited QA PowerShell tools also parse with zero syntax errors, Exit0.

### Full final-image integration repeat after fixture repair

`run-video.ps1 -Stage Integration`, Exit0, **49/0/0**,1301.333s,
`api-integration-video-20261006-142315.xml`. No exclusions/skips or application
limit changes. All real PostgreSQL race tests, proxy clients, maintenance,
SSE, Redis/storage fault recovery and the two formerly failing video cases
ran in this one complete collection. Synthetic accepted objects were read
back fully with SHA comparison, then retired through the application API.

| Boundary / actual bytes | HTTP | Peak anonymous bytes / delta | Peak raw cgroup bytes | OOM / restart |
|---|---|---|---|---|
| Material1GiB /1073741824 | 201 | 386113536 /18038784 | 1610444800 | none /unchanged |
| Material1GiB+1 /1073741825 | 413 | 372850688 /77824 | 1610072064 | none /unchanged |
| Video5GiB /5368709120 | 200 | 386670592 /90787840 | 1610600448 | none /unchanged |
| Video5GiB+1 /5368709121 | 413 | 323129344 /13418496 | 1610686464 | none /unchanged |

Raw cgroup usage includes reclaimable file cache. The largest raw value is
73728bytes above the1610612736-byte cap transiently; this is retained, not
filtered/smoothed. Kernel max-pressure events23506/51919 occurred in the video
cases; oom/oom_kill remained0 and usage settled below the same cap. Working
set/anonymous budgets passed. This proves a bounded byte-limit test, **not**
realistic5GiB video encoding throughput or a capacity/load conclusion: the
playable90-second fixture was padded with EBML Void.

Final source verification `verify-runtime-source.ps1`, Exit0: API112files,
encoder112files, web89assets/config, **zero SHA mismatches**, using fresh host
frontend build versus served assets. This verifies actual immutable image
code equivalence, not just Compose tags or a report date.

### Final full browser gate

`run-video.ps1 -Stage Browser`, Exit0: **78/0/0**,20.4minutes wall time
(JUnit sums556.07s of case execution, excluding shared-window fixture waits),
`video-browser-Browser-20261006-144501.xml`. ESLint Exit0/0errors/3 Fast Refresh
warnings; frontend build Exit0 with the633.98kB video-chunk warning retained;
Vitest **65/0/0**, Exit0; `npm audit --audit-level=high` Exit0/0known findings;
`git diff --check` Exit0. Command provenance in
`video-commands-Browser-20261006-144501.json`.

This complete run includes signup/signin, actual Mailpit reset mail,
password-change revocation, student/teacher navigation and ownership,
receipt approval/rejection/entitlements, notifications/real SSE, manual
assignment/essay grading, quiz/assignment publication/atomic retries,
Arabic schedules and invalid/stale inputs, original-source OCR review,
valid90-second video upload/encode/play/seek, interrupted multipart upload
plus browser reload, malformed media/revocation, mobile RTL/light/dark/axe,
and all three actual two-tab503/429/network refresh failures. Deliberate
real login429 did not auto-retry.119real enrolled courses hydrated with
peak4requests,119completed,0failures. These passed cases do not claim full
strict OCR fidelity or every combined two-tab/resource accessibility matrix.

Actual source artifact: `runtime-source-20261006T144647Z.json`, Exit0,
112API +112encoder +89web/config files,0mismatches.

### Actual backup failures and infrastructure repair (not a scanner waiver)

The clean-index repeat `clean-results-20261006-150943/` passed all eight
commands, Exit0: frontend65/0/0, backend306/0/0 (51.824s), source gitleaks,
npmci/lint/build and clean API build. It preceded the infrastructure fixes
below; a final reviewed-index repeat is still recorded separately.

`video-storage-20261006t151157z-c8b83fa9.json`: Exit1. Actual UID10001 API
backup could not create a snapshot under root-owned0755 `/backups/s3`.
`infra/backup-permissions.sh`, production Compose ops service, both drill
entry points and runbook now initialize ONLY `/backups` and `/backups/s3`
to10001:10001/0750, with no recursion or access to secrets/network. New backup
jobs use umask077. Existing backup contents are not rewritten. The API/S3
backup continues non-root. New `check-backup-permissions.ps1`: Exit0,
**3/0/0** cases, ten commands/assertions including expected negativeExit1,
retained in `backup-permissions-84320eae225440dbb8a962b4f2334697/commands.json`.
The original UID write fails; post-fix write succeeds with0600; symlink/file
targets fail before parent metadata changes, and old sentinel contents and
ownership/modes remain unchanged. CI has the same reproducible check, but
remote CI is not claimed run.

`video-storage-20261006t152130z-6cf922eb.json`: Exit1 after that repair. S3
restarted once during GETs; backup raised connection-refused and never wrote
a completed manifest. Actual HTTPS readiness returned200 after the finally
recovery, without deleting source data. Restarted-container memory counters
reset; a prior OOM event was not captured, so OOM is **not proven** as the
original restart cause. The pinned image's own CLI documents default
`s3.readerCacheSizeMB=0` as unlimited. Source/restore templates now use64MiB
reader budget, disable separate chunk cache, and set softGo `GOMEMLIMIT=384MiB`.
The source QA cgroup is still1GiB, not enlarged to hide this failure.
These settings are in `infra/docker-compose.yml` and
`infra/qa/production.override.yml`; API/encoder/web image payloads are unchanged.
The drill checks restart-count stability and cgroup OOM counters after backup.
Primary budget semantics are linked in the production runbook; a Go soft
budget does not guarantee a hard RSS ceiling or host/staging capacity.

### Successful full storage recovery after the two recorded failures

`video-storage-drill.ps1`, Exit0: **25 commands, all Exit0**,
`video-storage-20261006t152750z-fd458cec.json`, completed15:49:27UTC.
Snapshot `20261006T152829Z-b91eeaad`: **3113 objects /14,653,688,353 bytes**.
Every restored SHA-256 and metadata match; **0 discrepancies**. PostgreSQL
restore: **52 tables /33766 rows**,0 discrepancies. No old volumes removed:
the new `chemistryaudit2_restore_{pg,s3}_20261006t152750z-fd458cec` targets
are independent and retained after stopping their temporary services.

Actual API/Celery/encoder/upload gateway ran against both restored stores.
Five original valid90s videos retained original SHA and50 HLS outputs each,
anonymous access403; video/material/receipt verification included three
range checks,0 hash/permission failures. HLS range206/100bytes,
anonymous segment403, revoked manifest403. Lost multipart recovery returned
200/409/201/204 without500. Actual new browser upload/encode/play/seek and
malformed-media/revocation: Exit0, **1/0/0**,83.559s case,
`restored-video-20261006t152750z-fd458cec.xml`. Finally, the original services
were restored, HTTPS readiness200, source data and every backup preserved.

The source S3 snapshot finished with **0 restarts,0 oom/oom_kill** under the
unchanged1GiB cgroup. Raw peak1074749440bytes is retained, including a
transient1007616bytes above1073741824; max-pressure events76516. The restore
container did not have the source's1GiB hard limit: it used the available host
cgroup plus the same64MiB reader/384MiB Go soft budget. This is a recovery
and integrity result, not equivalent hard-limit/capacity evidence for restore.

### Sequential mixed load after returning to the original source stores

`run-video.ps1 -Stage Load`, Exit0, completed16:00:47UTC;
`load-20261006T160047Z.json` and `video-commands-Load.json`.
Same API/encoder image identities listed in the native ledger; the web was
still the earlier three-step build. Source-SHA verification afterwardsExit0,
`runtime-source-20261006T160053Z.json`:112API/112encoder/89web/config,0 mismatches.
Valid video45,835,131bytes/90s; PDF25,928,857bytes. Private-S3 fixture seeding
does **not** load-test the public direct-upload gateway; its actual browser
upload/resume behavior is tested separately.

| Sessions | Seconds | Requests | req/s | p95ms | p99ms | Errors |
|---|---|---|---|---|---|---|
| 1 | 180.28 | 667 | 3.70 | 30.08 | 49.74 | 0 |
| 5 | 180.55 | 3264 | 18.08 | 48.73 | 130.91 | 0 |
| 10 | 180.43 | 6344 | 35.16 | 57.39 | 154.93 | 0 |

At10sessions: browsep95/p99=53.97/153.13ms,
video58.65/153.58ms; uploads6787.82ms p95, two samples only (no reliable
tail estimate). Peak sampled memory bytes: API432627712, worker102019072,
S3628289536, PostgreSQL110972928, Redis11452416, encoder95002624,
gateway17633280. CPU peaks respectively65.26/6.56/28.06/9.87/2.13/0.38/0.37%;
PostgreSQL21 connections, active1. Sampling cannot prove every instantaneous
peak. No normal-load429; the intentional browser429 bounded-retry proof is
separate. No1000-active-user or requested external25–500×10min capacity claim.

## Latest two-step registration and distributed short-backoff revision

The all-live baseline `api-integration-video-20261006-165542.xml` passed
**50/0/0**, Exit0,1612.438s, before the new login backoff. It is not attributed
to the subsequent application image. Current Build17:25:33–17:27:03Z: Exit0;
current images are the17:30 scan table in the native ledger, plus web
`sha256:691c088c9c1c7ea71611b1b0f7b58ab4debb62b559c5476bcb57de31f1625c70`.

B2: `run-video.ps1 -Stage Backend`, Exit0, **307/0/0**,59.816s,
`api-unit-video-20261006-172703.xml`. All native Expat checks4/0/0 per image,
fresh/previous-head PG migrations and missing-multipart200/409/201/204 passed
again on this build. Added unit proves4wrong401 then short429, bounded1–10s
Retry-After without an extra authentication call/account-wide charge, normalized
HMAC key, second identity unaffected, and correct login after actual expiry.
The final live53-case round is distinct; interim failures are not counted as
a successful final gate until investigated and rerun.

Local frontend commands after the two-step edit: lintExit0/0errors/3existing
Fast Refresh warnings; buildExit0 with retained633.98kB chunk warning;
Vitest65/0/0Exit0. Initial sandbox build failed EPERM resolving index.html;
the same authorized invocation passed, not a code fix or assertion exclusion.

New source-fix-content QA tool: `verify-ffmpeg-magicyuv.py`, Exit0,3/0/0,
reverse-checks the official pinned MagicYUV patch in the exact7.1.5 release.
No binary exploit proof or raw native scanner waiver: latest Trivy91+1/
108+1 and Scout6/8High still leave the release gate OPEN. Full provenance and
all57 reviewed IDs are in `NATIVE_CVE_REVIEW_2026-10-06.md`.

### OCR candidates were measured and rejected, not substituted silently

No production Extract parser/model edit in this revision. Original strict v8
baseline remains6/1/0: biology10questions/7exact,CER0.008645533; PNG5/5exact.
The official pinned tessdata_best full comparison FAILED5/2/0Exit1:
biology9questions/4exact,CER0.138263666; PNG4questions/3exact,CER0.123123123.
Low-confidence word-crop modes also failed0/2/0Exit1 each: PSM7biology10/7,
CER0.014409222; PSM8biology10/7,CER0.012968300; bothPNG5/4,
CER0.010362694. Their weights/artifacts stay private and are not production
dependencies. Reproducible SHA-checked CLI tools/commands are tracked in
`QA_ROLE_REPRODUCTION.md`; no expected source words were fed to recognition.

The PDF skill's render-and-inspect workflow was used to view both original
biology pages at108dpi; visual source review confirmed the remaining diffs,
not permission to insert guessed words into arbitrary student material.
No real DOCX blind input was supplied, so passing DOCX units is not full live
Word fidelity proof. Strict OCR, native CVEs and external evidence remain open.

### Actual new53-case failure, diagnosed before the repeat

`api-integration-video-20261006-172832.xml`: **51/2/0**, Exit1,1645.037s.
The sequential entry point stopped there: no browser/source gate is attributed
to this failing iteration. Failures and changes were not hidden/excluded:

1. New repeated login timing probe compared entire error JSON, including the
   deliberately unique `request_id`, and exited1 even though HTTP401 was reached.
   `test_login_timing.py` now validates each UUID, header/body consistency and
   uniqueness, then compares ALL remaining contract fields unchanged. Failed
   probe diagnostics contain only synthetic status/sample evidence, no cookies.
2. The next real-client XFF test got only two401 before429: Docker reused a
   timing-client IP whose ten requests were still in the real Redis window.
   It now waits with the existing `clear_auth()` helper; no keys are erased,
   no limit is increased, and the exact12×401+2×429 assertion is retained.

This second failure also exposed a genuine security-header defect: early
middleware429 lacked HSTS. New `core/response_security.py` is a header-only ASGI
wrapper outside CORS/admission/upload/auth rejecting middleware; it does not
buffer SSE/video bodies, authorize requests or change CORS. `main.py` registers
it for consistent existing header policies on early errors/preflight. HTTPS
`infra/nginx-https.conf` supplies one HSTS header also on proxy errors/frontend,
with upstream HSTS hidden to prevent duplication; HTTP is not changed.
`test_response_security.py` adds12 status/secure combinations plus actual
early429 and CORS-preflight tests. A fresh image rebuild/full gate is required.

Positive subsets of the failed53 run remain narrow evidence, NOT a full pass:
real account+IP backoff4×401 then429/RetryAfter10 (5.242ms reject), second real
IP correct login200 during first cooldown, first recovered200 after real expiry,
both logouts204; no Redis reset/server sleep. Paused TLS SMTP reset HTTP remained
generic200: existing24.332/16.202ms, missing13.233/13.833ms (two samples/class).
Two durable encrypted jobs completed/ciphertexts erased with worker and Redis
broker stopped, after SMTP resumed. Public admission while Redis is down remains
fail-closed503; no promise of public reset availability without Redis.
These two-sample timings do NOT establish statistical identity indistinguishability.

### B3 security-header rebuild and unit gate

`run-video.ps1 -Stage Build`, Exit0, fresh immutable identities in the18:01
native scan table. Web rebuilt/recreated identity
`sha256:027f61f8d25f26344c8ecc4b66dc1183930b6f2bff04a6bf5b19e7169de229ed`;
the served two-step bundle will be verified against the final host build.
`nginx -t` on the actual proxy Exit0. Direct internal API CORS preflight,
without either proxy: OPTIONS200, approvedOrigin preserved, HSTS and nosniff
present, Exit0. First diagnostic used unavailable requests in the deliberately
minimal runtime and exited1; the corrected stdlib urllib probe passed without
installing anything in the runtime.

B3 `run-video.ps1 -Stage Backend`, Exit0, **321/0/0**,81.234s,
`api-unit-video-20261006-180048.xml`: includes all14 new header regressions.
Native Expat4/0/0 per image, fresh/previous-head migration gates and lost
multipart200/409/201/204 all passed again. Starlette TestClient/httpx and old422
constant deprecation warnings remain recorded, not failed runtime behavior.
Latest Trivy/Scout full findings are identical to17:30, but scans ran on the
new images: Trivy wrapper1/raw1each, Scout wrapper1/raw2each. Release remains
OPEN; completed scan artifacts are not a clean vulnerability gate.

### Docker client lifecycle defect in the timing harness

Second53-case iteration `api-integration-video-20261006-180232.xml`:
**52/1/0**, Exit1,1665.181s. XFF/client budgets and HSTS passed after repair;
the sole timing failure was the harness's late address observation: three
finished Docker containers exposed empty IP fields, not six measured live IPs.
The six child processes had returned0 after their real401/contract checks,
but this could not prove six independent addresses and was not called a pass.

`test_login_timing.py` now holds every new labelled client behind a bounded60s
start-file gate, captures all six nonempty/distinct IPs while still running,
then opens their gates. No Redis keys, limits, app configuration or authentication
outcomes are altered. Only temporary labelled clients are removed in finally.
Focused real repeat `timing-start-gate-20261006.xml`, Exit0,1/0/0; full53-case
repeat runs separately on the unchanged B3 API/encoder/web images. Neither
failing full iteration is converted into a successful full-suite result.

Intermediate source verification `runtime-source-20261006T182424Z.json` Exit0:
114API +114encoder +89web/config files, zero SHA mismatches. This is provenance,
not a substitute for the pending final browser/all-integration gates.

### Production-equivalent timing fixtures (not a crypto downgrade)

The focused gated probe passed its HTTP/IP/contract checks but its timing
fixture used the unit-test process's deliberately cheap Argon2 configuration
(APP_ENV=test). Its existing-account median191.625ms versus missing-account
996.858ms, with bootstrap median-difference interval[-1047.280,-698.032]ms,
therefore did NOT compare production-equivalent password hashes. Direct
inspection of the actual API confirmed that its real and dummy hash parameters
already match: time_cost3, memory_cost65536KiB, parallelism4, hash_len32,
salt_len16. No production password policy or authentication code was weakened.

The timing fixture now obtains only those nonsecret parameter values from the
running production entrypoint, asserts they equal the dummy hash metadata and
meet the production cost floor, and independently creates its synthetic hash
with those same costs. The next measured result must include this parameter
evidence. The preceding full rerun was interrupted with SIGINT only on its
label-verified chemistryaudit2 QA one-off, before continuing an invalid timing
comparison: pytest Exit2 / wrapper Exit1, not a successful full gate. Application
containers and data volumes were not deleted or reset. A new focused probe and
complete integration/browser/assets/source sequence are required and running.

Focused production-cost repeat `timing-production-cost-20261006.xml`: Exit0,
**1/0/0**,18.572s, six nonempty/distinct real Docker client IPs and30 samples
per class. Existing-wrong median1303.595ms/p952003.666ms; missing median1301.720ms/
p951888.972ms; bootstrap median-difference95% interval[-195.0225,112.911]ms.
The report verifies costs3/65536/4/32/16 for runtime, dummy and synthetic fixture.
These local simultaneous CPU/HTTPS measurements no longer show the prior
fixture-cost gap, but are not an assertion of universal timing indistinguishability.

### Final B3 PostgreSQL/integration gate

`scripts/qa/run-video.ps1 -Stage Integration`: Exit0, **53/0/0**,1700.714s,
`api-integration-video-20261006-184107.xml`, completed19:09:31Z. Same B3
immutable API/encoder/web identities, no app-source change or counter reset.
All collected tests ran: real overlapping quiz submission/answer uniqueness,
publication/payment/reset races, teacher read scope, actual byte boundaries,
replay grace, SSE, non-root runtime, shared limits, PostgreSQL maintenance,
seven individual service faults, storage compensation and worker crash recovery.
The earlier51/2,52/1 and interrupted runs remain retained failures/interruptions.

The in-suite timing repeat verifies actual Argon2 costs3/65536/4/32/16:
30 samples/class, existing median1204.0235ms/p951496.751ms; missing
median1153.3575ms/p951405.633ms; bootstrap difference interval
[-16.695,190.6235]ms. Real short backoff rejects in6.536ms with Retry-After10,
allows another client200 during cooldown and the first client200 after expiry;
no server sleep/counter reset. Paused TLS SMTP reset HTTP remains generic200:
existing23.511/18.133ms, missing15.311/14.365ms. Two encrypted durable jobs
completed and erased ciphertext with Celery worker and Redis broker stopped.
This two-sample reset timing observation is NOT statistical equality proof.

Subsequent Browser stage: lintExit0 (0errors,3 retained Fast Refresh warnings),
buildExit0 (633.98kB video chunk warning retained), frontend unit **65/0/0**,
Exit0. The78 browser cases are still running; no final browser pass claimed yet.

### Two residual three-step test scripts and clean CSS reproducibility

The first B3 Browser attempt exposed two stale QA flows, not registration API
failures: `account-security.spec.ts` and `auth-reset-ui.spec.ts` still clicked
the removed second Next and expected the third review heading. Seventeen cases
completed successfully and two timed out before the exactly identified QA
Playwright process tree was terminated (Exit1);59 cases were unfinished, NOT
recorded as skips/passes. No tests were deleted. Both flows now assert exactly
two progress steps and submit Create my account on the second step; all
password/reset/session-revocation checks remain intact. Focused actual browser
repeat `two-step-password-20261006.xml`: **2/0/0**, Exit0,15.9s; the complete
78-case Browser restart is separate and still pending.

`check-clean.ps1`, `clean-results-20261006-191222/`: eight commands allExit0,
frontend65/0/0 and API321/0/0 (59.393s); redacted current-source Gitleaks found
no leaks; npm ci reported0 known vulnerabilities. This did NOT establish byte
reproducibility: the clean CSS was107.23kB instead of77.40kB although all92
normalized frontend source files matched. Automatic Tailwind source detection
depended on checkout/ignored-directory context. `src/index.css` now uses
`@tailwind utilities source(none)` and explicit stylesheet-relative src/index
sources, following [Tailwind's source-detection documentation](https://tailwindcss.com/docs/detecting-classes-in-source-files).
The installed4.3.3 compiler verified root=none and the two explicit source paths.
The QA-only candidate and actual working-tree rebuild each Exit0 and generated
the original88 web assets with **zero SHA-256 differences**, preserving the
currently tested visual payload. Existing CSS/KaTeX/base styles are unchanged.
`check-clean.ps1` adds a failing-on-difference clean/working asset SHA gate;
fresh index export must rerun this ninth command after staging the fix.

Retained install warning: ESLint9.39.5 reports no longer supported. This is a
development-tool support warning, not a demonstrated runtime vulnerability or
one of the three Fast Refresh warnings; npm audit's zero-known-findings result
does not imply supported versions. No peer dependency was force-upgraded to
hide it. The video633.98kB chunk and Starlette/httpx/422 deprecations are retained.
