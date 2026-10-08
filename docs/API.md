# API Reference — `/api/v1`

Metadata responses are JSON; file/video downloads return binary content and
`/realtime/stream` returns SSE. Mutations require the CSRF header (`X-CSRF-Token`,
value of the `matgar_csrf` cookie) for cookie sessions except login/register
and password-reset/request/confirm. Independent Bearer calls do not use CSRF
on endpoints that support Bearer; refresh/logout require cookies. Errors use:

```json
{ "error": { "code": "QUIZ_EXPIRED", "message": "This quiz attempt has expired." }, "request_id": "..." }
```

## Conventions

- **Pagination**: `?page=1&page_size=25&search=&sort=-created_at&<filters>` →
  `PageResponse[T] { items, total, page, page_size, pages }`
- **Idempotency**: use the endpoint's documented JSON `idempotency_key` or
  upload `request_key` where supported. Do not assume an arbitrary
  `Idempotency-Key` HTTP header makes every POST retry-safe.
- **Auth**: session cookie set by `/auth/login` or `/auth/register`.

## Auth — `/auth`

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | /auth/register | public | student only; institution must already exist |
| POST | /auth/login | public | rate-limited; sets HttpOnly session cookie |
| POST | /auth/logout | any | revokes session server-side |
| GET | /auth/me | any | current user from session |
| POST | /auth/refresh | with refresh cookie + CSRF | rotate server-side family; no credentials in JSON |
| POST | /auth/change-password | any | rehash Argon2id, revoke all sessions/reset links |
| POST | /auth/password-reset/request | public | generic200 if configured,503 globally unavailable,429 rate limit; uniform padded encrypted identity queue, no HTTP account lookup; delivery asynchronous |
| POST | /auth/password-reset/confirm | public | consumes single-use token |

Login/register/refresh JSON contains user and expiry, **no token or refresh
credential**. Non-browser clients retain Set-Cookie in a private jar and copy
matgar_csrf into X-CSRF-Token for cookie mutations. Example:

```sh
# Use a private temporary jar; never commit it or log its content.
curl -c cookies.txt -H 'Content-Type: application/json' --data @login.json https://HOST/api/v1/auth/login
# Read CSRF from your cookie-jar library; use the same jar for refresh/logout.
curl -b cookies.txt -c cookies.txt -X POST -H "X-CSRF-Token: $CSRF" https://HOST/api/v1/auth/refresh
```

Refresh cookie path is /api/v1/auth. General auth does not accept ?token=.
Short-lived video/preview tokens cannot authenticate auth/admin APIs.
GET /bootstrap is200 as guest only without session evidence,401 with invalid
credentials and503 on unavailable identity storage. Clients distinguish
temporary503/network failure from invalid401; preserve drafts, retry explicitly,
never loop on429. Browser requests use HttpOnly cookies, not JS Bearer.

GET /ready returns only status and200/503. /ready/details and /metrics require
platform-admin authentication. Probes share a5s cache, one in-flight check
per API process and a2s HTTP waiting budget.

Registration has TWO steps: personal → contact/password/create, no third
review step or SMS/OTP. Phone numbers are contact data, not verified identities.
mother_phone/city/education_division/specialization remain nullable for legacy
clients. Password minimum remains10; public signup never creates staff.
New/published MCQs support2–26 options (text A–Z); option27 yields422 on creation
or400 on legacy publish, not500. Historical snapshots are not renumbered.
Objective codes are unique per institution/course (separate NULL-global index).
Legacy evidence uses the quiz-course override before a global fallback.

Credential mutations, including refresh, share the unchanged default auth
budget15/60s; stricter route policies also apply (reset5/300s). The existing
refresh route60/min guard does not replace the middleware15/min ceiling.
Profile GET/HEAD and the closed legacy avatar GET/HEAD use read budgets. Deployment Redis failure is503;
429 includes Retry-After. Never clear live counters to make QA pass.

Personal account photos are not supported for any role (product decision,
7October2026). Auth responses omit `avatar_url`; authenticated legacy
`GET /auth/avatar` and CSRF-protected `POST /auth/avatar` return410. They do not
read/decode/upload an image or delete existing stored objects. The UI uses
initials, never cached personal-photo URLs. Profile account changes require the
matching server bootstrap rather than cached identity alone.

Upload/concurrency admission uses renewable distributed reservations. Losing
the reservation before headers returns503 with Retry-After2 and
`{"detail":"Admission service temporarily unavailable"}`; it never silently
continues unreserved work. If a stream has already started it is closed, not
rewritten to a second status or a successful final chunk. Client cancellation
is not classified as a reservation failure. Clients retain the draft/file and
offer explicit retry after recovery rather than endlessly resubmitting.

## Managed users

| Method | Path | Roles |
|---|---|---|
| GET | /users | manager; teacher sees self and eligible students in owned courses |
| POST | /users/{id}/block | manager, subject to ownership/role policy and audit |
| DELETE | /users/{id} | manager, subject to ownership/role policy |

Listing is a JSON array, not a generic pagination contract for every endpoint.

## Curriculum — `/courses`

- `GET /courses` — paginated; students see published only, staff see all in tenant.
- `POST /courses` (teacher+) · `GET /courses/{id}` · `POST /courses/{id}/publish`
- `POST /courses/{course_id}/modules` · `POST /modules/{module_id}/lessons`
- `POST /modules/{module_id}/chapters` (extended metadata)
- `POST /lessons/{lesson_id}/assets` — metadata for stored objects
- `POST /courses/{id}/enroll` (student; duplicate-safe) · `GET /courses/me/enrollments`

## Progress & Telemetry

- `GET /progress/me`, `GET /progress/lessons/{lesson_id}`, `POST /progress/lessons/{id}/complete`
- `POST /telemetry/video-events` — student video events, deduplicated by
  client_event_id and checked against actual lesson enrollment.

## Questions — `/questions`

GET/POST question endpoints and explicit `/questions/versioned`,
`/questions/{id}/versions` endpoints. Historical attempts retain frozen
snapshots/versions. Do not infer generic CRUD or a `/question-banks` API.

## Quizzes — `/quizzes`, `/quiz-attempts`

- `POST /quizzes/publish-draft` — atomic reviewed draft publication.
- `POST /quizzes` and `POST /quizzes/{id}/publish` — legacy path, which also
  checks nonempty valid questions before publishing.
- `POST /quizzes/{quiz_id}/attempts` — rejects if attempt limit reached or an
  active attempt exists; returns server-computed `expires_at`.
- `POST /quiz-attempts/{id}/submit` — idempotent; objective items auto-graded;
  essays await authorized teacher grading. Expired attempts rejected.
- `POST /quiz-attempts/{id}/answers/{question_id}/grade` — teacher grading,
  preserving grade history and course/student scope.

## Assignments — `/assignments`, `/submissions`

- Teacher creation and `POST /assignments/{id}/publish` with validated
  dates/content; student attempt and submission endpoints enforce start time.
- Student submit/resubmit — each submission creates immutable `SubmissionVersion`.
- `POST /submissions/{id}/grade` — authorized teacher final grade.

## Grading — `/grades`

Final grade ledger per (student, course item); history retained on change.

## Notifications — `/notifications`

- `GET /notifications` (own), `POST /notifications/{id}/read`
- `POST /notifications` / `POST /notifications/broadcast` (teacher+/admin)
- Notification scheduling is server-side; browser rendering is not proof of
  actual scheduled delivery. See the live QA ledger for tested boundaries.

## Calendar — `/calendar`

List/create/update/cancel events. Stored UTC, recurrence via `rrule` string,
rendered in Africa/Cairo by clients.

## Certificates — `/certificates`

- `POST /certificates/courses/{course_id}` requests eligible student issuance.
  `GET /certificates/verify/{token}` is public and rejects invalid/revoked tokens.

## Analytics & Risk — `/analytics`

- `GET /analytics/courses/{course_id}` — aggregated server-side.
- `GET /analytics/students/{id}/mastery` — per learning objective.
- `/reports/summary` denies students and scopes teacher aggregates to owned
  courses/eligible students; institution admins remain tenant-scoped.

## Reports — `/reports`

`POST /reports/jobs` → job id → `GET /reports/jobs/{id}`, ownership-scoped.
Use the JSON idempotency_key field; do not infer ready artifacts from job creation.

## Removed functionality

AI/Knowledge Center/RAG/Whisper/gTTS routes were intentionally removed.
`/ai/jobs` is NOT part of the current mounted router. Nothing in this review
reinstates them. Extract is local document processing with teacher review,
not an external AI completion or automatic source-fidelity guarantee.

## Files and protected video

Materials use `POST /lessons/{id}/materials` and authorized
`GET /lessons/{id}/materials/{asset_id}/download`; receipts use
`/payments/orders/{id}/receipt`. There is no generic mounted `/files` API.
Video capability/session/part/complete endpoints use `/video-upload-capabilities`,
`/lessons/{id}/video-uploads`, `/video-uploads/{id}/parts/{number}` and
`/video-uploads/{id}/complete`. Direct multipart upload is resumable; it is not
claimed to implement tus POST/PATCH/HEAD. See VIDEO_PIPELINE.md for the contract.
Playback uses lesson-scoped tokens and authorized HLS/resource checks, not a
public object URL. Local protection is not external DRM or absolute prevention
of saving/recording authorized playback.

## Health — `/health`, `/ready`

Public liveness/readiness reveal only overall status; authenticated
platform-admin `/ready/details` exposes dependency details. Local HTTPS uses a
self-signed QA CA; no external TLS/provider deployment is certified here.
