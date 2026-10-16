# Parallel lesson video uploads — 2026-10-16

The browser now uploads up to three missing S3 multipart parts concurrently per
video, with at most two upload tasks (six part transfers) active in this manager.
Each current part is 32 MiB. The entire file is not read into JavaScript memory.

Progress combines server-confirmed completed parts and the actual bytes reported
by each active PUT, without double counting when parts finish out of order. The
existing single end-to-end bar stays monotonic and below 100 until the server
reports the encoded video ready. Multipart completion runs only after every PUT
succeeds. Encoding, qualities, playback permissions and scheduling are unchanged.

Failure stops sibling transfers and drains them before an explicit retry. Retry
re-reads the server's actual ListParts and skips completed parts. Cancellation,
account changes and removal of an active task abort all its part transfers.
Store requests receive neither application cookies nor bearer credentials.

Validation: 30 focused tests covering the helper, upload manager and recovery;
production TypeScript/Vite build passed. No upload throughput improvement has
been measured.

Deployment requires `VIDEO_DIRECT_UPLOAD_ENABLED=true`, an HTTPS
`VIDEO_UPLOAD_PUBLIC_ENDPOINT` pointing to the existing private object store,
and a bucket CORS rule allowing PUT from the exact production frontend origin.
Do not enable public reads or use a wildcard origin to activate this feature.
Before activation, the live capability check returned `direct_upload=false` and
the production-origin PUT preflight returned 403 without CORS headers. A code
deployment by itself therefore does not activate parallel uploads.
