# Security Policy & Model — Educational LMS

## 1. Authentication

- Passwords hashed with **Argon2id** (`argon2-cffi`, sensible defaults). Plaintext
  never stored, logged, or returned. Login/register responses contain no secrets.
- Sessions: opaque random token (32 bytes, `secrets`), stored server-side
  (`sessions` table + Redis cache), delivered as `HttpOnly; SameSite=Lax; Secure`
  (Secure in production) cookie with TTL and sliding revocation on logout.
- CSRF: double-submit cookie (`matgar_csrf`); all non-GET requests require the
  matching header except the two anonymous endpoints (login/register), which are
  rate-limited instead.
- Password reset: single-use, time-boxed tokens (30 min), hashed at rest,
  invalidated on use and on password change.
- Production startup refuses default `SECRET_KEY` (enforced in Settings validator).

## 2. Authorization (server-side only)

Role hierarchy: `platform_admin > institution_admin > teacher > student`.
Checks run in this order for every sensitive request:

1. **Authentication** — valid session.
2. **Role check** — decorator/dependency declares minimum role.
3. **Tenant check** — resource's `institution_id` must equal caller's.
4. **Ownership check** — teachers act only on their own courses/quizzes/etc;
   students read only enrolled/published content.
5. **Resource permission** — state machine rules (e.g. cannot submit to an
   unpublished quiz, cannot grade before submission exists).

The frontend role display is cosmetic; the API never trusts client-supplied
role or institution id.

## 3. Tenant Isolation

- Every tenant-scoped query filters by the caller's institution inside the
  service layer (repository takes an explicit scope argument).
- Cross-tenant IDs yield `404` for regular roles; admins get `403` diagnostics.
- Integration tests cover cross-tenant reads/writes for every domain.

## 4. Input Validation & Injection

- All bodies validated by Pydantic DTOs; query params bounded (page_size caps).
- SQLAlchemy ORM exclusively (parameterized SQL); no string-concatenated SQL.
- File uploads: extension + MIME allowlist, size caps, randomized object keys,
  presigned URLs scoped per-object and short-lived.

## 5. Transport & Headers

Middleware sets: `Content-Security-Policy`, `Strict-Transport-Security`
(production), `X-Content-Type-Options: nosniff`, `Referrer-Policy:
strict-origin-when-cross-origin`, `X-Frame-Options: DENY`. CORS limited to
configured origins; credentials allowed only from those origins.

## 6. Rate Limiting

Sliding-window counters in Redis keyed by IP+route-class:
login/register (strict), AI job creation, file upload, report generation,
telemetry batches (generous). Exceeding returns `429` with `Retry-After`.

## 7. Audit Trail

`AuditLog` rows (actor, action, resource type/id, before/after JSON, request_id)
written transactionally for: login/logout, password change/reset, role changes,
blocking, course/quiz mutations, grade changes, certificate issuance, admin actions.

## 8. Secrets Handling

`.env` git-ignored; `.env.example` placeholders only. CI greps for known secret
patterns. Object-storage and DB credentials injected via environment in compose/K8s.

## 9. Known Residual Risks (tracked)

- Malware scanning of uploads is architecture-ready (post-upload hook) but no AV
  engine is bundled in dev compose.
- Video DRM is out of scope; signed URLs mitigate casual sharing only.
