# Shared video pipeline and unified upload progress

Changes prepared locally on `fix/queen-p0-handoff`. No tests, builds, scanners,
benchmark, deployment, worker rebuild or worker restart were run for this change.
Updated test source is included but has not been executed. Production continues
to run the previously deployed version.

## Encoding

- New jobs select only 360p, 480p, 720p and 1080p at or below the source height.
  A source below 360p gets one native-height rendition, rounded down to even
  dimensions. Width is also rounded down, never enlarged. Existing lower-quality
  files, manifests and playback routes are not migrated or removed by this change.
- One FFmpeg process and one input decoder feed a common 30fps timeline, then a
  `split` and one `scale` branch per rendition. Each branch produces its own VOD
  HLS playlist and segments during that same invocation. This follows FFmpeg's
  documented [complex-filtergraph model](https://ffmpeg.org/ffmpeg.html#Complex-filtergraphs).
- Audio remains optional and is included in every output when present, with AAC
  stereo and timestamp-aware resampling. Six-second keyframes, a closed GOP,
  identical frame rate and disabled scene-cut keyframes align the video outputs.
- Temporary HLS files are renamed on completion. Before creating the master,
  every media playlist must end, reference nonempty local segments, and have
  matching segment counts/durations across renditions. The master declares the
  actual encoded dimensions and optional audio bandwidth.

## Resource limits and recovery

- The current PC Compose service remains limited to two vCPUs, 2560MiB memory
  and 128 PIDs. The configured CPU ceiling is two, further bounded by affinity
  and cgroup v1/v2 quota. Raising that environment ceiling alone cannot bypass
  a container quota.
- Decoder and filter pools use one thread on that configuration, and each video
  encoder uses one thread with a bounded lookahead pool. Four renditions share
  the CPU quota; they cannot each have a dedicated CPU on a two-vCPU service.
  This is a single shared graph, not four unconstrained FFmpeg subprocesses.
- FFmpeg address space stays at most 2GiB, reduced when a lower cgroup memory
  limit requires headroom. Less than 512MiB of available budget fails explicitly.
  Insufficient memory does not silently omit requested qualities or switch to
  sequential encoding. Some large sources can still exceed this fixed budget.
- Existing disk safeguards remain: worker preflight reserves source size plus
  26GiB; output is capped at 24GiB, individual files at 256MiB, with at least
  1GiB scratch free space and at most 15,000 output files. The shared invocation
  has a finite resource-dependent safety deadline capped at 24 hours, not an ETA.
- At most four object uploads are submitted concurrently, with progress based
  on bytes of successfully saved objects. This pool uploads files; it does not
  launch encoders. Durable output intents still precede remote writes.
- Advisory locks, isolated attempt directories/prefixes, retry limits, cleanup
  outbox, protected playback, publication scheduling and final ready transaction
  remain in place. No ready status is committed until every output and the
  retained source copy have been saved. Crash recovery retains the progress
  high-water mark while fully rebuilding the interrupted generation.

## Teacher experience

- The lesson card and global upload widget use the same one-bar component and
  the title `جاري رفع الفيديو…`. Quality names and encoding stages are hidden.
- The percentage represents completed work rather than elapsed time: file bytes
  contribute 0–40%; the server's source-byte, common encoded-time and saved-output
  progress contributes 40–99%. These are fixed work weights, not a duration or
  speed estimate. Updates preserve the maximum observed overall percentage.
- Only an authoritative ready acknowledgement completes the task at 100% and
  displays `تم رفع الفيديو بنجاح`. If duration metadata is absent, encoding
  progress holds its known milestone until the finished playlists can be read.
- A moving highlight remains visible while waiting for actual updates without
  increasing the percentage. Reduced-motion preferences disable that animation.
- Failures remain visible with an explicit retry action. Failed tasks no longer
  produce a green completed indicator. Processing-disabled capabilities reject
  new transfers instead of presenting raw-file storage as completed HLS work.
- Retry reads the existing job first. Ready/processing jobs need no new file
  upload; incomplete multipart jobs reuse their identity and acknowledged parts.
  Only a terminal or absent job gets a fresh intent on explicit retry.
- The visible “same video” message and native “Choose File” input are removed.
  If a browser reload has discarded access to an incomplete local file, retry
  may still open the system file picker through a hidden input. Browser file
  access cannot be restored from localStorage alone. Fingerprint validation
  prevents attaching a different file to a partially uploaded job.
- The lesson's upload circle is `rgb(17 24 39)` in dark mode.

## Playback follow-up

- The playback buffering message is now a centered loading indicator with an
  accessible status label and a reduced-motion fallback. It follows the existing
  media waiting/playing/pause/error events, with no artificial delay.
- Manual quality selection uses hls.js `nextLevel` instead of `currentLevel`.
  The old setter unconditionally flushed the entire playback buffer. The new
  setter preserves the playing fragment and schedules a switch using hls.js's
  buffer and fetch-time estimates. Re-selecting the current mode is a no-op.
- The selected menu entry denotes the requested quality. Its picture may appear
  at a later segment boundary; a slow connection can still cause buffering.
  Token renewal, access controls, resolution caps and native HLS are unchanged.
- Existing transport test source was updated, but no tests, builds, scanners,
  playback measurements or production actions were performed for this follow-up.

No speed improvement has been measured. Runtime encoding, audio alignment,
quality switching, resume, failure/recovery and responsive rendering still need
execution-based verification before a future production rollout is authorized.
