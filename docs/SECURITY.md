# Security model — current source contract (2026-10-06)

Login uses independent IP12/60s and normalized account+institution20/300s
budgets, plus a short account+IP pair budget4/10s before DB/password work.
The short budget returns429/Retry-After (at most10s), never sleeps while
holding a thread/lock. It is attempt-based, not a claim of exponentially
increasing failure delays. An attacker at another IP cannot impose this
pair cooldown on a victim's device; the broader account budget is retained
for distributed guessing and can still cause temporary denial under attack.
All identity keys are domain-scoped HMACs, not plaintext emails.

This is a source contract, not a deployment audit or a promise of zero risk.

## Authentication and recovery

Argon2id protects passwords. Access credentials are signed JWTs with issuer,
session audience, jti, and a server-validated active RefreshSession family.
Refresh credentials are random strings stored only as SHA-256 hashes, rotated
with replay detection and a configurable1–30s grace window (default30s).
Browser credentials are HttpOnly/SameSite=Lax/Secure in all deployment
environments, never returned in auth JSON or kept in localStorage.

The fixed browser contract is matgar_session, matgar_refresh, matgar_csrf.
Unsupported cookie renaming is rejected at startup. Refresh cookie path is
/api/v1/auth. General APIs accept cookies or independent Authorization Bearer
where declared; no general ?token= authentication. Video/preview credentials
remain separate audience/purpose/resource-bound credentials.

Cookie-authenticated unsafe requests need X-CSRF-Token equal to matgar_csrf.
Four anonymous exemptions: login, register, password-reset/request and
password-reset/confirm. Refresh/logout remain cookie endpoints. Origin
allowlisting and compatible Fetch Metadata add protection without granting
authentication or replacing CSRF. CORS credentials are limited to configured
origins; preflight caches600s.

Reset links are random, SHA-256 stored, expire after30min by default, are
consumed only by POST, and all outstanding links become invalid on successful
reset/change-password. Public reset admission commits the SAME padded,
encrypted identity envelope for every validated identity, including unknown
tenants. It does not look up accounts or perform SMTP. A bounded DB consumer
expires admission after5min, checks active ownership and UTC credential epoch,
then atomically mints the token/mail job and completes/erases the identity job.
Requests preceding registration or a password change cannot mint a new link.
New accounts record a UTC credential epoch; pre-migration accounts remain NULL
until their next password change. Reset mail is committed with an encrypted DB
outbox. Delivery retries with bounded backoff and a
stable Message-ID; SMTP is at-least-once, not exactly-once after acceptance
followed by process death. Completed/expired outbox secrets are erased.
Drain BOTH pending identity requests and mail before rotating SECRET_KEY, the domain-separated encryption
key source. No credentials/recipients enter broker arguments or error logs.
Background delivery is DB-backed and independent of broker availability.

Logout revokes the current family/video sessions even when access is absent or
expired, using the verified refresh hash/DB row; other devices stay active.
Password reset/change revokes all account families. Cleanup deletes only expired
session/reset evidence after7days additional retention, in bounded batches.
A detected old-token reuse is not proof of theft. Notification/audit are deduped
per family. Current API/SSE family checks remain authoritative across workers.

Temporary network/5xx/429/CSRF refresh failure preserves account and draft.
The frontend returns a recoverable error, no automatic request storm, with a
per-tab10s cooldown reset on a new auth generation. Definitive refresh401
invalidates identity but never erases unrelated drafts.

## Authorization and tenant/resource boundaries

Roles are explicit, not a blanket hierarchical bypass. Every sensitive route
must check identity, role, institution, resource ownership and workflow state.
Teachers manage/read only their own course scope and related students;
students read entitled/published content. Platform admins do not automatically
gain cross-tenant report scope. Reports reject students and scope every
aggregate/top quiz. Independent regression evidence is in dated QA ledgers;
this document does not claim every route has been penetration-tested.

Learning-objective codes are unique per institution/course and per institution
global NULL scope using partial unique indexes. Legacy code evidence resolves
to the quiz-course override before a global fallback. Conflicting historical
rows stop migration; no arbitrary merge/delete of parent/mastery history.
New/published MCQs support at most26 choices, text keys A–Z; old snapshots
and attempt keys are never silently rewritten.

## Transport, limiting and storage

production, production_like and staging reject known/short secrets, insecure
cookies, HTTP frontend origins, disabled rate limiting and missing SMTP/payment
configuration. Development/testing are explicit choices. Trusted proxies must
be confirmed exact IPs/CIDRs, not *. Cookies do not trust raw forwarded proto;
Uvicorn applies forwarding only for configured peers. External provider CIDRs
still require operator confirmation.

Redis sliding-window policies stack once per exact budget. Login uses IP and
HMAC-normalized account/institution budgets before DB/Argon2, with dummy verify
for unknown/inactive accounts. No long sleeps or unbounded account locks.
Refresh and other credential mutations retain the original shared default
auth15/60s ceiling; the refresh route60/min guard does not relax it. Stricter
route policies stack, including reset5/300s. GET/HEAD profile/closed legacy avatar reads use
read budgets, not the credential-mutation budget.
Redis outage fails closed in deployment; development fallback is bounded4096
keys.429 includes Retry-After, and the frontend does not auto-retry it.

Personal account photos are disabled for all roles. Old authenticated avatar
endpoints return410; auth responses expose no avatar URL and the browser ignores
old cached URLs. Existing private data is retained, not exposed or deleted.
Video device admission counts a validated refresh family rather than rotating
access JWTs; playback still requires the token's EXACT current-jti cookie nonce.
Legacy jti slots expire normally; upgrading never resets a live device budget.

Local storage operations use one canonical containment resolver; absolute
legacy keys work only inside the root. Traversal and symlink/junction escape
are rejected. This provider flaw is not proof of an exploitable remote file
read/delete endpoint. Object storage is private and persists separately from
app containers; only authorized streaming/purpose-bound links expose content.

Headers: nosniff, SAMEORIGIN, strict-origin-when-cross-origin, restrictive
Permissions-Policy; HTTPS deployments add HSTS and API CSP. Browser rendering
escapes formula fallbacks and uses KaTeX trust=false. Video signed sessions,
entitlements and watermarking do not equal Widevine/PlayReady or prevent screen
recording. External DRM/CDN configuration is not proven by local tests.

## Monitoring, images, CI and evidence

Public health/ready probes remain anonymous; ready reveals only status.
Detailed ready and metrics require platform-admin authentication. A5s cache,
one background probe per process and a2s HTTP wait budget bound probe load.
Each dependency also has finite timeouts; a still-running slow probe is reused,
not queued repeatedly. No long-lived SSE DB connection is held.

Supported API build: docker build -f infra/Dockerfile.api apps/api.
Deprecated root Dockerfile was retired after checking deployment references.
Runtime UID/GID10001, code read-only, writable staging only, dropped capabilities
and no-new-privileges. Non-root is containment, not a CVE fix.

.github/workflows/quality.yml declares regression, migration, frontend,
browser, secret, dependency and image gates with read-only repository
permissions and synthetic credentials. A workflow file is not evidence of a
successful remote run. Artifacts must never include env/cookie jars/traces/mail
bodies/DB backups or model weights containing secrets. CI result uploads are
limited to JUnit, redacted scan results, image identity and synthetic screenshots.

Known release gates remain in the dated follow-up ledger: native High findings,
strict OCR fidelity, representative staging capacity and external provider
TLS/CDN/DRM/storage evidence. No production-ready claim with an open gate.
