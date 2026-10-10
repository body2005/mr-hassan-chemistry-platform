# Adaptive video quality

The player lists only encoded renditions from the HLS manifest. `تلقائي`
uses hls.js bandwidth adaptation; a manual resolution changes `currentLevel`
and replaces buffered media. Manual preferences survive token renewal. Native
HLS-only browsers use their built-in adaptation. A progressive file exposes its
actual height, not fabricated quality options.

The encoder produces 144p, 240p, 360p, 480p, 720p and 1080p where
the source is tall enough. It never upscales. A 720p source has five renditions;
1080p cannot be recovered from a lower-resolution original. The output ceiling
is 1080p even for a 4K source. Existing progressive files must be converted to
apply this limit to their actual media; hiding a menu option does not transcode.

## Deployment

These changes alone do not convert the videos already stored on Render.
Deploy the API, web and video worker from this same checkout. The video worker
is `python -m scripts.video_worker`, built with `infra/Dockerfile.video`; its
base `API_VIDEO_IMAGE` must be built from the matching API checkout first.
The existing `infra/video-pipeline.override.yml` describes the separate worker
and its bounded CPU, memory and scratch volume. This worker is separate from
the Celery ingestion worker. It requires PostgreSQL and S3-compatible storage.

Keep the same private database/storage settings as the API and give the worker
writable `/work`. Current worker capacity checks reserve the source size plus
26 GiB scratch; its configured memory limit is 2560 MiB. Do not put this encoder
inside the small Render web process. A worker running on the operator's own
machine is an option if its private DB/storage access is configured and it stays
online. No hosted worker or paid service was created as part of this change.
For a Windows operator PC with Docker Desktop, see [VIDEO_WORKER_PC.md](VIDEO_WORKER_PC.md).
The standalone compose file publishes no ports and connects outbound to the
Render database and shared private object storage. The start script runs a
credential-safe connectivity/encoder/scratch preflight before starting it.

After the worker is running, set `VIDEO_PROCESSING_ENABLED=true` on the API.
Leave it false until then, so uploads cannot become stuck waiting for an absent
worker. The standard multipart upload path then queues preparation automatically
and the upload widget waits for `ready` before reporting completion. Direct S3
multipart uploads retain their existing processing queue.

The lesson card shows byte-upload progress instead of **مشاهدة الدرس** while
uploading. When an encoding job exists it stays in a non-clickable processing
state until the worker reports `ready`. The card follows the global upload
manager during navigation; manager-only course metadata restores server job
state after reload and a bounded 15-second poll refreshes pending jobs.
There is no manual quality-preparation button. If processing is disabled the
legacy upload completes as a progressive video with its actual single height;
deploying the UI cannot create encoded renditions without the worker/storage.

For an operator migrating existing progressive videos, the authenticated
manager endpoint remains available:

`POST /api/v1/lessons/{lesson_id}/prepare-video`

The response contains an owner-scoped processing job ID. The existing video
remains playable during preparation. Only a fully uploaded generation replaces
it. Failed preparation preserves the source. Repeated requests for the same
active source reuse its job; a replacement source cannot reuse an older job.

Playback keeps cookie/token, entitlement and per-segment checks. The red banner
inside the video has been removed; errors use the global feedback host and a
small resume button. 429 responses stop automatic renewal and honor Retry-After;
rate limiting remains enabled.

The player has no ±10 buttons. With focus inside the player, Right advances
10 seconds and Left rewinds 10 seconds. Native form/range keys remain intact.
Teachers/admins seek freely; student restrictions on unwatched content still
apply. Keyboard handlers do not run outside the player.

## Validation, 2026-10-10

- Web: 39 files / 248 tests passed; production TypeScript/Vite build and lint
  for changed frontend files passed. Upload-card integration covers byte
  progress, blocked playback while processing, server readiness after reload,
  and restoring the watch action. Keyboard tests cover managers, student
  restrictions, input isolation and duration bounds.
- API: direct-upload/video-protection regression suite passed, including
  automatic preparation after ordinary upload and manager-only latest-job
  metadata without private keys/errors. Four worker-preflight tests passed.
- Built `chemistry-video-worker-pc:local` on the operator PC. Under a 2 CPU /
  2560 MiB container limit, the real encoder converted an 8-second synthetic
  1080p source into 19 HLS files. FFprobe verified segment heights of 144, 240,
  360, 480, 720 and 1080; this was an offline encode, not a live Render upload.
- The PC start script correctly refused to start the persistent worker while
  storage/database settings remained placeholders. Shared object storage is
  still unconfigured; Render quality preparation remains disabled until then.
