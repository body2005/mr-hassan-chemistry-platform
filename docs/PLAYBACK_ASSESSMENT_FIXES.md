# Playback and assessment follow-up (2026-10-10)

These changes are local until the API and web are deployed together. Run
`alembic upgrade head` before starting the updated API. The new migration
`f6b8d0e2a4c6` adds lesson/unit association tables and backfills existing links.

## Assessments

- The three editor stage controls and course dropdown are removed.
- Multiple lessons and whole units can be selected in one assessment. They
  must belong to the same server course. The UI resolves that course from the
  selected content, without asking the teacher to choose a course dropdown.
- Quiz and assignment APIs persist all selected IDs, validate ownership and
  course membership, and expose the lists in assessment responses.
- Legacy lesson-plus-parent-unit records retain their lesson-only access scope;
  explicitly selected whole units use the new association tables.
- Students need enrollment and access to every selected lesson, including
  lessons in selected whole units. Selecting a free lesson does not bypass a
  paid lesson in the same assessment.
- Opening and submitting remain gated by server time. Future activities can
  appear as scheduled but cannot be solved before their start. The student's
  attempt expires at the earlier of its duration or the quiz closing time.
- Local teacher times are already normalized to UTC by `assessmentWindow`.
  No cron job is needed to enforce the opening/closing window.

## Playback and 429

- Long-lived video and SSE responses have separate finite admission budgets;
  they no longer occupy ordinary login/assessment request slots.
- SSE subscriptions release their leases even when the connection fails before
  streaming headers. Video responses release DB connections after authorization.
- Realtime probes and telemetry respect Retry-After; telemetry flushes are
  serialized and bounded. Existing playback admission stops automatic replay
  after denial. Rate limiting and session/payment checks remain enabled.
- New encodes stop at 1080p. Old HLS manifests omit larger variants and larger
  rendition paths are denied. Existing progressive sources need conversion;
  changing the menu alone cannot reduce the actual file resolution.

## Login and fields

- Names accept letters, combining marks and spaces; registration rejects
  digits and punctuation server-side. Phone inputs retain digits only, including
  normalized Arabic/Persian digits; the API rejects punctuation and letters.
- Password characters, including leading/trailing spaces, are preserved when
  logging in. A 401 is translated to an Arabic invalid-credentials message.
- Three preview students are an explicit deployment opt-in. See
  `PREVIEW_STUDENTS.md`. No live account was created or password reset during
  this change. A local test account/password is not proof of a Render account.

## Download protection limitation

The current session-bound HLS/progressive delivery is not licensed DRM. A
viewer entitled to receive clear media can still capture it using a browser
extension/download manager. `nodownload`, disabled context menus, signed
tokens and HLS segmentation do not guarantee prevention.

Licensed DRM requires a real packaging/license provider and client playback
integration. No such provider was configured here. Do not enable
`VIDEO_DRM_REQUIRED` until it is integrated: the existing guard intentionally
returns 503 instead of silently serving clear video. See Google's overview:
https://developers.google.com/widevine/drm/overview

## Local verification

- Web: `npm run test` passed 37 files / 232 tests. After the final mobile menu
  alignment change, the 18 player/transport tests passed again.
- API: 67 targeted tests passed across assessment scope/window, migration,
  stream admission/leases, upload, video authorization, realtime, registration
  and preview seeding. This is not a claim that the entire backend suite ran.
- `npm run build` passed after the final UI changes. The bundler still reports
  large chunks; this does not prevent the build.
- Browser playback used a synthetic 12-second HLS video. Selecting 144p and
  720p changed the actual video element dimensions to those heights. The mobile
  quality menu was checked within a 455px viewport and its clipping was fixed.
- The quiz editor was reviewed with two lessons and two units selected,
  without the old stage buttons or course dropdown.
- The live Render database/accounts, deployment settings, production video
  conversion and DRM were not verified or changed in this run.
