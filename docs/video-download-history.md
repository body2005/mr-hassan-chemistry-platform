# Video download history review — 12 October 2026

## Conclusion and evidence limits

The user's last successful personal IDM test has no exact date, deployment URL,
lesson ID, browser/profile, or captured request. **Its SHA and the change that
caused the observed regression cannot be proved from the available evidence.**
The references below are historical source/deployment anchors, not claims that
any version prevented downloading. No IDM/playback tests were run in this review.

| Reference | Source behavior | Observed deployment history |
| --- | --- | --- |
| `ce5a73137b81d81e42f5283189ae5519bba4eef7` (30 September) | Progressive clear video in `<video src>`, signed token plus live cookie/nonce binding; no video Blob/MediaSource transport or DRM | Vercel Ready, 30 September 21:16:19 Cairo, deployment `FBk1BHByE3NBiv32bFS7j2YF23dX`; Render attempt `dep-daul3kbncjis73cik3c0` Failed |
| `da84e3d8e981a8251bcf9f5dd63ba5ca66df3589` (4 October) | Introduced actual adaptive HLS and hls.js/MediaSource; retained progressive for genuine legacy files; `/stream` rejects attached HLS manifests | Vercel Ready, 4 October 17:43:53 Cairo, deployment `C4PcofJXt1SrzLACpT9FG2wVb4sv`; Render attempt `dep-db16bvbm8hqs73dm5tkg` Failed |
| `0a5d65d98760a2a3b14f24c56b133e1e3860f3a6` (10 October) | Replaced local FileResponse with bounded range transfers (4 MiB), retained same cookie/session authorization and private headers | Vercel Ready; Render succeeded (`dep-db4susflk1mc73ftr2n0`, manual; also `dep-db4ssv15efls73a3eub0`) |
| `f795db8e6e1f7ad9fd7ff6578ede3ac348c847f6` (11 October) | Used hls.js light build for clear H.264/AAC; did not remove content encryption (there was none) | Ready on Vercel and manually deployed on Render |
| `705f2c755ee5568ac83ee52f101beb2c3236d89f` (12 October) | Added object-existence check and separate missing-object/storage-error handling | Later succeeded on Render after storage configuration; does not prove an IDM regression |

At review start Vercel production was `0f74cf18852d9b1f5ffda3e06841c70f793305ec`
(`4HLucxWkS8147fDK61XXnY1JF5Qa`); Render was
`e3dc13d7237e081285416f39ba87d7dcb10d3ad0`
(`dep-db6hf667bikc73c1dml0`). A successful frontend build alone cannot identify
the backend or object storage configuration that served the user's test.

Source evidence: `git show ce5a731:apps/web/src/components/VideoLessonPage.tsx`,
`git show ce5a731:apps/api/app/api/routes/platform.py`,
`git show da84e3d -- apps/api/app/api/routes/platform.py`,
`git show da84e3d:apps/api/app/api/routes/video_uploads.py`,
and subsequent path-specific Git history through the starting HEAD.
The strict cookie/nonce mechanism added earlier in `c1975c8` and tightened in
`ce5a731` still exists in `_authorize_video_stream`. The original/private bucket
URL is not returned by the token endpoint. HLS already rejects superseded
generations and paths outside the exact output allowlist. These controls stop
unauthorized replays; they do not stop an authorized client copying clear media.

The HLS introduction in `da84e3d` is a proven transport change, **not a proven
cause of the reported IDM change**. No deleted DRM or video Blob-fetch mechanism
was found in the reviewed player history. Do not restore the old progressive
player, remove seeking/ranges, disable HLS, or turn on `video_drm_required`.

## Narrow source change selected for deployment

- `services/video_playback.py`: resolve the **attached** ready HLS generation by
  its exact manifest key, rather than the newest ready upload. Require its
  manifest to be in the stored output allowlist. An attached HLS manifest with
  missing generation metadata never falls back to a progressive URL.
- `api/routes/platform.py`: resolve that generation after session authorization
  and before consuming a playback slot; both progressive routes reject HLS
  manifests. Genuine legacy progressive files remain playable.
- `services/lesson_materials.py`: reject video/original/generation objects from
  both material download and preview, regardless of whether DRM is enabled.
  Ordinary PDF/document/image attachments remain available. This closes a
  potential alternate clear-file route in historical LessonAsset records; no
  production record or IDM request was inspected to establish that the user
  exploited it.

The existing HLS authorization, schedule, quality ladder, buffering, seeking,
and original private storage are not changed by this deployment. Old 144p/240p
outputs are not deleted. The pending four-quality/shared-encoder and buffering
enhancements remain intact in the local working tree; they are not silently
included in this narrow deployment. The local DRM adapter's generation resolver
also delegates to the new helper, but no paid DRM code, migration, credential,
worker restart, or DRM setting is included in the deployment commit.

This is closure of concrete code paths, **not restoration of a proven historical
download-prevention mechanism**, and not proof that IDM can no longer obtain a
playable copy. Unencrypted HLS remains copyable by an authorized client.
IDM's [official FAQ](https://internet.internetdownloadmanager.com/register/new_faq/functions20.html)
describes detection of video requests from the web player. A MediaSource Blob
URL does not encrypt those network responses. Future verification must compare
the same lesson/account/browser/IDM setup and capture which route is downloaded,
without sharing cookies or signed URLs. No tests, builds, or scanners were run
locally; only the user-authorized hosting deployment builds may run afterwards.
