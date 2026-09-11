# API Reference — `/api/v1`

All responses are JSON. Mutations require the CSRF header (`X-CSRF-Token`,
value of the `matgar_csrf` cookie) except login/register. Errors use:

```json
{ "error": { "code": "QUIZ_EXPIRED", "message": "This quiz attempt has expired." }, "request_id": "..." }
```

## Conventions

- **Pagination**: `?page=1&page_size=25&search=&sort=-created_at&<filters>` →
  `PageResponse[T] { items, total, page, page_size, pages }`
- **Idempotency**: sensitive POSTs accept `Idempotency-Key`; replaying the key
  returns the original response (24h window) instead of duplicating effects.
- **Auth**: session cookie set by `/auth/login` or `/auth/register`.

## Auth — `/auth`

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | /auth/register | public | first user may bootstrap platform admin |
| POST | /auth/login | public | rate-limited; sets HttpOnly session cookie |
| POST | /auth/logout | any | revokes session server-side |
| GET | /auth/me | any | current user from session |
| POST | /auth/change-password | any | rehash Argon2id, revoke other sessions |
| POST | /auth/password-reset/request | public | always 202; token emailed/stored |
| POST | /auth/password-reset/confirm | public | consumes single-use token |

## Users & Institutions

| Method | Path | Roles |
|---|---|---|
| GET | /users | institution_admin+, paginated |
| POST | /users/{id}/block | institution_admin+ (audit logged) |
| DELETE | /users/{id} | platform_admin |
| GET | /institutions/me | institution-scoped |

## Curriculum — `/courses`

- `GET /courses` — paginated; students see published only, staff see all in tenant.
- `POST /courses` (teacher+) · `GET /courses/{id}` · `POST /courses/{id}/publish` · `POST /courses/{id}/archive`
- `POST /courses/{course_id}/modules` · `PATCH /modules/{id}` (reorder via `position`)
- `POST /modules/{module_id}/chapters` · `POST /chapters/{chapter_id}/lessons`
- `POST /lessons/{lesson_id}/assets` — metadata for stored objects
- `POST /courses/{id}/enroll` (student; duplicate-safe) · `GET /courses/me/enrollments`

## Progress & Telemetry

- `GET /progress/me`, `GET /progress/lessons/{lesson_id}`, `POST /progress/lessons/{id}/complete`
- `POST /telemetry/video/batch` — batched video events (play/pause/seek/resume/
  ended/visibility/pagehide), idempotent per client batch id.
- `GET /telemetry/lessons/{lesson_id}/resume` — last position + watched duration.

## Question Bank — `/questions`, `/question-banks`

CRUD with search/filter (type, difficulty, topic, objective, status), pagination.
Mutating a question that has been used creates a new `QuestionVersion`;
historical attempts keep referencing the frozen version.

## Quizzes — `/quizzes`, `/quiz-attempts`

- `POST /quizzes` + questions in one transaction; `POST /quizzes/{id}/publish`.
- `POST /quizzes/{quiz_id}/attempts` — rejects if attempt limit reached or an
  active attempt exists; returns server-computed `expires_at`.
- `PUT /quiz-attempts/{id}/answers` — periodic save, server-time validated.
- `POST /quiz-attempts/{id}/submit` — idempotent; objective items auto-graded;
  essays queued for AI suggestion + teacher review. Expired attempts rejected.

## Assignments — `/assignments`, `/submissions`

- Teacher CRUD + publish; rubric attach (`Rubric` with weighted criteria).
- Student submit/resubmit — each submission creates immutable `SubmissionVersion`.
- `POST /submissions/{id}/grade` — teacher final grade; AI suggestion optional input.

## Grading — `/grades`

Final grade ledger per (student, course item); history retained on change.

## Notifications — `/notifications`

- `GET /notifications` (own), `POST /notifications/{id}/read`
- `POST /notifications` / `POST /notifications/broadcast` (teacher+/admin)
- Scheduling: worker executes due schedules (Redis-backed clock, not browser).

## Calendar — `/calendar`

List/create/update/cancel events. Stored UTC, recurrence via `rrule` string,
rendered in Africa/Cairo by clients.

## Certificates — `/certificates`

- Issuance is automatic when course completion criteria are met (transactional,
  idempotent). `GET /certificates/verify/{token}` is public.

## Analytics & Risk — `/analytics`

- `GET /analytics/courses/{course_id}` — aggregated server-side.
- `GET /analytics/students/{id}/mastery` — per learning objective.
- `GET /analytics/students/{id}/risk` — explainable score + contributing factors.

## Reports — `/reports`

`POST /reports/jobs` (async) → job id → `GET /reports/jobs/{id}` → signed download
URL when ready (xlsx/pdf produced by worker into object storage).

## AI — `/ai`

- `POST /ai/jobs` `{task, payload}` → queued `AIJob` (quiz generation, essay
  grading, document processing).
- `GET /ai/jobs/{id}` — state: queued|processing|completed|failed|cancelled.
- Essay suggestions appear to teachers flagged as *AI-suggested until approved*.

## Files — `/files`

Presigned upload/download URLs via object storage; MIME/extension/size validated;
object keys namespaced by `institution/course/lesson`; access checks on every URL grant.

## Health — `/health`, `/health/ready`

Liveness vs readiness separated; readiness reports each dependency's status.
