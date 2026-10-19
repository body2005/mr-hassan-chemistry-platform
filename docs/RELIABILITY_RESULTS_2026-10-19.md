# Reliability verification — 19 October 2026

This report distinguishes production observations, isolated staging measurements,
and work still requiring a live rollout. It does not certify overall site security.
The detailed local evidence is retained under `.qa/reliability-20261018/`.

| Requested item | Evidence and current boundary |
| --- | --- |
| Retired signing key rejected | Production verified: a fresh valid session returned200; the same active identity/family with fresh claims signed by the retired key returned401 before identity lookup; the current family remained valid. Logout204. The replacement key was not read. |
| Actual Vercel/Render caller identity | Signed proxy contract and tamper rejection pass locally on both API instances. Production still requires the separate proxy key on both providers and explicit Render mode, followed by the authenticated own-network comparison. |
| Intermittent readiness503 | Added dependency-stage timings and a finite5s wait. Healthy storage measured1.210–1.973s before DB/Redis; an isolated2.1s healthy probe reproduced old503/new200. This is evidence of a deadline problem, not proof of the dependency causing every historical production503. Live logs after rollout are still required. |
| API/DB/Redis/SSE latency | Fixed synchronous Redis blocking the ASGI loop and DB checkout starvation across sync auth/endpoint handoff. Controlled Redis-delay event-loop lag fell from199.28ms to13.82ms. Queue wait, pool acquisition, SQL, ORM, Redis and SSE revalidation are now measured separately. |
| 500 SSE connections | Passed on isolated local staging for167.35s:500 distinct active users,500 initial deliveries and500 deliveries after120s stream recycling; no recorded HTTP/network errors;500 active at finish. This does not prove500 browsing students on RenderFree. |
| Shared counters across two instances | Passed against two actual API containers with separate worker/instance fingerprints and common Redis:20 combined requests allowed by the heavy-query guard, then429 on both instances, with one common bucket fingerprint. Not20 per instance. |
| Gradual capacity test | Corrected fixture has3 published courses,30 visible locked paid text lessons,12 events and5,000 notifications. Fast-arrival browsing results below; production500load was not run. |

## Capacity workload and resources

Two API containers, each1CPU/768MB; PostgreSQL1CPU/512MB; Redis0.5CPU/192MB;
a private object-store emulator and separate load generator. These resources
are different from a single RenderFree0.1CPU instance.

Each distinct student bootstraps, opens one SSE stream, and reads courses and
calendar approximately every10seconds. The load fixture checks that paid lesson
bodies remain unavailable. Stop rules retain recent40-request p95>3s, unexpected
HTTP/network failures, or a control request exceeding5s.

Fast arrival:33.33students/second, native Linux staging network:

| Target students | Result | Completed requests | HTTP statuses | Client p95 | Server-header p95 |
| --- | --- | --- | --- | --- | --- |
| 5 | Pass | 25 | All200 | 0.187s | 0.134s |
| 10 | Pass | 50 | All200 | 0.082s | 0.072s |
| 25 | Pass | 125 | All200 | 0.737s | 0.702s |
| 50 | Pass | 250 | All200 | 0.926s | 0.884s |
| 100 | Pass | 500 | All200 | 1.237s | 1.216s |
| 250 | Safety stop on latency | 418 | All200 | 3.977s | 3.814s |
| 500 | Not run in this profile | — | — | — | — |

This is not a measured hard capacity limit of100 or250. The250 stage stopped
before all students connected. A slower-arrival profile, if run, is a separate
measurement and does not erase this failure.

## Failed measurements preserved

Earlier DB-starvation runs timed out at250; the SSE DB-close fix alone was
insufficient. Asynchronous request admission addressed the shared-thread
handoff mechanism, with regression tests for constrained pools and cleanup.
Earlier fixtures accidentally hid video lessons lacking media; their browsing
numbers are not used in the corrected-fixture table above.

The first500-SSE run failed during recycling. A later host-side measurement
showed a15.274s control request despite352ms server header time and an11ms
independent control. One diagnostic API process also exited139 without OOM.
These failures are retained rather than relabeled as passes. The completed
167.35s result used the native Linux network, an HTTP client idle lifetime shorter
than the server keepalive timeout, and fatal-error capture without periodic
all-thread dumps. Both API processes stayed alive. This does not establish one
unique root cause for every earlier transport/native failure.

## Validation and rollout boundary

The reliability group passed78 tests with one Windows symlink skip; that test
passed separately on Linux. The access/purchase/tenant group passed78 tests;
some cases overlap the reliability group. The new network-check and health
group passed5 tests on Windows and Linux. Web middleware tests passed2/2;
the web production build passed with its existing large-chunk warning.

No production500-student test or paid resource upgrade is authorized by this
report. Preserve the production tenant SSE limit until the deployment is sized
and measured. The new IP assertion must be provisioned with a fresh independent
key; never reuse or read the replacement session-signing key. Final deployment
status and live readiness/network proof remain separate rollout steps.
