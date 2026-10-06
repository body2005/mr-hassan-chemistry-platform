import { afterEach, describe, expect, it, vi } from 'vitest';

describe('payment review hints', () => {
  afterEach(() => { vi.resetModules(); vi.unstubAllGlobals(); });
  it('rejected payments never unlock a lesson; actual approvals emit one unlock', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200 })));
    const sources: Array<{ events: Record<string, (e: { data: string }) => void> }> = [];
    class FakeEventSource {
      events: Record<string, (e: { data: string }) => void> = {};
      constructor() { sources.push(this); }
      addEventListener(name: string, fn: (e: { data: string }) => void) { this.events[name] = fn; }
      close() {}
    }
    vi.stubGlobal('EventSource', FakeEventSource);
    const { realtimeService } = await import('./realtimeService');
    const unlocked = vi.fn();
    window.addEventListener('lms_lesson_unlocked', unlocked);
    try {
      realtimeService.connect();
      await vi.waitFor(() => expect(sources).toHaveLength(1));
      const send = (name: string, data: object) => sources[0].events[name]({ data: JSON.stringify(data) });
      send('payment_reviewed', { product_type: 'lesson', product_id: 'lesson', status: 'rejected' });
      expect(unlocked).not.toHaveBeenCalled();
      send('payment_reviewed', { product_type: 'lesson', product_id: 'lesson', status: 'paid' });
      send('lesson_access_approved', { lesson_id: 'lesson' });
      expect(unlocked).toHaveBeenCalledTimes(1);
    } finally { realtimeService.disconnect(); window.removeEventListener('lms_lesson_unlocked', unlocked); }
  });
});
