import { afterEach, beforeEach, expect, it, vi } from 'vitest';

beforeEach(() => { vi.resetModules(); localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());

it('keeps redacted native videos eligible for server admission without inventing an upload or a playback URL', async () => {
  const lessons = [
    { id: 'locked', kind: 'video', has_video: false, video_url: null, price_egp: 50 },
    { id: 'article', kind: 'article', has_video: false, video_url: null },
    { id: 'native', kind: 'video', has_video: true, video_url: '/api/v1/lessons/native/video-token' },
    { id: 'external-manager-preview', kind: 'video', has_video: true, video_url: 'https://example.test/preview.mp4' },
  ].map((item, index) => ({ ...item, title: item.id, position: index + 1, content: null,
    video_duration_seconds: 60, materials: [] }));
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    items: [{ id: 'course', code: 'CHEM', title: 'Chemistry', grade_level: 'SECONDARY_1',
      status: 'published', price_egp: 0, modules: [{ id: 'module', title: 'Unit', position: 1, lessons }] }],
    pagination: { pages: 1 },
  }), { status: 200 })));
  const { courseService } = await import('./lmsService');
  const { courses } = await courseService.getCatalogPage(1);
  const [locked, article, native, external] = courses[0].lessons;
  expect(locked.requiresProtectedPlayback).toBe(true);
  expect(locked.videoUrl).toBe('');
  expect(locked.hasUploadedVideo).toBe(false);
  expect(article.requiresProtectedPlayback).toBe(false);
  expect(native.requiresProtectedPlayback).toBe(true);
  expect(external.requiresProtectedPlayback).toBe(false);
  expect(external.videoUrl).toBe('https://example.test/preview.mp4');
});
