# Local review follow-up (not production readiness)

This round starts at4298486 on fix/queen-p0-handoff. No deployment/merge/history
rewrite. Changes require fresh unit, PostgreSQL/Redis integration and browser
proof before a status becomes FIXED_WITH_EVIDENCE.

8October update: use [QA_2026-10-08.md](QA_2026-10-08.md) for current tested
images, fresh raw security findings and unfinished gates. Numbers below are
chronological history, not final acceptance for later rebuilt application/native
images. Biology accuracy is user-deferred; all raw comparator failures remain.

- New RTL registration wizard matches the supplied visual structure but uses
  Mr Hassan branding and site-green palette, sign-in right/signup left. The
  latest revision has TWO steps: personal, then contact/password/create.
  SMS/OTP explicitly removed at the user's request.
- New migrations: f0b2d4e6a8c0 registration contact details, f1c3e5a7b9d1
  scoped/global objective identity, f2d4a6c8e0b2 encrypted reset-mail outbox,
  f3e5a7c9b1d3 uniform encrypted reset admission and UTC credential epochs.
- Objective conflicts abort migration for approved resolution, never merge or
  erase parent/mastery history. Inventory: GROUP BY institution_id,course_id,code
  HAVING COUNT(*)>1.
- Deprecated root Dockerfile removed after checking tracked deployment configs;
  supported context is apps/api with infra/Dockerfile.api:
  docker build -f infra/Dockerfile.api apps/api. Compose/Render already use it.
- Metrics/detailed readiness require platform admin. Public ready stays usable
  by unauthenticated probes and reveals only status.
- CI configuration is not evidence of a successful GitHub Actions run.
  Native High findings, OCR strict fidelity, external TLS/CDN/DRM/storage proof
  and representative staging capacity remain separate release gates.

Detailed current evidence, before/after status for all21 review items, command
exit codes, counts, failure history and immutable runtime image boundaries:
[`QA_REMAINING_REVIEW_2026-10-06.md`](QA_REMAINING_REVIEW_2026-10-06.md).
That ledger, not historical VERIFIED labels, is the local review handoff.
The7October continuation records the latest two-step clean/browser checks,
the correction retaining the original shared auth15/min ceiling, and new B4
image identities: [`QA_CONTINUATION_2026-10-07.md`](QA_CONTINUATION_2026-10-07.md).
Read its actual completed/pending gates; B4's78-case pass is not B6 acceptance.
Current B6 fixes stale lesson/account playback responses, removes fabricated
views/publication dates, separates HLS transport/option editing/source review,
and classifies actual lost upload reservations as503 instead of500. Current
frontend units92/0/0, lint/typecheck/build0; rebuilt API units345/0/0, Backend0.
The focused real Redis-outage/material-overflow/PG-compensation gate3/0/0
passes on B6. Full live/browser/timing/source/load/restore and raw final-image
scans must finish separately. Earlier failed full integration56/1/0 is retained,
not relabelled as a pass because focused tests succeed. No push yet this round.
