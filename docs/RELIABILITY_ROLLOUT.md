# Client identity, readiness and realtime capacity

## Signing-key rotation

`SECRET_KEY` belongs to the API. It signs access/preview/video credentials and
derives the encrypted password-reset outbox keys. The actual Render project
currently has one API service, PostgreSQL and Redis. The optional Celery worker
in `render.yaml` references the API key, but is not a currently deployed service.
The local video worker loads the application settings; it must not receive the
session-signing key merely to satisfy settings validation.

Before a future rotation, drain or discard expired reset outbox entries under
the operator's policy. Rotation invalidates old JWT signatures, but does not
revoke opaque refresh credentials stored in PostgreSQL. Revoke those families
separately if the incident includes refresh-token compromise. A new signing key
must never be copied into Vercel or a `VITE_*` environment variable.

The existing production Vercel project also lists a variable named `SECRET_KEY`
and several backend variables. Their values were not read. The reviewed web
source consumes only `VITE_API_URL` and the new proxy-only assertion key; the
presence of an environment name does not prove that a service signs sessions.
Do not pull the whole Vercel environment to perform deployment checks.

The 18 October rotation was verified using a fresh valid session as control:
the same identity and active family, with fresh timestamps but a retired-key
signature, was rejected401 before identity lookup. The fresh session remained
valid. No replacement signing-key read was required.

## Authenticated proxy identity

The API no longer needs to infer the browser from an arbitrary-length external
`X-Forwarded-For` chain. `apps/web/middleware.js` executes only in Vercel's server
runtime and replaces any supplied `X-Chemistry-Client-*` headers. It signs:

```
client-ip-v1\n<unix seconds>\n<METHOD>\n<encoded path and query>\n<client IP>
```

The API validates the HMAC, address, method, target and a maximum60second age
(at most5seconds of forward clock skew). The secret is **separate** from the
session key: `PROXY_ASSERTION_SECRET`, at least32random characters, configured
identically in Vercel server environment and Render API. No client bundle reads
this variable. The assertion identifies a rate-limit subject; it does not grant
authentication or content access.

Rollout order:

1. Deploy the API validator and middleware with the assertion key absent. This
   preserves existing proxy behavior while stripping supplied assertion headers.
2. The operator generates the proxy-only key and enters it directly into both
   providers' secret settings, without sending it through chat. Redeploy both.
3. Set `CLIENT_IP_MODE=render` on the Render native API to enable its documented
   Cloudflare header contract. This branch requires `RENDER=true` and an actual
   loopback socket peer. It never trusts arbitrary private networks or claimed
   Vercel headers. A valid signed Vercel assertion takes priority.
4. Compare expected caller-IP fingerprints through Vercel and direct Render,
   then repeat forged XFF/CF/Vercel/assertion controls and the short login guard.
   Do not call the production identity fix verified until these live checks pass.

`GET /api/v1/operations/client-network` permits an ordinarily authenticated user
to verify their own path without reading any signing key. Supply the independently
known caller address as `X-Expected-Client-IP`. The response contains only three
booleans: `expected_match`, `signed_proxy_assertion`, `render_edge_contract`.
The expectation never supplies an identity and raw addresses are never returned.
Use a normal session, repeat forged forwarding/assertion headers, then log out.
The successful Vercel path must have `expected_match=true` and
`signed_proxy_assertion=true`; direct Render must match through its edge contract.

After both deployments, run the bounded smoke with an ordinary authorized
student; the password is prompted without echo (or supplied only to the process
as`LIVE_STUDENT_PASSWORD`). It never reads a server key or saves raw IP/cookies:

```powershell
apps/api/.venv/Scripts/python.exe scripts/qa/reliability/live_network.py --email student03@demo.com --output .qa/reliability-live/network.json --login-guard
```

The optional guard sends five failed login attempts to a new nonexistent reserved
identity through Vercel only, after network and normal smoke checks pass. Acceptance
requires four401responses followed by429with a positive Retry-After within10s.
It does not create an account, change real student credentials, or bypass limits.

Primary contracts: [Vercel request headers](https://vercel.com/docs/headers/request-headers),
[Vercel middleware](https://vercel.com/docs/routing-middleware/api),
[Render edge forwarding](https://render.com/articles/host-pocketbase-on-render).
The Render mode is provider-specific and must not be enabled on a generic host.

## Readiness and latency

`/ready` keeps a single in-flight probe and a5second result cache. The probe
still checks actual private-storage write/read/delete, PostgreSQL and Redis.
Failures remain503 and public responses do not expose dependency names.
`READINESS_WAIT_SECONDS` defaults to5 (bounded2..10), covering more than a
two-second healthy storage round trip. A larger wait is not proof that an outage
is fixed. Logs now name each dependency, duration, completion/failure, and the
active stage when the HTTP deadline expires; they never include credentials.
PostgreSQL is not acquired before the storage probe and is returned immediately
after its own check. Redis probe connections are closed.

Synchronous Redis enforcement runs outside the ASGI event loop. Optional
`REQUEST_TIMING_LOGS=true` reports matched route templates, status, response
header/total duration, Redis operations, ORM calls and SQL duration. Pool
acquisition includes opening a new connection as well as queue wait; ORM time
includes compilation/execution, so ORM-minus-SQL is not pure pool wait. No SQL
text, parameters, cookies or concrete resource paths are logged. Signed operator
proof responses also contain these timings; ordinary clients receive no extra
diagnostic header.

Request DB sessions now wait for a per-event-loop admission semaphore **before**
entering synchronous authentication. Its size is bounded by the already
configured DB capacity and half the shared AnyIO thread budget. This
prevents blocked checkouts from consuming every shared AnyIO thread while
authenticated requests await a thread to execute their endpoints. Session
cleanup uses an independent thread limiter and cancellation shielding so it can
return connections even during saturation/disconnect. `db_request_queue_ms`
measures this asynchronous wait. SSE releases this slot before subscription.

## SSE resource policy

* Each account retains the existing five-stream distributed budget.
* `SSE_INSTITUTION_LIMIT` defaults to200; staging explicitly tests600 to cover
  500students plus reconnection headroom. Production must be sized and measured
  before changing this setting.
* `SSE_PROCESS_LIMIT` defaults to1000 and bounds process memory independently of
  tenant limits. Redis leases still renew and expire on crashes.
* `SSE_QUEUE_SIZE` defaults to32. An overflowing slow consumer is closed so the
  client reconnects and rereads durable authorized state; the backlog cannot grow.
* Authentication remains checked for every emitted message and every15second
  heartbeat. Revalidation is one SQL query retaining JWT expiry, current role,
  active account, family and individual-token revocation checks.
* The initial authentication DB connection is closed **before** awaiting Redis
  subscription/lease registration. This avoids holding DB capacity over a Redis
  wait. That fix alone did not resolve the250student pool exhaustion; the shared
  sync authentication/endpoint thread handoff also needed the asynchronous DB
  admission described above. No DB connection or DB admission slot is retained
  for the stream's lifetime.
* Streams retain the120second lifetime. Staging's500student stage must span at
  least150seconds to exercise renewal and reconnection, not just open sockets.

## Staging boundary

`infra/staging/compose.yml` runs two actual API containers, one common Redis,
PostgreSQL and private S3 emulator on isolated volumes/networks. API host ports
bind only127.0.0.1. Use freshly generated staging-only environment and keys; never
reuse a production connection string, institution or signing key. Local results
are not proof that a RenderFree0.1CPU instance supports the same load.

Counter proof must show two different worker and instance fingerprints, one
bucket fingerprint, and one combined allowance across both instances. Capacity
tests use distinct active synthetic users, real bootstrap/courses/calendar
requests and one SSE per user, including cross-instance pub/sub delivery. Stop
on unexpected status/timeouts or latency limits. Production follow-up is a
separate small smoke test, never an automatic500student load.

Local reproducibility (use an available reviewed runtime image in the preparation
script; the recorded image ID is local to the audit machine):

```powershell
apps/api/.venv/Scripts/python.exe scripts/qa/reliability/prepare_staging.py
docker compose --env-file .qa/reliability-staging/staging.env -f infra/staging/compose.yml up -d
docker compose --env-file .qa/reliability-staging/staging.env -f infra/staging/compose.yml run --rm --no-deps api-a python /audit/stage_seed.py
apps/api/.venv/Scripts/python.exe scripts/qa/reliability/stage_shared.py
apps/api/.venv/Scripts/python.exe scripts/qa/reliability/stage_capacity.py
docker compose --env-file .qa/reliability-staging/staging.env -f infra/staging/compose.yml run --rm --no-deps load python -u /audit/stage_sse.py
docker compose --env-file .qa/reliability-staging/staging.env -f infra/staging/compose.yml run --rm --no-deps load python -u /audit/stage_capacity.py --output capacity-linux.json
```

The optional sizing profile is explicitly separate from the1CPU baseline:

```powershell
docker compose --env-file .qa/reliability-staging/staging.env -f infra/staging/compose.yml -f infra/staging/capacity.override.yml up -d --no-deps api-a api-b
docker compose --env-file .qa/reliability-staging/staging.env -f infra/staging/compose.yml -f infra/staging/capacity.override.yml run --rm --no-deps load python -u /audit/stage_capacity.py --arrival-per-second 6.666667 --output capacity-scaled.json
```

It allocates2CPU/1024MB and two Uvicorn workers per API instance, leaving DB/Redis
unchanged. Record actual Docker limits/worker arguments with the report. This
does not change Render billing or demonstrate that a0.1CPU instance handles500.
The generator uses8independent transport pools by default with no more than900
total connections;`--client-pools 1` reproduces the earlier generator. Its optional
`--stages` accepts only an increasing subset of the standard stages and records
that subset: a500-only diagnostic must not be called a gradual capacity pass.

Wait for both APIs to finish startup before sending the proof or load requests.
The fixture command refuses any non-staging database or nonempty institution
table. It creates only synthetic accounts on the reserved example.com domain.
The stage report records failures as well as successes; it does not skip failed
stages to claim500. Preserve reports and stop the dedicated project after work.

The internal Linux generator avoids Docker Desktop's host forwarding path.
Its target allowlist accepts only the two staging loopback URLs or the two
private service URLs. It cannot be redirected to production by changing an
environment URL. Arrival rate is explicit: the default is33.33students/second;
`--arrival-per-second 6.666667` is a different workload and must be reported
separately, preserving fast-arrival failures. The browsing preflight requires
30 visible paid lesson cards and confirms that their content remains locked.
SSE-only results must not be described as complete browsing capacity.

Vercel CLI deployment checks must explicitly target production project
`prj_VseKtzoA9bhCR4aHY7AUtW5Ma3Pr` in organization
`team_nLzjFSHaOLCTq2QmNA2nRXB0`. The existing local `.vercel/project.json`
points to a separate legacy project; do not deploy there accidentally.
