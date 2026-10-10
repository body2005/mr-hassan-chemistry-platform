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
