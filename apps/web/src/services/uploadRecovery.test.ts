import { afterEach, beforeEach, expect, it, vi } from 'vitest';

let automaticStatus: number | null = null;
class FakeUpload {
  static UNSENT = 0;
  static instances: FakeUpload[] = [];
  readyState = 0;
  status = 0;
  responseText = '';
  withCredentials = false;
  timeout = 0;
  upload = { onprogress: null as ((event: ProgressEvent) => void) | null };
  onload: (() => void | Promise<void>) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;
  open = vi.fn(() => { this.readyState = 1; });
  setRequestHeader = vi.fn();
  abort = vi.fn(() => { this.readyState = 0; this.onabort?.(); });
  send = vi.fn(() => {
    if (automaticStatus !== null) queueMicrotask(() => this.respond(automaticStatus!));
  });
  constructor() { FakeUpload.instances.push(this); }
  respond(status: number) {
    this.readyState = 4;
    this.status = status;
    this.responseText = JSON.stringify(status === 200 ? { id: 'qa-upload' } : { detail: 'Synthetic upload rejection' });
    void this.onload?.();
  }
}
beforeEach(() => {
  FakeUpload.instances = [];
  automaticStatus = null;
  vi.stubGlobal('XMLHttpRequest', FakeUpload);
});

it.each(['network', '503', '429', '403'])('a 401 after transfer plus %s refresh failure preserves account without replaying bytes', async failure => {
  automaticStatus = 401;
  localStorage.setItem('lms_cached_user', '{"id":"student"}');
  localStorage.setItem('qa_draft', 'kept');
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/auth/refresh')) {
      if (failure === 'network') throw new TypeError('offline');
      return new Response('{}', { status: Number(failure) });
    }
    return new Response('{}', { status: 200 });
  });
  vi.stubGlobal('fetch', fetch);
  const api = await import('./apiClient');
  api.setApiAuthScope('student');
  api.markBrowserSessionActive(true);
  await expect(api.uploadWithProgress('/lessons/qa/materials', new FormData()))
    .rejects.toMatchObject({ code: 'SESSION_REFRESH_UNAVAILABLE' });
  expect(FakeUpload.instances).toHaveLength(1);
  expect(FakeUpload.instances[0].send).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(1);
  expect(api.isSessionKnownInvalid()).toBe(false);
  expect(api.hasBrowserSession()).toBe(true);
  expect(localStorage.getItem('lms_cached_user')).not.toBeNull();
  expect(localStorage.getItem('qa_draft')).toBe('kept');
});

it('renews after a late upload401 but requires explicit retry instead of replaying multipart', async () => {
  automaticStatus = 401;
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200 })));
  const api = await import('./apiClient');
  api.setApiAuthScope('student');
  await expect(api.uploadWithProgress('/lessons/qa/materials', new FormData()))
    .rejects.toMatchObject({ code: 'UPLOAD_RETRY_REQUIRED', status: 401 });
  expect(FakeUpload.instances).toHaveLength(1);
  expect(FakeUpload.instances[0].send).toHaveBeenCalledTimes(1);
  expect(api.isSessionKnownInvalid()).toBe(false);
  expect(api.hasBrowserSession()).toBe(true);
});

it('invalidates only a definitive refresh401 and preserves unrelated drafts', async () => {
  automaticStatus = 401;
  localStorage.setItem('lms_cached_user', '{}');
  localStorage.setItem('qa_draft', 'kept');
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response('{}', { status: url.endsWith('/auth/refresh') ? 401 : 200 })));
  const api = await import('./apiClient');
  api.setApiAuthScope('student');
  await expect(api.uploadWithProgress('/lessons/qa/materials', new FormData())).rejects.toMatchObject({ status: 401 });
  expect(FakeUpload.instances[0].send).toHaveBeenCalledTimes(1);
  expect(api.isSessionKnownInvalid()).toBe(true);
  expect(localStorage.getItem('lms_cached_user')).toBeNull();
  expect(localStorage.getItem('qa_draft')).toBe('kept');
});

it('honors owner cancellation before send even if the browser emits no abort event', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200 })));
  const api = await import('./apiClient');
  api.setApiAuthScope('student');
  await expect(api.uploadWithProgress('/lessons/qa/materials', new FormData(), undefined, 0, xhr => {
    const fake = xhr as unknown as FakeUpload;
    fake.onabort = null;
    fake.abort();
  })).rejects.toMatchObject({ code: 'ABORTED' });
  expect(FakeUpload.instances[0].send).not.toHaveBeenCalled();
});
afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); localStorage.clear(); });

it.each(['network', '503', '429'])('does not transfer bytes or erase account on pre-upload refresh outage: %s', async failure => {
  automaticStatus = 401;
  localStorage.setItem('lms_cached_user', '{"id":"student"}');
  localStorage.setItem('qa_draft', 'kept');
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/auth/refresh')) {
      if (failure === 'network') throw new TypeError('offline');
      return new Response('{}', { status: Number(failure) });
    }
    return new Response('{}', { status: 401 });
  });
  vi.stubGlobal('fetch', fetch);
  const api = await import('./apiClient');
  api.setApiAuthScope('student');
  api.markBrowserSessionActive(true);
  await expect(api.uploadWithProgress('/payments/orders/qa/receipt', new FormData()))
    .rejects.toMatchObject({ code: 'SESSION_REFRESH_UNAVAILABLE', status: 503 });
  expect(FakeUpload.instances).toHaveLength(0);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(1);
  expect(api.isSessionKnownInvalid()).toBe(false);
  expect(api.hasBrowserSession()).toBe(true);
  expect(localStorage.getItem('lms_cached_user')).not.toBeNull();
  expect(localStorage.getItem('qa_draft')).toBe('kept');
});

it.each([200, 401])('a late upload response %s cannot overwrite or log out the new account', async status => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200 })));
  const api = await import('./apiClient');
  api.setApiAuthScope('old');
  const pending = api.uploadWithProgress('/lessons/qa/materials', new FormData());
  const cancelled = expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' });
  await vi.waitFor(() => expect(FakeUpload.instances).toHaveLength(1));
  api.setApiAuthScope('new');
  api.markBrowserSessionActive(true);
  localStorage.setItem('lms_cached_user', '{"id":"new"}');
  FakeUpload.instances[0].respond(status);
  await cancelled;
  expect(FakeUpload.instances[0].abort).toHaveBeenCalledTimes(1);
  expect(api.getApiAuthScope()).toBe('new');
  expect(api.isSessionKnownInvalid()).toBe(false);
  expect(localStorage.getItem('lms_cached_user')).toBe('{"id":"new"}');
});
