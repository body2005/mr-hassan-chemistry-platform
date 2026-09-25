# Phase 0 — Security Baseline and Threat Model

**Scope.** This is a code-evidence baseline for commit `9a7fb991b809e99fc090be89222034e7deb257ef`.  It is intentionally not a claim that the controls below are already enforced.  Route and data-flow evidence was collected from `apps/api/app/api/router.py`, its route modules, and the active React entry points.

## Baseline execution

| Check | Result | Evidence |
| --- | --- | --- |
| API health | pass | `GET http://localhost:8080/api/v1/health` returned `200` |
| Backend suite | fail | one failure: `test_upload_single_file_above_100mb_accepted`; the upload persisted as `QUEUED`, but the test expected a local dispatcher call while `allow_local_ingestion=False` |
| Web lint | pass with warnings | exit 0; three existing Fast Refresh warnings |
| Web build / typecheck | pass | `tsc -b && vite build`; main JS chunk is 666.24 kB (warning) |

## Authorization matrix

`Auth` means an authenticated session. `Relationship` is mandatory object-level scope that must be verified in the same query or a policy helper.  A `?` marks a known gap to be closed in Phase 1.

| Route family | Actor | Required relationship / expected policy | Baseline status |
| --- | --- | --- | --- |
| `/auth/register`, `/auth/login`, password reset | Public | rate limit, anti-enumeration, CSRF only once cookie auth is issued | partial |
| `/auth/me`, logout, password change, revoke/refresh | Auth | session belongs to caller; password change revokes caller's prior families | incomplete |
| `/courses`, modules, lessons, publish, reindex | Teacher/Admin | `can_manage_course(course_id)`; course belongs to caller institution and teacher owns it | partial / audit required |
| course enrollments and student course reads | Student/Teacher/Admin | student is enrolled; teacher owns that course; admin is same institution | partial / audit required |
| lesson video, transcript, stream, summary, AI ask, progress | Student/Teacher/Admin | `can_access_lesson_asset(lesson_id)` via course ownership or active enrollment; signed media token is purpose-bound | partial / audit required |
| questions, versions, quizzes, attempts, assignment attempts | Teacher/Admin or enrolled Student | teacher manages course; student can read only published items and own attempts; never expose answers before permitted | known gap: question-version reads |
| submissions and grading | Teacher/Admin or owning Student | `can_access_submission`; teacher owns the associated course; student owns submission | known gap: broad teacher scope |
| grades, mastery, risk, analytics | Teacher/Admin or owning Student | `can_access_student` plus course ownership; aggregate queries limited to managed courses | known gap |
| `/users`, audit logs, block/delete user | Institution/Platform Admin | same institution for institution admin; platform scope only for platform admin | known gap: teacher user listing |
| AI/report jobs and runs | Job owner/Admin | `can_read_job`; institution scope and owner match | known gap |
| knowledge sources, outline, relations, previews, downloads, page assets | Teacher/Admin or authorized enrolled Student | source/course/lesson relationship, source type, institution and role are all checked | partial / audit required |
| knowledge upload, reindex, stop/delete | Teacher/Admin | source and target course/lesson are teacher-managed | partial / audit required |
| payments, receipts, entitlements, pricing | owning Student / Institution Admin | order belongs to caller; pricing object belongs to institution and managed course | partial / audit required |
| `/system/asr-config` | Platform/Admin only | no public provider address or secret; generic capability response | known gap |
| transcription callback | service principal only | signed callback secret and job ownership; no browser session authority | audit required |
| `/health`, `/ready` | Public | no secrets or tenant information | expected |
| `/metrics` | private operations network | not publicly routable | audit required |

## Data flows

### Authentication and session

```text
Browser -> /auth/login or /auth/register -> AuthResponse (currently includes token)
        -> lmsService/apiClient -> localStorage lms_session_token -> Authorization: Bearer
        -> /auth/me -> API dependency decodes the bearer/cookie token -> current User
```

The intended Phase-1 replacement is `HttpOnly` access and rotating refresh cookies, an in-memory `expires_at` display value only, CSRF on cookie-authenticated mutations, and a single-flight `/auth/refresh` retry.  `401` may refresh once; `403`, network failures, and `502` must not clear the identity.

### Student AI and retrieval

```text
FloatingAITutor (mounted by App.tsx)
  -> POST /api/v1/tutor/chat (ai_demo.py)
  -> current-user/course authorization + retrieval
  -> grounded_answer.py / knowledge_retriever.py
  -> model or local text matching -> TutorChatResponse -> browser
```

The server currently appends `المصدر بالمقرر` and citations.  Phase 3 will retain internal provenance for audit while removing source metadata from every user-facing payload.  Retrieval must stay constrained to sources the current student is authorized to read.

### Teacher analytics

```text
Teacher UI / teacher prompt -> analytics_report.py, platform_service.course_analytics,
                              and ai_demo.py live analytics
                           -> ORM queries over courses, progress, attempts, submissions
                           -> aggregate/answer -> browser
```

There is not yet one metric catalog or one policy boundary.  Phase 2 will centralize allowlisted metric tools, normalize denominators, and require teacher-course ownership before every filter.

### Upload and indexing

```text
Teacher upload -> knowledge_center.py validates scope -> randomized stored object
  -> KnowledgeSource(UPLOADED/QUEUED) -> _enqueue_source_processing
  -> configured dispatcher/worker -> parsing/OCR/indexing -> INDEXED or FAILED
  -> preview/download routes enforce source relationship and purpose-bound preview token
```

The 100 MB baseline test exposed an ambiguous contract: persistence as `QUEUED` succeeds when a local dispatcher is disabled, but the test simultaneously expects immediate enqueue.  Phase 1 will preserve production's explicit dispatcher requirement and separate persistence-contract and dispatcher-contract tests.

## Threat model and Phase-1 controls

| Threat | Entry point | Impact | Required mitigation |
| --- | --- | --- | --- |
| IDOR / cross-tenant data access | IDs in courses, jobs, grades, assets, reports, payments | disclosure or modification of another teacher/student's data | centralized policy helpers; tenant plus relationship predicates; negative tests for another teacher and tenant |
| Token disclosure/reuse | JSON login response, browser storage, bearer header | account takeover | cookie-only access/refresh tokens, hashed rotating refresh records, reuse family revocation, no token logging |
| CSRF | cookie-authenticated writes | unauthorized state change | same-origin policy, per-session CSRF token/header, strict origin checks |
| Stored/reflected XSS | formulas, rich text, exports, AI text, CSV | session action/data theft | KaTeX `trust:false`, safe DOM rendering, strict HTML allowlist, contextual output encoding, spreadsheet formula escaping, CSP |
| Upload parser abuse | PDF/DOCX/PPTX/images/videos | RCE, disk/memory exhaustion, path traversal | magic-byte validation, streamed size/page/dimension/decompression limits, random storage names, worker timeouts and scan hook |
| DoS / rate-limit bypass | login, AI, OCR, upload, telemetry, reindex | resource exhaustion/cost | Redis-required production limiter, per-IP/user/institution quotas, trusted proxy validation, queue backpressure |

## Performance baseline

Only the health request was captured in this phase; no authenticated browser trace is safe to synthesize.  The build measured a 666.24 kB main JavaScript chunk.  Phase 4 will capture authenticated per-role request waterfalls, query counts, latency percentiles, and a staged 10-user load baseline before tuning.

## Explicit non-claims

This document does **not** claim that Cloudflare/WAF, production Redis enforcement, refresh rotation, complete IDOR protection, or a completed security audit is already active.  Those require the code changes and negative tests described in the subsequent phases.
