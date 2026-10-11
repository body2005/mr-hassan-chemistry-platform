import { beforeEach, afterEach, expect, it, vi } from 'vitest';

beforeEach(() => { vi.resetModules(); document.cookie = 'matgar_csrf=test-token; path=/'; });
afterEach(() => { vi.unstubAllGlobals(); document.cookie = 'matgar_csrf=; Max-Age=0; path=/'; });

it('reports a failed publish once with the server reason but keeps read probes quiet', async () => {
  const listener = vi.fn();
  const { subscribeToRequestErrors } = await import('./errorFeedback');
  const unsubscribe = subscribeToRequestErrors(listener);
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'أضف سؤالًا واحدًا قبل النشر.' }), { status: 400 })));
  const { apiRequest } = await import('./apiClient');
  await expect(apiRequest('/quizzes/q/publish-draft', { method: 'POST', body: '{}' })).rejects.toThrow('أضف سؤالًا');
  expect(listener).toHaveBeenCalledExactlyOnceWith('أضف سؤالًا واحدًا قبل النشر.');
  listener.mockClear();
  await expect(apiRequest('/auth/features', { skipCache: true })).rejects.toThrow();
  expect(listener).not.toHaveBeenCalled();
  unsubscribe();
});

it('does not report intentional cancellations or logout requests', async () => {
  const listener = vi.fn();
  const { subscribeToRequestErrors, reportRequestError } = await import('./errorFeedback');
  const unsubscribe = subscribeToRequestErrors(listener);
  reportRequestError(Object.assign(new Error('Cancelled'), { code: 'REQUEST_CANCELLED' }));
  reportRequestError(Object.assign(new Error('Cancelled'), { code: 'ABORTED' }));
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 503 })));
  const { apiRequest } = await import('./apiClient');
  await expect(apiRequest('/auth/logout', { method: 'POST' })).rejects.toThrow();
  expect(listener).not.toHaveBeenCalled();
  unsubscribe();
});
