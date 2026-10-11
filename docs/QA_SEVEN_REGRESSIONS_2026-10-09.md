# Seven reported regressions — 9 October 2026

Scope: the seven specific grading, progress, upload and Docker-email reports.
This is **not** a claim that every platform release gate is closed.

## Source and concurrent work

- Branch: `fix/queen-p0-handoff`.
- Base HEAD and remote before this repair: `92b0d4f3e99d257a2b5222f0113988164a0537c3`.
- Another Codex chat owns the unrelated catalog/auth/frontend/seed changes.
  Coordination messages were sent with explicit human permission. Those dirty
  changes were neither overwritten nor included in the candidate image/commit.
- Candidate: a clean `git archive` of that HEAD plus only the ten repair/test
  files listed in `.qa/audit2/seven-source-manifest-20261009.json`.
- Tested API image: `sha256:f711994a4e96b8aaf0cc896f075e2f355b8fc7566764882d82f16f23db58c2d5`.
  Runtime user: `10001:10001`. All ten source hashes matched the export after QA.
- The shared `chemistryaudit2` API/web/workers were **not** recreated or stopped.
  The browser site is therefore **not evidence that this repair is running**.

## Before / after

| Report | Reproduced before | Cause and changed files | Verified after |
| --- | --- | --- | --- |
| Correct MCQ text marked wrong | Four Arabic/Latin-key versus option-text cases scored 0 instead of 10; two wrong-answer controls already passed | Literal answer comparison. `mcq_answers.py`, `question_policy.py`, `platform_service.py`, `routes/platform.py` now resolve the frozen option, with explicit keys and Arabic aliases; unknown/ambiguous choices do not earn points | SQLite route tests and real HTTPS/PostgreSQL submission score 10; student result and teacher solution use consistent option indices/letters |
| Practice changes official average | Official 0 plus practice 100 produced 50 | `/users` included practice attempts. `routes/platform.py` excludes `is_practice` from official totals and pending counts | Average 0, official attempt count 1, in SQLite and PostgreSQL |
| Edited bank type hides pending essay | After changing the live bank question to MCQ, pending count became 0 | Pending query joined mutable bank type. `routes/platform.py` uses the stored answer's ungraded state instead | Pending 1 and no final average; manual grade 7 yields pending 0 and average 70, including real PostgreSQL |
| Progress crosses courses | Completed course A incorrectly gave course B 100% | Analytics joined enrollment by student but not the progress lesson's course. `platform_service.py` joins lesson → module → matching enrolled course, with tenant/status filters | A=100%, B=0%, B completed lessons=0, including PostgreSQL |
| Anonymous file upload consumes body | Five upload families and invalid-token request consumed ASGI body and returned multipart 400 | FastAPI parsed uploads before route auth. New `upload_auth.py` and `main.py` authenticate/revoke/authorize before parsing and upload leases, inside admission limits | ASGI receive calls=0 on denials. Real HTTPS requests declare 1 MiB but send **zero body bytes**, and all five promptly return 401. Valid auth reaches parsing; wrong role/revocation/invalid Bearer are denied; rate limits and outage fail-closed are tested |
| Unpaid student forges progress | Explicit completion **already returned 403**. Video telemetry incorrectly accepted 202 and wrote progress | Missing entitlement check in `routes/telemetry.py` | Both endpoints return 403 with zero paid progress/events written; real lesson entitlement permits telemetry 202 and completion 200. Mixed free/paid batch rollback tested |
| Production reset feature disabled | Production Compose omitted `EMAIL_ENABLED` | Settings default false despite SMTP variables. `infra/docker-compose.yml` supplies `${EMAIL_ENABLED:-true}`; explicit operator opt-out remains possible | Candidate Compose `config -q` exits 0. Production-mode HTTPS API advertises feature enabled and delivers one reset email through certificate-verified TLS to a fresh local Mailpit sink |

No historical submitted grades were silently rewritten. The grading repair
applies to submissions; an audited historical regrade is a separate operation.
No external SMTP provider/server, deployment, purchase or real recipient was used.
The local API uses production settings for mail/TLS/auth with local test storage;
this targeted check does not replace the separate full production storage drill.

## Commands and results

Raw artifacts remain under `.qa/audit2/`; these paths are ignored deliberately
because that directory also contains local secrets and synthetic test state.
The tests and instructions are tracked; no secret directory is committed.

| Command / artifact | Exit | Passed | Failed | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: | ---: |
| `pytest tests/test_seven_user_regressions.py -q` — `seven-regressions-before-20261009.xml` | 1 | 3 | 15 | 0 | 0 |
| Correct fixture's missing `started_at`, then run only practice/essay cases — `seven-regressions-before-valid-fixture-20261009.xml` | 1 | 0 | 2 | 0 | 0 |
| Initial repairs, same new file — `seven-regressions-after-20261009.xml` | 0 | 18 | 0 | 0 | 0 |
| Add pre-auth limiter/admission preservation, run only six affected upload cases plus 13 new boundary cases — `seven-boundaries-after-20261009.xml` | 0 | 19 | 0 | 0 | 0 |
| `docker build -f <export>/infra/Dockerfile.api -t chemistrysevenfix-api:20261009 <export>/apps/api` | 0 | — | — | — | — |
| Live harness first setup: Docker exclusive `none` mode prevented network attach — `seven-live-setup-failed-20261009.xml` | 1 | 0 | 0 | 7 | 0 |
| Live harness second setup: host key unreadable by non-root API — `seven-live-key-permission-failed-20261009.xml` | 1 | 0 | 0 | 7 | 0 |
| Fixed harness isolation/key copy; `pytest /target/test_seven_regressions_live.py -q` — `seven-live-20261009.xml` | 0 | 7 + 5 subtests | 0 | 0 | 0 |
| Candidate production Compose `config -q` — `seven-compose-config-20261009.json` | 0 | — | — | — | — |
| `git diff --check` | 0 | — | — | — | — |

The first red run had **two fixture errors reported as failures**, not two
proven application defects. They were corrected and those two cases reproduced
the actual application bugs in the separate red run. The live setup failures
were harness issues before any test body ran; no application success was inferred.

There are **31 unique new SQLite/ASGI cases**, not 37: six cases were rerun after
their relevant middleware changed. Live QA adds seven test methods (five upload
subtests, so JUnit reports 12 successes), taking 22.10 seconds. The build also
ran its mandatory native-Expat preflight; no historical full suite was rerun.

## Reproduce from a clean checkout

Build a candidate API, and create the disposable QA tooling image from it:

```powershell
$docker = 'C:\Users\body\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
& $docker build -f infra/Dockerfile.api -t chemistry-seven-api apps/api
& $docker build -f infra/Dockerfile.qa --build-arg API_TEST_IMAGE=chemistry-seven-api -t chemistry-seven-tests apps/api
$candidate = & $docker image inspect chemistry-seven-api --format '{{.Id}}'
$repo = (Get-Location).Path.Replace('\', '/')
# Prepare LOCAL QA-only cert.pem/key.pem using scripts/qa/prepare-production.ps1.
# SANs must include proxy and mailpit. Never use a public server's private key.
$artifacts = "$repo/.qa/audit2"
& $docker run --rm --network bridge `
  -e QA_ISOLATED=true -e "QA_CANDIDATE_IMAGE=$candidate" `
  -e QA_REPOSITORY=/repo -e "QA_HOST_SECRETS=$artifacts/secrets" `
  -e QA_CA_FILE=/qa/secrets/cert.pem `
  -v /var/run/docker.sock:/var/run/docker.sock `
  -v "${repo}:/repo:ro" -v "${repo}/scripts/qa/tests:/target:ro" `
  -v "${artifacts}:/qa" --entrypoint python chemistry-seven-tests `
  -m pytest /target/test_seven_regressions_live.py -q --tb=short `
  --junitxml=/qa/seven-live.xml -o cache_dir=/tmp/pytest-seven-live
```

Use only a local disposable runner with Docker socket access. The harness
creates a new internal UUID network, pinned PostgreSQL/Redis/Mailpit fixtures,
fresh database, and the supplied candidate API. It publishes no ports, validates
TLS, never sends external mail, never disables real rate limiting, and removes
only its own fixtures. It copies the **local QA** private key with UID10001/mode
0400 into the disposable API; it neither chmods the host key nor runs API as root.

For the new in-process cases only:

```powershell
& $docker run --rm --network none -e STORAGE_DIR=/tmp/qa-storage `
  -e QA_REPO_ROOT=/repo -v "${repo}/apps/api:/srv:ro" -v "${repo}:/repo:ro" `
  --entrypoint python chemistry-seven-tests -m pytest `
  tests/test_seven_user_regressions.py tests/test_seven_regressions_boundaries.py `
  -q --tb=short -o cache_dir=/tmp/pytest-seven-unit
```

The clean-checkout commands are instructions for future reviewers, not a claim
that unrelated historical tests were rerun during this repair. Shared-runtime
updates must be coordinated with the other chat before recreating services.
Normal Git push is separate from Docker verification; no Actions dispatch,
merge, force-push or external deployment is authorized by this report.
