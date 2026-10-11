import { afterEach, expect, it, vi } from 'vitest';
afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); localStorage.clear(); });
it('removes legacy session tokens and uses only cookies for login, reads and refresh', async () => {
  localStorage.setItem('lms_session_token', 'legacy-secret');
  let reads = 0;
  const calls: RequestInit[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    calls.push(init);
    if (url.endsWith('/auth/login') || url.endsWith('/auth/refresh')) return new Response(JSON.stringify({ token: 'must-not-persist' }), {status: 200});
    return new Response('{}', { status: ++reads === 1 ? 401 : 200 });
  }));
  const { apiRequest } = await import('./apiClient');
  await apiRequest('/auth/login', {method: 'POST', body:'{}'});
  await apiRequest('/auth/me', {skipCache:true});
  expect(localStorage.getItem('lms_session_token')).toBeNull();
  expect(calls).toHaveLength(4);
  for (const init of calls) {
    expect(init.credentials).toBe('include');
    expect(new Headers(init.headers).has('Authorization')).toBe(false);
  }
});
