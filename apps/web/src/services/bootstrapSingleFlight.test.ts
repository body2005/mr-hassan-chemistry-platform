import { beforeEach, expect, it, vi } from 'vitest';
import { bootstrapService } from './lmsService';
import { clearApiCache, setApiAuthScope } from './apiClient';

beforeEach(() => { clearApiCache(); setApiAuthScope(`bootstrap-test-${Math.random()}`); localStorage.clear(); });

it('shares the entire bootstrap mapping so concurrent callers do not cancel each other', async () => {
  let resolve!: (value: Response) => void;
  const fetch = vi.fn(() => new Promise<Response>(done => { resolve = done; }));
  vi.stubGlobal('fetch', fetch);
  const first = bootstrapService.getBootstrap();
  const second = bootstrapService.getBootstrap();
  expect(second).toBe(first);
  resolve(new Response(JSON.stringify({ authenticated: true, user: {
    id: 'teacher', role: 'teacher', display_name: 'Teacher', email: 'teacher@example.com',
    created_at: '2026-10-12T00:00:00Z', institution_id: 'school', username: 'teacher',
  }, courses: [], notifications: [], enrolled_course_ids: [], entitlements: [], settings: {} }), {
    status: 200, headers: { 'Content-Type': 'application/json' },
  }));
  const result = await Promise.all([first, second]);
  expect(result[0].user?.id).toBe('teacher');
  expect(result[1]).toBe(result[0]);
  expect(fetch).toHaveBeenCalledTimes(1);
  vi.unstubAllGlobals();
});
