import { afterEach, expect, it, vi } from 'vitest';
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.resetModules(); localStorage.clear(); });

it.each(['network', '503', '429', '403'])('preserves account and draft after temporary refresh failure: %s', async failure => {
  localStorage.setItem('lms_cached_user', '{"id":"student"}');
  localStorage.setItem('qa_draft', 'unchanged');
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
  await expect(api.apiRequest('/auth/me', { skipCache: true })).rejects.toMatchObject({ code: 'SESSION_REFRESH_UNAVAILABLE', status: 503 });
  await expect(api.fetchApiBlob('/assignments/file')).rejects.toMatchObject({ code: 'SESSION_REFRESH_UNAVAILABLE' });
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(1);
  expect(api.isSessionKnownInvalid()).toBe(false);
  expect(api.hasBrowserSession()).toBe(true);
  expect(localStorage.getItem('lms_cached_user')).not.toBeNull();
  expect(localStorage.getItem('qa_draft')).toBe('unchanged');
});

it('clears cooldown after a new auth generation and renews only once', async () => {
  let failing = true, reads = 0;
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/auth/refresh')) return new Response('{}', { status: failing ? 503 : 200 });
    return new Response('{}', { status: failing || ++reads === 1 ? 401 : 200 });
  });
  vi.stubGlobal('fetch', fetch);
  const api = await import('./apiClient');
  api.setApiAuthScope('first');
  await expect(api.apiRequest('/auth/me', { skipCache: true })).rejects.toMatchObject({ status: 503 });
  failing = false;
  api.setApiAuthScope('second', true);
  await api.apiRequest('/auth/me', { skipCache: true });
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(2);
});

it('does not let a delayed refresh from a previous account update the current account', async () => {
  let finish!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/auth/refresh')
    ? new Promise<Response>(resolve => { finish = resolve; }) : new Response('{}', { status: 401 })));
  const api = await import('./apiClient');
  api.setApiAuthScope('old');
  const request = api.apiRequest('/auth/me', { skipCache: true });
  const rejected = expect(request).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' });
  await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
  api.setApiAuthScope('new');
  api.markBrowserSessionActive(false);
  finish(new Response('{}', { status: 200 }));
  await rejected;
  expect(api.getApiAuthScope()).toBe('new');
  expect(api.hasBrowserSession()).toBe(false);
});

it('a definitive refresh 401 invalidates the session, without deleting unrelated drafts', async () => {
  localStorage.setItem('lms_cached_user', '{}');
  localStorage.setItem('qa_draft', 'kept');
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 401 })));
  const api = await import('./apiClient');
  await expect(api.apiRequest('/auth/me', { skipCache: true })).rejects.toMatchObject({ status: 401 });
  expect(api.isSessionKnownInvalid()).toBe(true);
  expect(localStorage.getItem('lms_cached_user')).toBeNull();
  expect(localStorage.getItem('qa_draft')).toBe('kept');
});
