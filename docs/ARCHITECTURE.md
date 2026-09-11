# Architecture — Educational LMS Platform

> Status: living document. Updated as implementation lands. Last full revision: 2026-08-26.

## 1. System Context

```
Browser (React 19 + TypeScript + Vite)
        │  HttpOnly session cookie (SameSite=Lax), CSRF token
        ▼
FastAPI  ── /api/v1 ───────────────────────────────┐
   │            │                                  │
   │      Service Layer                    AI Provider Layer
   │      (business rules, RBAC,           ├─ Ollama (local)
   │       tenant scoping)                 ├─ Groq / OpenAI-compatible
   │            │                          └─ Mock (tests only)
   │      Repository / SQLAlchemy ORM
   │            │
   ▼            ▼
PostgreSQL   Redis (cache, rate-limit, queues, scheduling)
(source of truth)     │
                      ▼
              Background Workers
        (AI jobs, notifications, reports,
         analytics aggregation, video pipeline)
                      │
                      ▼
        MinIO / S3-compatible object storage
        (videos, PDFs, submissions, report artifacts)
```

## 2. Monorepo Layout

```
D:\learning project\
├── apps/
│   ├── api/          # FastAPI application (main platform backend)
│   │   ├── alembic/  # migrations — the only way schema changes
│   │   ├── app/
│   │   │   ├── api/          # routers (HTTP concerns only)
│   │   │   ├── core/         # config, security, db, errors, middleware, rate limit
│   │   │   ├── models/       # SQLAlchemy ORM models
│   │   │   ├── schemas.py    # Pydantic DTOs (never leak ORM objects)
│   │   │   ├── services/     # business logic; routes stay thin
│   │   │   └── main.py
│   │   └── tests/            # unit + integration + security tests
│   ├── ai-service/           # dedicated AI intelligence layer (quiz gen,
│   │                         # essay grading, RAG tutor, risk ML, reports narrative)
│   └── web/                  # React SPA
│       └── src/
│           ├── views/ components/ hooks/
│           ├── services/     # typed API client (single fetch boundary)
│           └── types/
├── workers/                  # Celery workers (AI jobs, notifications, reports)
├── packages/                 # shared types (planned: generated from OpenAPI)
├── infra/                    # docker-compose, backup/restore scripts
├── docs/                     # this documentation set
└── tests/                    # cross-cutting E2E specs
```

## 3. Layering Rules (enforced by review)

| Layer | May depend on | Must never |
|---|---|---|
| `api/routes` | services, schemas | touch ORM sessions or SQL directly |
| `services` | repositories/models, other services | read request/response objects |
| `models` | base mixins only | import services/routes |
| web `views` | hooks + api client | call `fetch` directly, own business logic |

## 4. Data & Tenancy

- PostgreSQL is the single source of truth. localStorage in the browser holds **only** theme/language/UI prefs.
- Every tenant-scoped row carries `institution_id`. The server derives institution membership from the authenticated user/session — never from a client-supplied id.
- All queries in tenant-scoped services filter by the caller's institution; cross-tenant access returns `403` (not `404`) for admins debugging, `404` otherwise.
- Money-free domain; timestamps stored UTC (`timestamptz`), rendered per-user timezone with `Africa/Cairo` default.

### Key entity groups (see `apps/api/app/models/`)
- Identity: `User`, `Institution`, `PasswordResetToken`, `RevokedSession`
- Curriculum: `Course → CourseModule → Chapter → Lesson → LessonAsset`
- Progress: `Enrollment`, `LessonProgress`, `VideoEvent`
- Assessment: `QuestionBank`, `Question`, `QuestionVersion` (immutable history),
  `Quiz`, `QuizQuestion`, `QuizAttempt`, `QuizAttemptAnswer`
- Assignments: `Assignment`, `AssignmentSubmission`, `SubmissionVersion`,
  `Rubric`, `RubricCriterion`, `Grade`
- Notifications: `Notification`, `NotificationRecipient`, `NotificationSchedule`,
  `NotificationDelivery` (dedup on event_type+source+recipient)
- Calendar: `CalendarEvent` (UTC, recurrence rule field)
- Certificates: `Certificate` (verification token)
- Analytics/AI: `LearningObjective`, `StudentMastery`, `RiskAssessment`,
  `Intervention`, `ReportJob`, `AIJob`, `AIRun`, `IdempotencyKey`, `AuditLog`

## 5. Request Lifecycle

1. Middleware assigns `request_id` (UUIDv7-ish), starts structured log context.
2. Security headers applied; CORS restricted to configured origins.
3. Session auth resolves user from signed HttpOnly cookie; CSRF checked on mutations.
4. Route → service. Services enforce role → tenant → ownership checks explicitly.
5. Sensitive POSTs may require an `Idempotency-Key` header (submissions, grading,
   certificate issuance, notification dispatch); replay returns original result.
6. Errors exit through the unified handler: `{error:{code,message}, request_id}`.
7. Audit-worthy actions write `AuditLog` rows inside the same transaction.

## 6. Exam Integrity Model

- Server owns time: attempt row stores `started_at`/`expires_at`; every answer
  save and submit is validated against DB clock. Client countdown is cosmetic.
- One active attempt per (student, quiz) enforced by a partial unique index.
- Submission is transactional: lock attempt row (`FOR UPDATE`), verify expiry,
  persist answers, auto-grade objective items, enqueue essay grading job.

## 7. AI Architecture

- Platform never calls providers inline for heavy work. `POST /api/v1/ai/jobs`
  enqueues to Redis; a worker runs provider adapters and persists results.
- `AIRun` records task, provider, model, prompt_version, input hash, latency,
  token usage, status (`success|error|timeout|fallback|cancelled`). Fallbacks are
  explicit and surfaced in API responses — never silent.
- Essay grading: AI produces `suggested_score/criteria_scores/feedback/confidence`;
  teacher approval required before final grade (workflow state machine).
- Tutor: RAG over lesson chunks with citations; below similarity threshold the
  tutor refuses rather than invents.

## 8. Background Work

Celery over Redis broker. Queues: `ai`, `notifications`, `reports`, `analytics`.
Retries with exponential backoff, max attempts, then dead-letter queue table for
inspection. Notification dispatch deduped via unique constraint before send.

## 9. Environments

`development | testing | staging | production` selected by `APP_ENV`.
`.env` holds real values locally (git-ignored); `.env.example` holds placeholders.
Production startup refuses default `SECRET_KEY`.

## 10. Observability

- Structured JSON logs with request_id everywhere.
- `/health` (liveness: process up), `/health/ready` (checks PostgreSQL, Redis,
  object storage, AI provider reachability individually).
- Metrics endpoint exposes request rate/latency percentiles and error rates.
