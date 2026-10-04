# Production Docker: SeaweedFS/S3 operator runbook

This is a deployment candidate, not external deployment approval. The September report is historical; use [QA_AUDIT_2026-10-03.md](QA_AUDIT_2026-10-03.md) for current code/image checks and open gates. No real server, public certificate, real merchant payment or external email delivery has been tested.

## Production settings

Copy `infra/.env.production.example` outside Git. Set the real HTTPS origin, SMTP credentials, payment destinations, TLS certificate/key, and durable access-controlled backup directory. Create independent random secret files: PostgreSQL password, app signing key, S3 password, SMTP password. Restrict OS file permissions. Do not print resolved configuration containing secrets or commit secret files.

Only the proxy publishes ports 80/443. PostgreSQL, Redis, API, worker, web, and S3 have no host mappings. Test-only Mailpit publishes its inbox on loopback via a separate QA overlay; never include that overlay on a public server. Internal traffic is unencrypted on a trusted single-host Docker network. The network is not an air gap: outbound access exists for SMTP and required services.

SeaweedFS 4.48 is pinned to `sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d`. Its `mini` single-node layout persists all components under `s3data:/data`; this is not clustered HA. Credentials come from Docker secrets, the default bucket is private, and the app uses signed S3 operations via the private endpoint. Review size/capacity, replication, monitoring and disk redundancy before selecting a real host.

PostgreSQL, Redis, Python, Node and Nginx upstream images are pinned too. Build the app images from the reviewed code snapshot and record resulting image IDs. A successful scanner invocation does not mean zero CVEs; inspect the findings.

```sh
docker compose --env-file /secure/production.env -f infra/docker-compose.yml config -q
docker compose --env-file /secure/production.env -f infra/docker-compose.yml up -d --build
docker compose --env-file /secure/production.env -f infra/docker-compose.yml ps
```

Migrations run once before API/worker startup. Alembic escapes ConfigParser percent interpolation while preserving URL-encoded passwords. Configure initial authorized identities through the seed script only after reviewing its environment. Do not run the QA seeder on real data.

## Local reproduction from a clean clone

Windows prerequisites: Docker Desktop Linux Engine, PowerShell 7, Node/npm, Git and network access to pinned registries/npm/PyPI. The script accepts `-Docker` for other executable locations. All generated credentials, certificates, media, backup snapshots, JUnit and SARIF artifacts stay under ignored `.qa/production`.

```powershell
./scripts/qa/run-production.ps1 -Stage All
# Independent second QA project, without deleting an existing project's data:
./scripts/qa/run-production.ps1 -Project chemistryaudit2 -Stage All
```

This builds the REAL `infra/docker-compose.yml` plus `infra/qa/production.override.yml` as `chemistryprodlocal`, with fresh synthetic data, loopback HTTPS 18443, HTTP 18480 and Mailpit 18425. It generates a 14-day local test certificate. Python clients and SMTP explicitly trust that certificate; only Playwright's explicit local-test setting accepts the self-signed certificate. Production SMTP verification remains enabled and cannot be disabled by production settings.

The overlay adds resource limits, disposable test tooling, and a QA-only Celery recovery probe. It does NOT substitute the production store or expose PG/Redis/S3. Only the QA runner gets the Docker socket to inject failures into the exact isolated project. Do not mount that socket in app containers or use this harness against real data.

The second project uses `.qa/audit2`, HTTPS 18543, HTTP 18580 and Mailpit 18525. Both projects use the same production template and pinned store. Do not copy a QA overlay to a public server. The local self-signed certificate explains Chrome's warning; it is not evidence that authenticated API mutations should return 401/422. Never disable browser security globally to use this harness.

Stages `Prepare`, `Storage`, `Tests`, `Load`, `Dependencies`, `Scan`, `Extract` can be rerun individually, with prerequisites already created. API and browser suites run sequentially. Only shared-IP auth counters are cleared BETWEEN serial cases in the allowlisted QA project; user rate windows, video/session ledgers and admission limits are not erased. Reused demo users wait for their actual auth window to expire; publication tests provision a distinct synthetic teacher per case. The real limits remain active WITHIN each case. Cleanup uses actual logout/revoke-all rather than changing limits. Failed gates throw and stop; no stage pushes, merges or publishes. Review commands-<stage>.json, api-unit-tests.xml, api-integration-tests.xml, browser-tests.xml, load.json, scout-*.sarif and extract-fidelity.json. These artifacts can contain synthetic user data; do not share generated secret files.

The in-process SQLite test app uses `QA_UNIT_REDIS_URL` (DB15); fixture maintenance never clears the actual HTTPS app's Redis DB0. A live regression preserves a unique sentinel in DB0 across unit resets. Keep these URLs distinct. This separation changes test tooling only, not production rate limits.

`Dependencies` creates a clean temporary virtualenv, installs the project, builds its wheel and compares every active runtime requirement against the exact version lock, installed distribution and wheel metadata. Dev transitive dependencies are not fully locked; this is not hash-verified reproducibility. `Extract` compares blind inputs against separately transcribed question stems and ordered options, not merely counts/types. It fails on textual discrepancies even if the structural tests pass. Do not replace this gate with a weaker test or silently repair text from the expected reference.

Legacy `infra/qa/compose.yml` preserves the earlier HTTP-only test harness, not the production evaluation. The older mixed-load smoke script is historical; use the longer new `scripts/qa/run-production.ps1 -Stage Load`.

## Readiness, failure recovery and logs

`/api/v1/health` is liveness; `/api/v1/ready` tests DB, Redis, S3 write/read/delete and Celery ping. S3 readiness caches for only 5 seconds. A Celery ping is not evidence that a removed product workflow exists: the old Knowledge Center indexer/routes were removed. Its integration test now checks actual Celery durable delivery using an explicitly QA-only task, without claiming product indexing.

DB/S3 connection failures produce sanitized 503 + Retry-After, not 500 or a false “file missing”. Genuine missing S3 keys remain 404. The proxies have 3-second connect timeouts; gateway outages may return 502/504. A bind-mounted proxy config change needs `nginx -t` followed by reload/recreation—`up` alone may not reload it.

Password reset retains a generic 200 when configured SMTP fails to avoid revealing account existence; the sanitized delivery failure is logged. Monitor that error and retry after recovery. A 200 is not proof that email arrived. Unconfigured SMTP returns 503. Local Mailpit proves the browser reset flow and verified local SMTP TLS, not real inbox delivery.

Video tokens bind to a live cookie/session, role, institution and current entitlement. Logout/revocation invalidates old playback; links alone do not grant access. Query tokens are redacted from app logs. Nginx uses a privacy access format with the path (never query, cookies or referer), status, upstream status and request duration. Raw per-server error logs are intentionally disabled because Nginx cannot redact request arguments in upstream errors/buffering warnings; startup/configuration diagnostics and safe status/timing logs remain. Response buffering is off for API streams. Monitor safe 4xx/5xx and upstream timings plus sanitized application errors. A live regression streams a large video, stops the API, checks gateway failure, restarts it and checks all three HTTP-hop logs for the actual signed token. This is access protection, NOT absolute anti-copy: an authorized client can copy delivered bytes or screen-record. No DRM/CDM provider has been configured.

## Consistent backup and safe restore

For a coherent DB/S3 snapshot, quiesce app/worker writers and block user traffic first. Separate jobs do not create an atomic cross-store snapshot by themselves. Never run `down -v` on data that must be retained.

```sh
docker compose --env-file /secure/production.env -f infra/docker-compose.yml stop api worker
docker compose --env-file /secure/production.env -f infra/docker-compose.yml run --rm backup-postgres
docker compose --env-file /secure/production.env -f infra/docker-compose.yml run --rm --build backup-s3
docker compose --env-file /secure/production.env -f infra/docker-compose.yml run --rm --build backup-videos
docker compose --env-file /secure/production.env -f infra/docker-compose.yml up -d
```

PostgreSQL writes a timestamped custom-format dump and checks its catalog. S3 writes a NEW timestamped snapshot with object keys, sizes, SHA-256 and content metadata, never credentials. Object keys are not used as filesystem paths. It detects changed listings/ETags and writes a manifest only after a completed snapshot. Versioned objects/bucket IAM configuration are not copied; configure equivalent private IAM on the new server separately. Encrypt backups, copy offsite, monitor failures and define retention; the local bind mount is not an offsite recovery solution.

`apps/api/scripts/s3_snapshot.py restore --snapshot /path/to/snapshot` reads S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET from the operator environment. It verifies every local payload before writing, requires an empty destination, preserves content metadata and checks all restored keys/bytes. It never overwrites a nonempty destination. Use the SAME bucket name on a NEW store when DB records contain canonical `s3://bucket/key` paths; renaming that bucket requires a reviewed DB path migration.

For PostgreSQL restore into a NEW DB using `pg_restore --exit-on-error --no-owner --no-privileges`. Compare all application table rows, not just table counts. Restore any legacy local video archive into a new compatible volume and compare file checksums. Current S3-backed videos are included in the S3 snapshot; an empty legacy video volume is expected and is not a video backup failure.

The repeatable local drill `scripts/qa/production-storage-drill.ps1` recreates source containers without deleting volumes, freezes writers, runs all backups, creates fresh restore volumes, verifies DB rows and SHA-256/content metadata, switches the actual API temporarily to restored S3, tests video/full download/ranges/permissions, then returns it to the original store. Restore volumes are retained and their services stopped, not deleted. Failed checks still return the API to its original configuration.

After restoration the drill waits for the worker's Docker health check and polls real HTTPS readiness (verified local certificate) for at most 160 seconds, both on restored storage and after returning to the source. A fixed five-second sleep was insufficient during asynchronous worker startup; 503/degraded is never accepted as success. The last change was in this host-side harness, not runtime application code, and the complete drill was rerun successfully on the same final images.

## Old MinIO data

Do not mount MinIO data directories into SeaweedFS. Preserve old volumes read-only. If actual old objects exist, bring up the compatible old MinIO version with its credentials in an isolated network, use this provider-neutral snapshot tool against its S3 API, and restore to a fresh SeaweedFS bucket. Verify object listing, SHA-256, metadata and private access before changing the application endpoint. Keep old data until migration approval. No actual MinIO data migration is claimed by the synthetic local drill.
