# Reliability verification — 19 October 2026

This report distinguishes production observations, isolated staging measurements,
and work still requiring a live rollout. It does not certify overall site security.
The detailed local evidence is retained under `.qa/reliability-20261018/`.

| Requested item | Evidence and current boundary |
| --- | --- |
| Retired signing key rejected | Production verified: a fresh valid session returned200; the same active identity/family with fresh claims signed by the retired key returned401 before identity lookup; the current family remained valid. Logout204. The replacement key was not read. |
| Actual Vercel/Render caller identity | Signed proxy contract and tamper rejection pass locally on both API instances. Production still requires the separate proxy key on both providers and explicit Render mode, followed by the authenticated own-network comparison. |
| Intermittent readiness503 | New production logs identify the19October15:42 failure: `readiness_deadline stage=storage wait_seconds=5.0`; storage completed in5151.5ms, DB7.8ms, Redis9.9ms. This specific503 was the storage round trip exceeding the HTTP deadline, with all three checks subsequently completing. Prepared an8s bounded wait for rollout; this is not a claim that every historical503 has the same cause or that an outage is healthy. |
| API/DB/Redis/SSE latency | Fixed synchronous Redis blocking the ASGI loop and DB checkout starvation across sync auth/endpoint handoff. Controlled Redis-delay event-loop lag fell from199.28ms to13.82ms. Queue wait, pool acquisition, SQL, ORM, Redis and SSE revalidation are now measured separately. |
| 500 SSE connections | Passed on isolated local staging for167.35s:500 distinct active users,500 initial deliveries and500 deliveries after120s stream recycling; no recorded HTTP/network errors;500 active at finish. This does not prove500 browsing students on RenderFree. |
| Shared counters across two instances | Passed against two actual API containers with separate worker/instance fingerprints and common Redis:20 combined requests allowed by the heavy-query guard, then429 on both instances, with one common bucket fingerprint. Not20 per instance. |
| Gradual capacity test | Corrected fixture has3 published courses,30 visible locked paid text lessons,12 events and5,000 notifications. Gradual browsing passed250on both measured profiles;500did not meet acceptance. Production500load was not run. |

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

Gradual arrival6.666667students/second, same two1CPU API containers, native Linux
network, generator sharded across8connection pools (896total slots, below the
old900slot maximum):

| Target students | Result | Requests | Client p95 | Server-header p95 |
| --- | --- | --- | --- | --- |
| 5 | Pass | 25 | 0.043s | 0.035s |
| 10 | Pass | 50 | 0.064s | 0.048s |
| 25 | Pass | 125 | 0.060s | 0.052s |
| 50 | Pass | 264 | 0.097s | 0.064s |
| 100 | Pass | 619 | 0.052s | 0.043s |
| 250 | Pass | 2090 | 0.111s | 0.096s |
| 500 | Safety stop on recent latency | 3276 | 2.862s | 2.812s |

The500stage finished its stop/cleanup after74.86s with424SSE users connected; all3276completed
requests were200. The rolling40request guard exceeded3s even though whole-stage
p95 was lower. It never reached500active browsing users, so this is a failure.
The earlier one-pool gradual run passed250but stopped at500with358SSE users;
client/server timing differences exposed generator transport overhead. Sharding
removed that confounder without removing the remaining server latency failure.

A separate500-only resource diagnostic (explicitly not a gradual capacity pass)
also finished its stop/cleanup after74.86s:2247responses200,337connected users, clientp953.235s
and serverp953.148s. API CPU reached99.12%/99.76% of the one-core limits;
PostgreSQL peaked35.95%, Redis4.66%, and API memory stayed below165MiB.
Slow requests recorded2.5–2.9s in asynchronous DB admission before execution.
CPU saturation is supported by these samples; increasing only a connection
limit would not establish the requested capacity. Detailed CPU samples and all
failed profiles are preserved locally.

`infra/staging/capacity.override.yml` defines a separate optional sizing profile:
two API instances, each2CPU/1024MB and two independent Uvicorn workers. PostgreSQL
and Redis retain the same resources. Docker inspection records the actual CPU,
memory and process arguments. Its measurements must be reported separately and
must never be described as results for RenderFree or the two1CPU baseline.

Full gradual results for that separate four-worker sizing profile:

| Target students | Result | Requests | Client p95 | Server-header p95 |
| --- | --- | --- | --- | --- |
| 5 | Pass | 25 | 0.147s | 0.136s |
| 10 | Pass | 50 | 0.067s | 0.057s |
| 25 | Pass | 125 | 0.082s | 0.063s |
| 50 | Pass | 270 | 0.076s | 0.062s |
| 100 | Pass | 616 | 0.050s | 0.040s |
| 250 | Pass | 2073 | 0.151s | 0.134s |
| 500 | Safety stop on recent latency | 2698 | 1.487s | 0.731s |

The500stage finished stop/cleanup after74.87s with365connected users and all
2698responses200; the recent40request guard exceeded3s. It is not a500pass.
CPU samples reached203.70%/137.09% (container maximum200%; sampling can briefly
exceed the quota), DB77.52%, Redis6.27%. Some client requests took4–5s despite
application header timings64–387ms. Therefore this failed profile also includes
transport/accept/response delay outside the measured application interval; the
whole client/server difference must not be labeled database or Redis time.
Further500acceptance needs profiling across that boundary and a successful full
stage, rather than relaxing stop guards or claiming that adding workers suffices.

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

The new ordinary-session rollout smoke script passed a mocked no-network flow:
both hosts, logout cleanup, four401attempts then429, and artifacts without raw
IP/password. This validates the harness only; it is not production IP acceptance.

No production500-student test or paid resource upgrade is authorized by this
report. Preserve the production tenant SSE limit until the deployment is sized
and measured. The new IP assertion must be provisioned with a fresh independent
key; never reuse or read the replacement session-signing key. Final deployment
status and live readiness/network proof remain separate rollout steps.

Source commit`ed9f32665c0bfd10ce4aec0f62dc959453bd2010` was pushed and Vercel
reported a successful deployment. The Render service's Deploys page also shows
`ed9f326` as Live. Ordinary student login/network-check/logout returned200/200/204
on both hosts. Before provisioning the independent proxy key and Render mode,
both expected-address comparisons were false, including forged-header controls;
the production IP fix is not accepted yet. The replacement session key was not
read during these checks.
