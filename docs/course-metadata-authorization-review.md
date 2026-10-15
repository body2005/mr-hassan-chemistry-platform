# Course and assessment metadata authorization — 13 October 2026

Source-only follow-up on `fix/queen-p0-handoff`, starting at
`d3785d0595d456a8142335a2360287e14451e3de`. No tests, builds, scanners, production
requests, deployment, database writes, or session changes were performed.
Previously pending video/DRM/UI changes remain in the working tree.

## What the reports establish, and what source inspection adds

The submitted report describes authenticated unenrolled students receiving
assessment metadata and anonymous clients receiving course details. Its request
times/deployed SHA are unknown. Do not label it a demonstrated payment bypass,
content theft, or successful unauthorized attempt/submission/video stream.

- The starting assessment endpoint lacked an early enrollment rejection and
  serialized available lesson titles/IDs with `accessible: false`. Its
  `next_availability_at` also included boundaries of inaccessible lessons and
  assessment scopes. These are concrete disclosure paths in the source.
- The starting code **already** applied `filter_student_assessments`, which
  excludes quiz/assignment rows for unenrolled students. The supplied response
  containing those full rows cannot be attributed to this starting source
  without a deployment/request trace. This change adds defense at admission,
  rather than assuming that filter was missing.
- Anonymous course list/detail reads are intentional sales-catalog behavior.
  `_course_query_for_user` already excludes unpublished courses for guests and
  students; `_safe_course_responses` already removed paid content, playback URLs,
  and material downloads for users without access. Returning HTTP200 for a
  published sales item is not by itself missing authorization.
- The old course response nonetheless retained lesson structure, duration,
  scheduling/processing metadata and teacher/institution IDs. The user explicitly
  chose a **brief public course-and-price catalog without lesson details**.

## New source behavior

The user's final clarification is **individual lesson purchase**, not mandatory
whole-course checkout. Both requested endpoints now use the same purchase gate.

1. `/courses/{id}` and `/courses/{id}/assessments`, with or without a trailing
   slash, require `CurrentUser`: anonymous/invalid sessions receive401 directly.
   Students require active/completed enrollment **and** an active server-side
   LESSON entitlement belonging to this course (or an existing whole-course
   entitlement). Free enrollment, a zero price, pending payment, another
   student's purchase or another course's purchase is not enough; denial is403.
   Expired, future or revoked entitlements do not count. Tenant/draft/teacher
   ownership mismatches remain404. The owning teacher and authorized admins
   retain management access.
2. A partial buyer's course detail contains only purchased, currently released
   lessons and their associated modules. Assessments use the intersection of
   purchased lesson IDs and `accessible_course_lesson_ids`. A unit/multi-lesson
   assessment is hidden unless every required lesson belongs to that scope.
   An unscoped whole-course assessment is not disclosed merely because one
   lesson was purchased. Existing whole-course entitlements retain full scope.
   Existing quiz/assignment filtering still applies, including lesson payment,
   publication/readiness, and opening-time policy. Closed assessments remain
   visible when their underlying scope is authorized; `accessible` can be false
   because the action window closed, not because the course is unauthorized.
3. The refresh deadline excludes locked lessons and assessment scopes. Authorized
   future assessments can retain a future refresh boundary. An aggregate
   timestamp is not allowed to bypass the underlying metadata access check.
4. Anonymous `/courses` and `public_only=true` use an explicit
   `PublicCourseResponse` allowlist: course ID/code/title/description/publication
   status/price/grade. No modules, lessons, teacher/institution IDs, timestamps,
   video URLs, processing metadata or material paths are included. Invalid
   optional catalog cookies may receive the same public **list** summary; that
   does not authorize either protected course-detail/assessment endpoint.
5. Signed-in catalog entries retain released lesson IDs/titles/prices for the
   existing per-lesson purchase flow. Locked entries lose content, media state,
   duration, schedule, notification state and processing diagnostics. Worker
   error text is manager-only even for entitled students. This is intentional
   product discovery, distinct from assessment/content authorization.
6. Course list/detail and assessment success responses set
   `Cache-Control: private, no-store` and `Vary: Cookie, Authorization`.
   This hardens identity-dependent responses; no CDN/cache incident was proved.
7. The landing page now renders course sales cards from the brief response,
   without requiring lesson data or displaying private lesson titles/durations.
   The API client accepts summaries without modules or manager timestamps.
8. A denied assessment read clears the previous result and displays a purchase
   requirement instead of a retryable network error or a fake progress total.
   Enrollment without a purchase directs the student to lesson checkout.

## Independent action-route audit (source inspection only)

| Entry point | Existing independent server gate |
| --- | --- |
| `POST /quizzes/{id}/attempts`, `GET /quizzes/{id}/solve` | `platform_service.start_quiz` / route call `require_assessment_access(..., writing=True)` before issuing a new attempt or questions |
| `POST /quiz-attempts/{id}/submit` | Attempt ownership + institution match, then `require_assessment_access(..., writing=True)` before accepting answers |
| Assignment attempts, JSON/file submissions | `require_assessment_access(..., writing=True)` before creating attempts, accepting answers or writing uploaded objects |
| Assignment solve/PDF | `require_assessment_access` before content serialization |
| `POST /lessons/{id}/video-token` | `_require_lesson_access` -> `can_access_lesson_content`, plus live cookie/family/nonce checks before stream admission |
| Progressive/HLS resources and material downloads | Stream authorization rechecks access/session; material download/preview checks lesson access independently |

`require_assessment_access` rejects an unenrolled student, checks the published
course/tenant and linked lesson access, and enforces relevant opening/closing
windows. Existing **unscoped** assessments retain the documented enrollment-only
policy; this review does not silently introduce a new course-payment policy.
No source path demonstrating an unenrolled action bypass was found in the
reviewed entries. This is not a live exploit reproduction or a claim that all
possible authorization defects have been excluded.

## Files and validation status

- `apps/api/app/services/course_purchase_access.py`: shared server-side purchase
  admission returning the permitted lesson scope; no browser access flag is trusted.
- `apps/api/app/api/routes/platform.py`: assessment admission, lesson projection,
  refresh-boundary filtering, cache headers.
- `apps/api/app/api/routes/courses.py`: public projection, locked metadata
  redaction, response types and cache headers.
- `apps/api/app/schemas.py`: explicit public course DTO.
- `apps/web/src/services/lmsService.ts`: consume course summaries safely.
- `apps/web/src/views/LandingPageView.tsx`: public course cards.
- `apps/api/tests/test_course_metadata_authorization.py`: regression source for
  public/detail/list/owner-public-only, two unenrolled accounts, active/completed
  partial access, tenant/draft/teacher isolation, no unauthorized action writes.
- `apps/web/src/views/LandingCatalog.test.tsx`: adapt existing source expectations
  and cover a course summary with no lessons.
- Existing public-catalog/payment/direct-upload test sources now expect the new
  public summary contract instead of traversing anonymous lesson arrays.
- `apps/api/tests/test_course_purchase_scope.py`: identity/slash variants,
  inactive/unrelated purchases, one-lesson isolation, aggregate deadline
  redaction, legacy full-course rights, and delete/restore of an unpurchased
  account's own cookie. Source only, not executed.
- Existing assessment completion/scope/query-count fixtures now provide an
  explicit entitlement where they expect a successful purchased read.
- `useCourseAssessments`, `MyCoursesView`, `FloatingProgressFab`, and the
  enrollment handler in `App.tsx` distinguish purchase denial from load failure.

These test files were **not executed**. Manual source review covered call paths,
serialized fields and frontend consumers. Practical status-code/content checks
and production verification remain unperformed. No severity increase beyond
metadata disclosure is justified by this work alone.

The user separately reported that a friend actually played/downloaded content
using that friend's own supposedly unsubscribed account. The exact successful
request, lesson and enrollment/payment state are still awaited. This metadata
purchase gate is **not evidence that that separate playback path has been
identified or fixed**. No production fix or practical cookie-bypass test is
claimed here.
