# Local playback and navigation follow-up

Source changes only on `fix/queen-p0-handoff`. No tests, builds, scanners,
browser checks, benchmarks, deployments or worker restarts were run.

## Refresh and navigation

The old history entry remembered only a lesson ID; resolving that ID depended on
an in-memory map that disappears on Refresh. Player entries now retain lesson,
course, account, originating hash and list scroll position. No video URL, signed
token or serialized lesson content is stored in history.

After account/catalog hydration, the player resolves the entry from the current
account's catalog and restores the course/year selection. Student restoration
also fetches current course assessment access before opening the lesson. Back
returns to the originating list; playlist selection replaces the same player
entry. Old entries lacking account/course metadata cannot be restored safely.
Playback admission still enforces authorization and scheduling on the server.
Existing saved watch position and student seek restrictions are unchanged.

## Actual buffer display

The timeline uses `video.buffered` to render every downloaded interval separately,
including islands after seeking. Media events and HLS append/flush events update
the ranges. Downloaded ranges use `rgb(163, 153, 146)`, unbuffered track uses
`rgb(95, 80, 70)` and played progress keeps its existing accent. Previously the
background layer represented watched progress rather than downloaded bytes.

Loading feedback follows actual waiting/seeking with insufficient media data
while playing; background network activity and clicking Play alone do not show
it. Pausing, playing, can-play or errors clear the indicator.

## Forward buffer and resource bounds

HLS starts with a 60-second forward target and automatic bandwidth-based quality
selection. Actual completed fragments and hls.js bandwidth estimates permit
15-second increases when the connection exceeds the selected stream bitrate
by 1.5x and the current buffer is approaching its target. There is no time-based
increase and no requirement to finish buffering before playback starts.

- Devices reporting more than 4 GiB: up to 120 seconds ahead, 20 seconds behind,
  with a 64 MiB encoded-media planning budget.
- Devices reporting 4 GiB or less, or no memory information: up to 90 seconds
  ahead, 10 seconds behind, with a 24 MiB planning budget.
- The time target is reduced at high bitrates to respect the planning budget,
  reserving 20% bitrate headroom and the retained back-buffer time. The minimum
  forward target is 12 seconds so complete segments remain loadable.
- hls.js `maxBufferSize` is a minimum byte target, not a hard RAM limit. Both time
  bounds and finite back/front retention are configured; the browser ultimately
  controls SourceBuffer and decoder memory, may evict media, and may reduce
  buffering further under memory pressure. A large individual segment can exceed
  the planning budget. Native HLS buffering remains browser-controlled.
- Seeking outside downloaded ranges cancels the current distant fragment and
  restarts loading at the new playhead. A transport stopped for a fatal/access
  error is not restarted by seeking. Quality selection, rate and audio remain
  unchanged by this loading operation.

Manual quality selection remains available and retains the prior safe-switch
behavior; automatic mode remains the default. This cannot guarantee uninterrupted
playback on every connection or a buffer extending to the end of a long video.

## Long playback and private requests

Token admission records the server's `expires_in` (300 seconds fallback for older
responses). Successful renewal schedules the next renewal before expiry. HLS
XHR requests await the shared renewal if needed and substitute only the current
credential, restricted to the admitted origin, lesson and generation prefix.
Concurrent requests share one renewal; expired/denied scopes cannot send it.
Successful cookie refresh also emits a non-secret session change marker (shared
across tabs). Media admission refreshes for the newly rotated cookie before the
next HLS request, retaining the server's strict token-to-session binding.

For the same HLS generation, renewal preserves MediaSource and its buffer rather
than reloading the player every four minutes. A different generation, native HLS
or explicit recovery still uses the existing saved-position transport replacement.
Renewal failure stops loading and presents recovery; it does not create an
automatic failure retry loop or bypass 401/403/404/429 decisions. Account changes
abort requests and release the old source. No public URL or download control was
added, and entitlement/schedule rules were not changed.

## Badge colors

Assignment history/preview badges and the teacher studio header explicitly use
`rgb(15, 118, 110)` on the existing light mint badge treatment. Scoped CSS keeps
generic dark-mode color overrides from replacing this requested text color.

All behavior above is based on source inspection; runtime verification remains
outstanding under the user's no-execution instruction.
