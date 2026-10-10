import { afterEach, expect, it, vi } from 'vitest';
afterEach(() => {vi.useRealTimers(); vi.unstubAllGlobals(); vi.resetModules();});

it('honors Retry-After on the realtime identity probe without a reconnect storm', async () => {
  vi.useFakeTimers();
  const fetch = vi.fn(async()=>new Response(JSON.stringify({detail:'busy'}), {status:429,headers:{'Retry-After':'60'}}));
  vi.stubGlobal('fetch', fetch); vi.stubGlobal('EventSource', class {});
  const {realtimeService} = await import('./realtimeService');
  realtimeService.connect();
  await vi.advanceTimersByTimeAsync(0);
  expect(fetch).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(59999); expect(fetch).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(1); expect(fetch).toHaveBeenCalledTimes(2);
  realtimeService.disconnect();
});

it('backs off telemetry batches after 429 and never sends simultaneous flushes', async () => {
  vi.useFakeTimers();
  const fetch = vi.fn(async()=>new Response('{}', {status:429,headers:{'Retry-After':'60'}}));
  vi.stubGlobal('fetch', fetch);
  const {VideoTelemetryTracker} = await import('./videoTelemetry');
  const tracker = new VideoTelemetryTracker('lesson');
  tracker.record('play', document.createElement('video'));
  await Promise.all([tracker.flush(), tracker.flush()]);
  expect(fetch).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(59999); await tracker.flush(); expect(fetch).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(1); await tracker.flush(); expect(fetch).toHaveBeenCalledTimes(2);
});

it('silently stops denied background telemetry instead of retrying or showing player errors', async () => {
  vi.useFakeTimers();
  const fetch = vi.fn(async () => new Response('{"detail":"Student telemetry only"}', { status: 403 }));
  vi.stubGlobal('fetch', fetch);
  const { subscribeToRequestErrors } = await import('./errorFeedback');
  const onError = vi.fn();
  const unsubscribe = subscribeToRequestErrors(onError);
  const { VideoTelemetryTracker } = await import('./videoTelemetry');
  const tracker = new VideoTelemetryTracker('lesson');
  const video = document.createElement('video');
  tracker.attach(video);
  tracker.record('play', video);
  await tracker.flush();
  tracker.record('pause', video);
  await vi.advanceTimersByTimeAsync(120000);
  await tracker.flush();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(onError).not.toHaveBeenCalled();
  tracker.detach(); unsubscribe();
});
