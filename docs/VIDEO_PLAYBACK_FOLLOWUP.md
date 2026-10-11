# Video playback follow-up — 2026-10-10

## Observed live

- Render logs showed repeated progressive 206 responses followed by 429 after
  the video admission pool filled. The player assigned its source both through
  JSX and the transport hook. Progressive cleanup did not abort its resource.
- Teacher playback submitted student-only telemetry and received 403.
- The live Render Free service has no STORAGE_BACKEND/S3 environment variables,
  no secret files and no linked environment groups. The default provider is
  local. Logs showed a missing video before it was uploaded again.
- The user confirmed that originals of all uploaded files are available before
  approving continuation of the deployment.

## Changes

- One transport owns the video source and aborts the old resource on cleanup.
  Sources are immediately hidden when the lesson/account/auth generation changes.
- Video Range responses finish after at most 4 MiB, with accurate Content-Range
  and Content-Length. Chrome requests further ranges as needed. Object storage,
  local storage and legacy local video use the same response logic. Full GET and
  non-video media behavior remains intact. Authorization/admission stay enabled.
- Telemetry attaches only for students, without restarting on ordinary lesson
  object rerenders. Terminal 401/403 disables that tracker; background telemetry
  failures do not become foreground playback error toasts.
- Teachers and administrators can seek freely and have explicit +/-10 second
  controls. Student forward-seek restrictions remain in effect.
- Unknown/infinite WebM duration is not displayed; durationchange updates it
  when the browser discovers the actual duration.

## Verification and limits

- Automated tests exercise authenticated range offsets, suffix ranges, invalid
  ranges and repeated requests across all three storage paths, plus revoked
  sessions and access denial. Player tests cover teacher/admin seeking, student
  restrictions, telemetry isolation, cleanup, account changes and WebM duration.
- A local Chrome preview uses an existing synthetic 35 MB WebM and the actual
  response helper. It played through successive bounded 206 requests.
- Render's local files are ephemeral: redeploy/restart/spin-down can remove
  uploads. This fix does not supply persistent storage or restore missing files.
  Configure supported object storage before relying on uploads in production:
  https://render.com/docs/free#local-files-lost-on-redeploy
