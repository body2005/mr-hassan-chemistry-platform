# Re-running teacher/student closure gates

Use a disposable local Docker project, never a production database. Commands
below are run from the repository root in PowerShell. They need Docker Desktop
and Node/npm, plus a Python runtime with `pypdf` for inspecting downloaded PDFs.
Set `$qaPython` to that Python executable. Do not put credentials in this file.

1. Run `./scripts/qa/prepare-production.ps1 -Project chemistryaudit2` on a fresh
   checkout. This writes random secrets and a self-signed local certificate into
   ignored `.qa/audit2/`. Review the generated local environment before use.
2. Build and start the production template plus isolated QA/video overlays:
   `./scripts/qa/run-video.ps1 -Stage Build`.
3. Follow `docs/QA_VIDEO_2026-10-04.md` and
   `docs/PRODUCTION_DOCKER_RUNBOOK.md` to generate the large synthetic media and
   seed the disposable teacher/student accounts and storage checkpoint. The
   storage checkpoint is needed for the live fault/restore tests; it contains
   synthetic IDs and private file hashes, not user content to publish.
4. Run `./scripts/qa/run-video.ps1 -Stage Tests` for backend unit/security,
   missing-multipart recovery and publication/playback tests.
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
10. With explicit approval to share image package/SBOM metadata, run
    `./scripts/qa/run-video.ps1 -Stage Scan -ApproveScout`. Nonzero is a real
    open security gate, not a reason to suppress CVEs.

NEVER overlap Browser, Integration, Recovery, Load or restore. Their deliberate
service failures and shared synthetic account counters would invalidate results.
The browser harness only isolates shared-IP login counters on allowlisted QA;
it waits for real user rate windows and does not relax production limits.

## New regression evidence

- `discovery.spec.ts`: assignment options/score/start, atomic failure and lost
  response, audience isolation, calendar outage/partial save retry, avatar
  reload/re-login, course selection and persisted binding, real profile data,
  printable Latin questions. Run the entire file, not only a passing selection.
- `test_role_discovery_regressions.py`: direct API/DB checks of those contracts.
- `test_audit_concurrency.py`: independent TCP requests released by a barrier
  and actual PostgreSQL row counts (including publication and submission).
- `test_assignment_pdf_fonts.py`: glyph coverage and science text. Also run
  `python -m scripts.qa_assignment_pdf` in QA (writes `/qa/role-pdf-fonts.pdf`),
  render with `pdftoppm`, and inspect the rendered page visually.
- `qa_extract_fidelity.py`: strict stem/type/ordered options/blank/formula
  comparison. A correct number of questions alone is NOT a pass.
- `qa_ocr_candidate.py`, `qa_ocr_lines.py`, `qa_ocr_ensemble.py`,
  `qa_ocr_words.py`: rejected candidate experiments. They override OCR ONLY
  inside the QA process; they are not production fixes. The reference is read
  by the comparator, never used as runtime OCR input or a correction dictionary.

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
