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
