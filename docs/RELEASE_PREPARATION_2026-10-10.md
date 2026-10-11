# Release candidate preparation — 2026-10-10

Branch: `fix/queen-p0-handoff`. Starting commit: `2b4cb7d05ba499876140ab2193825388516ce02e`.

This document describes the changes and operational requirements. It does not
certify production readiness. Current-run commands, exit codes, test XML,
image identities, raw vulnerability reports and browser evidence are retained
locally under `.qa/release1010/`, excluded from Git. Earlier reports are not
evidence for this candidate.

## Publication checkpoint — 2026-10-11

The user explicitly requested uploading all project changes on 11 October.
This supersedes the preparation-only push restriction below for this upload.
Render was last observed with automatic deployment on commit; pushing may
therefore redeploy it. Uploading code is not a production-readiness sign-off.

At the user's stop request on 10 October, the 64-case integration runner was
stopped during the telemetry case, after 90% progress. The large-file streaming
case had failed; the four exact size-boundary cases had passed. No final pytest
summary or complete passing integration gate was obtained. The failure cause
still needs investigation; do not report the interrupted suite as passing.
All primary QA services were healthy after stopping the runner.

Frontend verification completed with 265 passing tests, lint and production
build Exit 0. Backend verification completed with 545 passing tests; its API
source is unchanged by the later frontend and Nginx fixes. Python and npm
dependency audits returned no findings. Fixed web/proxy images returned zero
HIGH/CRITICAL, while API/encoder retained 63/79 HIGH findings respectively.
These results do not clear the incomplete integration, failed mixed-load,
native security, external storage/worker/email or Render readiness gates.
The rebuilt final frontend still requires its remaining browser acceptance
checks; prior restored-browser evidence is explicitly from the earlier image.

Unrelated local files, QA evidence, secrets, media and backups are excluded
from this upload. Persistent private production storage, PC encoder preflight,
Celery ingestion connectivity, Resend sender/delivery verification and a
successful actual Render readiness check remain external operating requirements.

## Official assessment results

Migration `f7c9e1a3b5d7` adds nullable approver/time fields; it preserves old
scores and answers and does not fabricate historical approval. Legacy attempts
without frozen questions require historical evidence review before release.

Student submit/result/history responses redact official grades, correctness,
feedback and answer keys until the owning teacher explicitly approves the
submitted attempt. Student mastery excludes unreleased attempts. Essays and
short answers require manual marking; zero is a grade, NULL `graded_at` is not.
Objective marks may be computed internally. Practice remains separate from
official grading; practice essays remain pending rather than being marked by
literal matching or AI.

The teacher action is **اعتماد وإظهار النتيجة**. Approval locks the attempt,
requires every frozen answer to be marked and validates the frozen total.
Grading uses the same row lock and cannot change an approved result. The
student's pending message is **تم تسليم الاختبار، والنتيجة في انتظار اعتماد المدرس**.

## Player and assessment scope

Keyboard jumps display their actual accumulated duration inside the player,
forward right / backward left, for 800 ms. The overlay belongs to the fullscreen
container, has no pointer interaction, and retains the existing student seek
restriction. Inputs and editable controls do not trigger player shortcuts.

The separate units/lessons multi-select fields retain multiple IDs and support
removing one selection or clearing only one field. Existing server-side scope,
ownership, unit expansion/deduplication and entitlement validation remain in
force. Clearing units does not clear separately selected lessons.

## External production blockers

1. **Permanent private storage:** a working S3-compatible account, private bucket,
   endpoint, region, access key and secret are required. Configure both Render
   API and the PC worker for the same bucket. Keep credentials in the private
   environment/dashboard, never in Git or chat. Local Docker S3 QA is not proof
   that Render has been configured.
2. **PC worker:** configure the Render external PostgreSQL URL with TLS and the
   same storage credentials in `.env.video-worker.local`. Run
   `scripts/start-video-worker.ps1 -CheckOnly`, then start the worker and prove
   a real job reaches `ready` before enabling production processing. See
   [VIDEO_WORKER_PC.md](VIDEO_WORKER_PC.md). No port forwarding is required.
3. **Email recovery:** Resend requires a sending API key and verified sender.
   Enable email only after a synthetic recipient test. Disabled email does not
   provide working password recovery. Do not substitute an example sender.
4. **DRM:** current session-bound MP4/HLS authorizes access; an entitled viewer
   can capture received clear media. An IDM detection button alone does not
   prove a successful download. Do not describe token expiry, HLS, CSS, or
   disabled right-click as DRM. Real DRM requires encrypted packaging plus
   authenticated entitlement-bound license issuance and a compatible player.
   `VIDEO_DRM_REQUIRED` is fail-closed, not an implemented DRM provider.
5. **Native security review:** retain raw HIGH/CRITICAL findings. Custom native
   source fixes need independent review; runtime isolation is mitigation, not
   a fix for an unfixed native CVE. No suppression or version relabelling is
   part of this candidate. Python/npm audit success does not clear OS findings.

For a pricing reference, [Mux DRM](https://www.mux.com/docs/guides/protect-videos-with-drm)
lists a $100/month add-on plus $0.003/license, separate from video charges
(checked 2026-10-10). No provider was bought or configured. DRM cannot promise
100% protection against all recording methods.

## Existing files: preserve before changing storage

Inventory the current database references and every source file before a
Render restart/redeploy. Export to a private backup with object key, owner,
size and SHA-256 manifest. Copy to the new private bucket without deleting
the source. Verify every byte count/hash, authorized downloads and anonymous
denial. Change references only after all copied objects verify; retain the
original backup through acceptance and the rollback window. A database record
alone does not establish that its media still exists. Render's ephemeral disk
is not production storage ([Render documentation](https://render.com/docs/free)).

## Deployment and rollback order

No production deployment is authorized in this preparation task. A push to an
auto-deploying branch is itself a deployment trigger; do not push until that
conflict is resolved. `render.yaml` specifies automatic deployments off, but
the actual dashboard setting must be checked separately.

Read-only inspection of the user's Chrome Render tab on 2026-10-10 found the
service live on `788aec123a697cb941f2cd8c391e029ff3be5cc6`, using the Free native
Python runtime, with **Auto-Deploy: On Commit**. Its root is `apps/api`; build
is `pip install -r requirements.txt`; start is `alembic upgrade head && python
scripts/seed_teacher.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
The pre-deploy command and health-check path are empty. No production setting
was changed and no deployment was started.

The repository blueprint now declares `healthCheckPath: /api/v1/ready` for
the API. Its offline production-settings check passed. This does not update
the existing native-Python dashboard service or certify its readiness.

With explicit permission, only environment-variable names were read. Redis
and Resend names exist; no S3 names appeared in the service variable list.
`NITIAL_TEACHER_EMAIL` appears misspelled. Demo and password-reset flag names
also exist, but their values were not read, so activation and connectivity
remain unverified. This evidence does not establish working permanent storage
or working email delivery. See the private local observation JSON for details.

After explicit release approval:

1. Freeze writes and take PostgreSQL plus S3 snapshots. Restore both into NEW
   stores and compare all tables/rows, object hashes and access controls.
2. Provision and test private storage, database TLS and Redis. Confirm sender,
   stable frontend origin, trusted proxy ranges and private secrets.
3. Deploy the matching API, run `alembic upgrade head` once, verify readiness
   and existing accounts. Keep reset-password/demo seed flags false. The
   obsolete Gemini/Groq credential inputs have been removed from Render's
   template; existing dashboard values require a separate dashboard review.
4. Deploy the matching frontend. Verify cookies, CSRF, refresh and stable
   origin login through the Vercel proxy. Do not wildcard preview origins.
5. Start and verify the PC worker, perform a synthetic video job, then enable
   processing. Prove every offered rendition, seek, logout/revocation and
   pending/approved quiz flow before inviting external testers.

Prefer rolling back application images with the additive migration left in
place. Do not run destructive downgrades or restore a stale backup over a live
database. If data restore is necessary, restore into new stores, verify and
switch after reconciliation. Restoring an older backup can lose later writes.

## Deferred improvements and limits

The restored browser journey on 10 October exposed a real grading UI defect:
an immediate read after marking could reuse a pending solution cached for 15
seconds, reset the displayed marks, and prevent approval on that click. Both
solution reads now bypass that cache. The regression covers an unmarked
approval followed by an explicit zero and a single successful approval action.
Submission copy no longer promises immediate official correction. Results
with awarded partial points are labelled partial, rather than wholly wrong.
Account changes also clear the previous account's notices and delayed error
notifications; navigation within the same account still preserves errors.
The complete frontend suite passed 265 tests in 40 files on the pinned Node 22
image, with lint and production build Exit 0. Four existing lint warnings and
the large-chunk warning remain; neither was suppressed. The interrupted/failed
Windows test runs are retained separately rather than reported as passes.

Actual Render readiness returned HTTP 503 after startup. Its project listed
the API, PostgreSQL and Valkey, with no Celery worker listed in that project.
The deployed source defaults to Celery ingestion, so a missing/unconnected
worker is a plausible cause; names-only settings inspection cannot establish
the exact failing dependency. Local-directory storage was also reported by
the running service. Do not disable readiness checks to hide these failures.

The current local mixed-load run stopped at ten sessions after S3 memory
exceeded its unchanged 1 GiB safety threshold for three samples. One and five
sessions completed without request failures. This remains a failed capacity
gate. Actual API/encoder image scans retained 63/79 HIGH findings respectively
(zero CRITICAL); the current distribution repositories offered no upgrades.
The native review remains open, even where source backports are documented.
An additional scan of the actual Nginx web image found CVE-2026-103111 in
PCRE2 10.48-r0, with stable 10.49-r0 available from Alpine v3.24 main. The web
runtime and the proxy/upload-gateway Dockerfile now install that exact fixed
package. Both rebuilt images scanned with zero HIGH/CRITICAL (Exit 0), and
nginx configuration checks passed. The original vulnerable scan is retained;
the API/encoder's separate 63/79 HIGH findings remain open. Frontend Docker
builds also exclude .env files instead of copying environment secrets.

Large frontend bundles remain a performance improvement, distinct from
authorization/storage/recovery blockers. Marketing counts should be backed by
real data before public publication. Biology OCR accuracy remains deferred;
no parser, AI, indexing, SMS, profile photos or video translation was added.
Small local load tests cannot establish capacity for 1,000 concurrent users.

QA project `chemistryrelease1010` is explicitly allowlisted alongside the
previous local projects. Fault tests still require `QA_ISOLATED=true` and
verify Docker Compose project/service ownership. They must never run against
Render or real users. QA volumes/backups are retained, not deleted.
