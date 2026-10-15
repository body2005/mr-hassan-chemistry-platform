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
  await vi.waitFor(() => expect(resolve).toBeTypeOf('function'));
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

it('maps each lesson upload date without substituting the course update date', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ authenticated: true, user: {
    id: 'teacher', role: 'teacher', display_name: 'Teacher', email: 'teacher@example.test',
    created_at: '2026-10-01T00:00:00Z', institution_id: 'school', username: 'teacher',
  }, courses: [{ id: 'course', code: 'chemistry', title: 'Chemistry', description: '', status: 'published', price_egp: 0,
    created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-15T00:00:00Z',
    modules: [{ id: 'unit', title: 'Unit', position: 1, lessons: [
      { id: 'dated', title: 'Dated', kind: 'video', position: 1, content: '', video_duration_seconds: 60,
        uploaded_at: '2026-10-12T00:00:00Z' },
      { id: 'legacy', title: 'Legacy', kind: 'video', position: 2, content: '', video_duration_seconds: 60 },
    ] }],
  }], notifications: [], enrolled_course_ids: [], entitlements: [], settings: {} }), {
    status: 200, headers: { 'Content-Type': 'application/json' },
  })));
  try {
    const result = await bootstrapService.getBootstrap();
    expect(result.courses[0].lessons.map(lesson => lesson.uploadedAt)).toEqual(['2026-10-12T00:00:00Z', '']);
  } finally { vi.unstubAllGlobals(); }
});
