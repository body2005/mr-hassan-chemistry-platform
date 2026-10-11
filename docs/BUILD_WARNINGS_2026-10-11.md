# Frontend build warnings — 2026-10-11

## Changes

- Upgrade ESLint from 9.39.5 to 10.12.0, @eslint/js to 10.0.1, typescript-eslint to 8.71.1, React Hooks plugin to 7.1.1 and React Refresh plugin to 0.5.7. Keep the existing two Hooks checks explicitly; adopting React Compiler diagnostics is separate from upgrading the linter. Preserve the caught enrollment error as `cause`, and remove an overwritten SSE variable initializer flagged by ESLint 10.
- Review esbuild 0.28.2's `install.js`: it locates/installs the platform binary, verifies the binary version, and verifies the shipped binary hash on its download fallback. Record the official npm approval as `allowScripts: { "esbuild@0.28.2": true }`. No blanket script approval or global npm/Node upgrade.
- Lazy-load the student video player when a lesson opens. Use the official HLS light build for the platform encoder's H.264/AAC streams with muxed audio, preserving manual quality switching and adaptive bitrate selection. Emit the HLS transmuxing worker as a separate hashed asset with Vite's `?url` import.

## Compatibility boundary

The light build omits alternate audio/subtitle tracks, EME DRM, advanced MPEG-TS codecs and other optional HLS extensions. The current encoder emits muxed H.264/AAC, and the current transport does not configure EME. If these optional features are introduced later, review the HLS build choice before enabling them. This change does not add DRM or claim that downloading can be prevented. Server-side admission, expiring playback credentials and entitlement checks are retained.

## Verification

- Production build (`tsc -b && vite build`) passes without the chunk-size warning; the default 500 kB threshold is unchanged. Player chunk: 636.46 kB before, 414.51 kB after. Separate worker: 118.23 kB. Largest application chunk after: exportEngine, 430.24 kB. These are emitted sizes, not measured load-time improvements.
- ESLint passes with zero errors and seven existing warnings (Hooks dependencies/cleanup and Fast Refresh exports). These warnings are not the three installation/build warnings addressed here.
- 41 existing tests pass across useHlsTransport, useProtectedPlayback and VideoLessonPage, covering source cleanup, quality selection, the 1080p cap, playback admission and keyboard seeking. No live authenticated playback journey was performed.
- npm 12.2.0 install completes without deprecated-ESLint or unapproved-install-script warnings; `npm rebuild esbuild --foreground-scripts` executes the approved postinstall successfully. A temporary cached Node 24.15.0 was used for this npm 12 verification because the installed Node 24.13.1 is older than npm 12's minimum. The installed system runtimes were not changed.

Deployment evidence and commit identity are supplied in the delivery message. Only frontend files and this note are included; backend deployment is skipped.
