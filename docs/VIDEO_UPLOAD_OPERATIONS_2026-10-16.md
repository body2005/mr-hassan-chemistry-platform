# Video processing recovery and request limits

The production API runs on Render. FFmpeg processing and output uploads run in
the private local Docker worker. Closing Docker or sleeping/shutting down this
PC stops that worker; the Render API cannot finish the job by itself.

During this incident the job's stored progress stopped at processing 88 (overall
91 with the previous mapping), in the output upload stage, for over three hours.
Docker was not running when inspected. Docker was started and the existing job
was recovered using its already stored private source. Current recovery starts
a fresh output generation; it can repeat encoding, rather than resume a partial
FFmpeg run. This is not another browser upload of the source file.

The worker's CPU quota was increased live from 2 to 4 without restarting its
container or interrupting recovery. Docker reports 12 CPUs and about 8 GiB RAM
available. Its 2560 MiB memory limit and output/storage bounds remain unchanged.
The compose CPU budget is also 4 for future recreation; no image rebuild or
container replacement is needed to apply the live CPU quota.

New progress allocation follows measured work: original transfer 0–10, worker
source download 10–15, encoded timeline 15–75, durable output upload 75–99.
Only authoritative readiness reaches 100. This is weighted completed work, not
a constant-speed animation or ETA. An existing task's high-water mark remains
until its recovered work catches up; it is never moved backward. Long videos
and variable network speed still make phases take different amounts of time.

Requested API defaults per 60-second window:

| Category | Limit |
| --- | ---: |
| Login | 10 |
| Read | 300 |
| Upload | 20 |
| Assessment extraction | 10 |
| PDF render | 30 |
| Heavy query | 20 |
| General API | 300 |

The separate video-stream budget is unchanged. Tightening HTTP request limits
does not speed up FFmpeg or limit the worker's private R2 upload throughput.

Keep the PC, Docker, and its internet connection running until the video is
ready. No paid Render upgrade or DRM service was purchased. No before/after
encoding speedup is claimed without a comparable measurement.

Validation: 39 focused frontend tests, 29 API rate-limiter tests, production
TypeScript/Vite build and targeted ESLint passed. Render had no `RATE_LIMIT_*`
environment overrides when checked, so the API deployment uses these defaults.

## Separate finalization failure in a new upload

The subsequent upload was a different job, started with Docker and connectivity
available. Its first attempt failed near finalization and the next attempt
repeated encoding while the stored high-water progress remained near 97%.
The old logs retained only a generic infrastructure error; they do not prove
the exception type of that original attempt.

A controlled private copy of the same approximately 405 MB source reproduced
a `ReadTimeoutError` in about 62 seconds. The probe destination was cleaned up.
The worker previously performed this full CopyObject after uploading every HLS
output; failure then discarded that generation and retried the whole pipeline.

The worker now retains the already durable, SHA-256-verified private source in
place and verifies its size before the atomic ready transaction. It no longer
copies or deletes that source at finalization. Cleanup of superseded renditions
preserves a shared original, including legacy s3:// pointers. Failed output
cleanup never includes the retained retry source. Error logging records phase,
exception class and a bounded provider code without SDK URLs or SQL parameters.
Playback authorization, scheduling, rendition selection and readiness gates
are unchanged. The bucket remains private; its lifecycle UI showed only the
default rule aborting unfinished multipart uploads after seven days, with no
completed-object expiration rule.

Validation: 36 focused API tests passed, the finalization test file passed Ruff,
and the replacement worker image built successfully. The idle worker was
recreated with the fix and reports healthy, with four CPUs and 2560 MiB RAM.
The user deleted the affected lesson and requested the worker fix only; no
lesson was restored or republished. A new long-video end-to-end success has
not been verified, and no measured speedup or constant processing rate is claimed.

## Long names and upload history controls

The teacher's rejected lesson title contained 220 Unicode characters; the API
and database previously allowed only 200. Lesson titles and original video
filenames now allow 1000 characters without silently truncating the text.
The additive migration also widens titles in scheduled events and notifications
that carry lesson names. A downgrade refuses to shorten columns containing long
values. Client validation uses Unicode character counts and keeps the entered
text when it reports the limit.

The preview's cancel action no longer shrinks or wraps vertically beside a long
filename. Upload history reserves space for retry and dismiss controls, wraps
the full title, and offers clearing completed/failed history even if no upload
completed. Clearing history does not delete lessons or stored videos.

An owner-scoped 404 marks a saved upload unavailable and stops automatic polling
of that ID, including after reload. Explicit retry remains available; temporary
errors and other accounts' tasks keep the existing ownership/resume behavior.
Deleted or inaccessible jobs still correctly return 404 on the server.

Validation: 26 focused frontend tests, production web build, targeted ESLint and
the PostgreSQL migration probe passed. The migration probe used a private QA
schema and rolled back its entire transaction, including the schema and data.

## AV1 compatibility and schedule/card consistency

A separate 3,115,020-byte, 59.07-second portrait MP4 failed immediately at
`encoding:shared` with `VIDEO_DECODE_FAILED`. Reproducing the supplied local file
under the same limits showed AV1 input; the restricted FFmpeg build had no
software AV1 decoder and its native decoder required unavailable acceleration.
The worker now includes Debian's libdav1d development/runtime packages, enables
that decoder explicitly in the signed FFmpeg build, and selects it for AV1 input
after probing the codec. Decoder threads still follow the existing CPU budget;
there is one input decode and the existing shared four-output graph.

The complete supplied file encoded successfully in a network-disabled candidate
container with the production limits (4 CPUs, 2560 MiB, 128 PIDs). It produced
360p/480p/720p/1080p HLS; every rendition decoded completely and contained audio.
This verifies local processing of this file, not a new production upload or
long-video speed benchmark. Deleted lessons were not recreated.

Teacher lesson cards now have a consistent 500px height across upload states;
the responsive grid keeps equal widths per row. Long titles/descriptions remain
available through a scrolling text area, while the progress/actions stay fixed.
Newly selected past scheduling minutes are rejected in lesson, assessment,
calendar and notification writes. Existing unchanged historical timestamps and
idempotent retry responses remain valid. The current minute is allowed to match
minute-resolution Cairo form inputs. Browser minimum dates/times and submission
validation complement authoritative server checks; processing completion never
retroactively rejects a valid lesson schedule that elapsed while encoding.

Validation: 63 focused API tests, 31 frontend tests, targeted ESLint, frontend
production build, worker image build and the real-file AV1 check passed.

## Three-step lesson upload (2026-10-17)

The teacher form now groups file selection, optional materials, unit selection
and revision classification in step one; title, description and price in step
two; and availability scheduling in step three. Back/Next navigation retains
the selected File objects and entered values. Leaving the preview pauses it.
Only final confirmation creates the lesson and enqueues file transfers; a
pending submission guard prevents duplicate confirmation/submission. Invalid
fields block their step, and server errors keep the final form for correction.

Lesson cards form one vertical column, retaining newest-upload-first sorting.
The title-length counter, numbered lesson badge and canned description were
removed. A teacher-authored description is still shown. The form's success
banner describes saved details and points to upload progress rather than
claiming that queued media is already complete.

Validation: the wizard regression covers empty selection, video plus PDF,
revision selection, details retained after Back/Next, final scheduling, delayed
confirmation, and duplicate-click prevention. Focused tests, targeted ESLint
and the production web build passed. This change requires no database migration
or worker replacement.

## Clickable steps and compact cards (2026-10-17)

Step headings are now buttons. Returning to an earlier step retains the form;
forward jumps validate the preceding required data and focus the invalid step.
The private-storage explanatory sentence was removed from the upload form.
Superseding the earlier fixed 500px card layout, cards now grow with their
content with a 340px minimum, avoiding the large blank space below short titles.

The current upload stalled at 10% because the file transfer had completed but
the processing job was queued: Docker was stopped and the last worker heartbeat
was from the previous day. Starting the already configured Docker worker resumed
that same job without another upload. The job advanced into shared encoding
with no recorded error; no artificial progress increment was introduced.

Validation: seven focused frontend tests, targeted ESLint and the production
web build passed. No worker replacement or database migration is needed.
