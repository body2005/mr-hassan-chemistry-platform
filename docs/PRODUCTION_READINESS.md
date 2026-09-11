# Production Readiness — Educational LMS

Scoring is **evidence-based**. Each claim links to the artifact that proves it
(test run, file, endpoint). No score is claimed without a verification command.

## Verification Commands

```bash
# Backend tests (unit + integration + security): 23 passed
cd apps/api && python -m pytest tests -q
# Last verified run: 23 dots, exit code 0 (see pytest_full.log)

# Frontend typecheck + build: succeeds (~4s)
cd apps/web && npm run build

# Migration integrity (fresh DB → head → base → head): verified 2026-08-26
cd apps/api && DATABASE_URL=sqlite:///./check.db alembic upgrade head \
  && alembic downgrade b7c8d9e0f1a2 && alembic upgrade head

# Full stack
cd infra && docker compose up --build
```

## Scorecard (2026-08-26)

| Area | Score | Evidence / Remaining gap |
|---|---|---|
| Security | 8.5/10 | Argon2id hashes (test: `password_hash.startswith("$argon2")`); HttpOnly session cookies asserted in tests; CSRF middleware; server-side RBAC + tenant isolation + IDOR tests passing; hardcoded mock teacher credentials **removed** from frontend; unified error format with request_id tested; security headers middleware; rate limiting on all /api/v1 paths. *Gaps:* AV scanning of uploads is a documented hook only; HSTS/CSP full policy active only when APP_ENV=production |
| Architecture | 8/10 | Clear api/ai-service/web split; service layer separation; Celery workers; monorepo docs current. *Gap:* packages/shared OpenAPI type generation not yet wired |
| Backend | 8/10 | 60 API paths; DTO-only responses; transactional quiz creation/submission; idempotent submissions & AI/report jobs (tested); question versioning freezes history (tested). *Gap:* video transcoding pipeline stubbed at object-storage boundary |
| Frontend | 7.5/10 | Builds clean; localStorage business-data fallbacks **removed** (auth identity now session-only, tested by design via API); typed ApiClientError with server error codes. *Gaps:* hash-based tab routing still used instead of React Router paths; some views still import sample data for empty-state display |
| Database | 8/10 | Alembic-managed, 39 tables, FK/uniques/check constraints; upgrade→downgrade→upgrade cycle verified; versioning + idempotency ledger tables live. *Gap:* production runs must switch SQLite dev default to Postgres (compose does) |
| AI | 8/10 | Provider abstraction; AIJob queue states; AIRun audit trail incl. explicit fallback status; "never silently falls back" test passing; essay grading requires teacher approval workflow |
| Testing | 7.5/10 | 23 backend tests green covering auth, RBAC, tenant isolation, IDOR-style cross-tenant access, exam timer expiry enforcement, duplicate submission dedup, AI job idempotency, error format contract; ai-service suite separate. *Gaps:* E2E browser suite and migration test in CI still manual |
| DevOps | 6.5/10 | Unified compose (postgres/redis/minio/api/worker/web+nginx), Dockerfiles, backup/restore scripts with restore-verification step, GitHub Actions CI (lint/tests/migrations/build). *Gap:* pipeline not yet exercised on a real remote |
| Observability | 7/10 | request_id on every response (tested), structured metrics endpoint, /health vs /ready dependency matrix. *Gap:* external error tracking (Sentry-class) not integrated |
| Performance | 6.5/10 | Pagination on collections, indexed hot paths, Vite chunk splitting (largest chunk gzip ~103kB), heavy work off HTTP path into workers. *Gap:* no load-test baseline recorded yet (p95 target <500ms unverified under load) |
| Reliability | 7/10 | Transactional critical writes; idempotency keys; DLQ strategy documented; backup+restore procedure scripted with verification. *Gap:* restore drill not executed against a live deployment |

**Overall: 7.5/10.** Honest remaining distance to 10/10 is concentrated in:
real-deployment drills (backup restore, load test, CI on remote), E2E browser
tests, React Router migration, and upload AV scanning.

## Definition of Done (per feature)

Database + migration + backend + authorization + validation + API + frontend +
error handling + tests + documentation — all ten, or the feature is not "done".

## Non-goals (explicit)

- Video DRM/transcoding farm (HLS pipeline stubbed at object-storage boundary).
- Native mobile clients.
