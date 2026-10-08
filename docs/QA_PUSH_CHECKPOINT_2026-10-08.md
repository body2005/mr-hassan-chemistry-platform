# Work-in-progress push checkpoint — 8 October 2026

The user explicitly requested publishing the current work BEFORE completion
of the remaining QA gates. This supersedes the earlier wait-until-finished
push instruction; it does not approve deployment, merging or scanner waivers.
Target: `fix/queen-p0-handoff`, remote/base HEAD verified immediately before
the checkpoint: `429848608834c7c012e3b2c9e7fcc4eb71f93ac0`.
The actual resulting commit and remote equality must be checked after push;
this document alone is not evidence of a successful GitHub operation.

Counts below are Passed/Failed/Skipped, not collection counts. Full reports
and chronological failures are retained in [current QA](QA_2026-10-08.md).
Private raw logs, cookies, traces, uploaded files, backups, local secret files
and Docker volume data are NOT part of this commit.

## Completed evidence on the current application bytes

| Gate | Result | Exit code |
|---|---|---|
| ESLint | 0 errors; 3 reviewed Fast Refresh export warnings retained | 0 |
| TypeScript/Vite build | Successful; large video chunk warning retained | 0 |
| Full frontend units | 141/0/0 | 0 |
| Complete browser journeys | 88/0/0, 1797.131209s | 0 |
| Full API units | 388/0/0 | 0 |
| Complete live integration | 57/3/0, all 60 executed, 2210.031s | 1 |
| Standalone byte-boundary diagnostic, unchanged app/limits | 5/0/0, 485.984s | 0 |
| Approved npm audit | 353 dependencies, 0 known findings | 0 |
| Approved PyPI audit | 81 actual-image/lock-matched dependencies, 0 known findings, 0 skipped | 0 |
| Post-suite source/runtime equivalence | 428 frozen source files unchanged; API/Celery/encoder 123 each and web 90 match | 0 |

API image `sha256:d8c8c6ffa0fbb163ae84faf3eb2f4245ea67103710e0ddd7167b21a329627691`;
encoder `sha256:9f228147d40861c7e1caca15f5cac1852bcdf810bb8f8482270cb58f5e89bff3`;
web `sha256:26e6f035f89ce303e390312aab7d91c8e12c3d13679e4a938a27b34a8de652f2`.
These are tested local images, not images deployed on an external server.

## Open failures and incomplete gates

| Item | Current evidence / remaining work |
|---|---|
| Exact 1GiB material memory | Full integration accepted 201 and matched downloaded SHA, but anonymous RAM peaked 552,833,024 bytes above the unchanged 512MiB budget. Root cause/repair remains open. |
| Exact 5GiB video admission | Full integration returned 503 Admission service temporarily unavailable instead of 200; Redis renewal logged TimeoutError. Do not assume TTL expiry or label passing isolated repeats a fix. |
| 5GiB+1 rejected-video memory | Correct 413, but anonymous RAM peaked 539,918,336 bytes above the same 512MiB budget. No quota/buffer/container cap raised. |
| Long-lived/warmed reproduction | Prefix concurrency/session/SSE cases followed by all five byte-boundary tests are running; no complete result was available when this checkpoint was prepared. The earlier standalone 5/0/0 does not close the failed full gate. |
| Native scanner gate | Scout 3 High/0 Critical EACH API/encoder, raw exit 2 each; Trivy 62 High API/78 High encoder, 0 Critical, raw exit 1 each. All 38 unique union CVEs individually triaged, but source backports/configuration restrictions are not scanner clearance or independent acceptance. See [native review](NATIVE_CVE_REVIEW_2026-10-06.md). |
| Final recovery/backup/restore | Repeat the encoder crash/retry and frozen-writer SeaweedFS/PostgreSQL restore into NEW stores on this final code, compare all object hashes/metadata and database rows, and exercise restored browser upload/playback/seek/permissions. Earlier runs and guard-only tests are not final acceptance. |
| Final performance | Repeat longer realistic-media mixed browsing/video/file load with throughput, p95/p99, errors, RAM and PostgreSQL connections. No demonstrated 1000-user capacity; representative external staged load remains unavailable. |
| Clean checkout acceptance | Latest indexed-source clean install/build/full unit/native image build still pending. A pre-push secret/diff check is not this complete gate and not remote CI success. |
| Remaining architecture work | Video/quiz responsibilities have been split into tested components/hooks, but the earlier larger modularization request is not fully closed. No unmeasured performance claim from reduced line counts. |
| External infrastructure | Public trusted TLS, externally deployed production server, CDN/DRM provider integration and real-domain delivery have NOT been provisioned/tested. Local self-signed TLS can still display a browser warning. |

No production readiness claim. Concurrency/PostgreSQL quiz submission passes
in the full integration suite do not prove the three upload failures safe.

## Explicit scope boundaries

- Biology Extract fidelity is deferred by the user. Identical original files,
  OCR models and parser outputs yield baseline/candidate EACH 6/1/0 with the
  same biology PDF failure. Native dependency parity is not fidelity success.
- Registration is TWO steps, site colors, no SMS, no personal account photos.
- Video subtitles/captions/transcripts are explicitly NOT requested.
- No technical protection can guarantee prevention of all copying/screen
  recording; signed session/entitlement checks are not a DRM provider license.
- All 1281 removed-from-index runtime assets remain on disk and in the verified
  private archive. This commit removes their Git tracking, not original data.
- Unrelated `pc_builder_3d_cases/` remains unchanged and excluded.

Operator reproduction tools are in `scripts/qa/`; commands and private
evidence filenames are documented in the current QA and production runbook.
Do not expose `.qa/` artifacts or populate Git with real deployment secrets.
