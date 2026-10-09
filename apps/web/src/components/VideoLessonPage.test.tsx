import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { VideoLessonPage } from './VideoLessonPage';
import type { Course, TeacherProfile, VideoLesson } from '../types/lms';

const mocks = vi.hoisted(() => ({ request: vi.fn(), toast: vi.fn() }));
vi.mock('../services/apiClient', () => ({ apiRequest: mocks.request, apiUrl: (url: string) => url,
  getApiAuthGeneration: () => 0, getApiAuthScope: () => 'teacher' }));
vi.mock('./ToastProvider', () => ({ useToast: () => mocks.toast, ToastRegion: () => null }));
vi.mock('../services/videoTelemetry', () => ({
  VideoTelemetryTracker: class { attach() {} detach() {} },
}));

type Token = { stream_url: string };
const pending: Array<{ path: string; resolve: (value: Token) => void; reject: (error: Error) => void }> = [];
const lesson = (id: string): VideoLesson => ({
  id, courseId: 'course', academicYear: '1st_secondary', title: id, description: '',
  durationMinutes: 1, durationFormatted: '01:00', videoUrl: '', requiresProtectedPlayback: true,
  materials: [], uploadedByTeacherName: 'Teacher', uploadedAt: '', order: 1,
});
const course: Course = {
  id: 'course', title: 'Course', subject: 'Chemistry', academicYear: '1st_secondary',
  academicYearLabel: 'الأول الثانوي', teacherName: 'Teacher', teacherTitle: 'Teacher', description: '',
  thumbnailColor: '#059669', lessonsCount: 2, totalDurationFormatted: '02:00',
  lessons: [lesson('first'), lesson('second')], enrolledStudentsCount: 0,
};
const teacher: TeacherProfile = {
  id: 'teacher', name: 'Teacher', email: 'teacher@example.test', role: 'teacher',
  nationalId: '', phone: '', teachingYear: 'all', teachingYearLabel: '', subject: 'Chemistry',
  contractAgreed: true, joinedDate: '',
};
let host: HTMLDivElement;
let root: Root;
async function render(id: string, account = teacher) {
  await act(async () => root.render(<VideoLessonPage lesson={lesson(id)} course={course}
    currentUser={account} completedLessonIds={[]} onClose={() => {}}
    onToggleCompleteLesson={() => {}} onSelectLesson={() => {}} />));
}
async function resolve(index: number, url: string) {
  await act(async () => pending[index].resolve({ stream_url: url }));
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  mocks.request.mockReset();
  mocks.toast.mockReset();
  pending.length = 0;
  localStorage.clear();
  mocks.request.mockImplementation((path: string) => {
    if (path.endsWith('/comments')) return Promise.resolve({ comments: [] });
    if (!path.endsWith('/video-token')) throw new Error(`Unexpected request: ${path}`);
    return new Promise<Token>((resolve, reject) => pending.push({ path, resolve, reject }));
  });
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

it.each(['resolve', 'reject'] as const)('ignores a late manual renewal %s after switching lessons', async outcome => {
  await render('first');
  await resolve(0, '/first-original.mp4');
  await act(async () => host.querySelector('video')!.dispatchEvent(new Event('error')));
  expect(pending[1].path).toBe('/lessons/first/video-token');
  await render('second');
  await resolve(2, '/second.mp4');
  await act(async () => {
    if (outcome === 'resolve') pending[1].resolve({ stream_url: '/first-late.mp4' });
    else pending[1].reject(new Error('Old lesson offline'));
  });
  expect(host.querySelector('video')?.getAttribute('src')).toBe('/second.mp4');
  expect(host.textContent).not.toContain('تعذر تجديد رابط الفيديو');
});

it('ignores a late unlock response and toast after switching lessons', async () => {
  await render('first');
  await resolve(0, '/first.mp4');
  await act(async () => window.dispatchEvent(new CustomEvent('lms_lesson_unlocked', {
    detail: { lesson_id: 'first' },
  })));
  await render('second');
  await resolve(2, '/second.mp4');
  await resolve(1, '/first-unlocked.mp4');
  expect(host.querySelector('video')?.getAttribute('src')).toBe('/second.mp4');
  expect(mocks.toast).not.toHaveBeenCalled();
});

it('fetches fresh playback when the account changes on the same lesson', async () => {
  await render('first');
  await render('first', { ...teacher, id: 'another-teacher' });
  expect(pending).toHaveLength(2);
  await resolve(1, '/new-account.mp4');
  await resolve(0, '/old-account.mp4');
  expect(host.querySelector('video')?.getAttribute('src')).toBe('/new-account.mp4');
});

it('does not fabricate view counts or a publication date for missing metadata', async () => {
  await render('first');
  expect(host.textContent).not.toContain('ألف مشاهدة');
  expect(host.textContent).not.toContain('24 يناير 2024');
  expect(host.textContent).toContain('تاريخ النشر غير متاح');
});

it('uses a native keyboard-operable course breadcrumb', async () => {
  await render('first');
  const navigation = host.querySelector('nav[aria-label="Breadcrumb"]')!;
  const courseControl = [...navigation.querySelectorAll('button, [role="button"]')]
    .find(element => element.textContent === course.title)!;
  // Native button activation supports Enter and Space without pointer-only JS.
  expect(courseControl.tagName).toBe('BUTTON');
  expect(courseControl.getAttribute('type')).toBe('button');
});

it('does not position the RTL breadcrumb outside the viewport with a fixed negative offset', async () => {
  await render('first');
  const navigation = host.querySelector<HTMLElement>('nav[aria-label="Breadcrumb"]')!;
  expect(Number.parseFloat(navigation.style.marginRight) || 0).toBeGreaterThanOrEqual(0);
});

async function typeDiscussion(placeholder: string, value: string) {
  const input = host.querySelector<HTMLInputElement>(`input[placeholder="${placeholder}"]`)!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  return input;
}
async function submitDiscussion() {
  await act(async () => host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
}

it('keeps the discussion draft and reports failure when the server rejects a comment', async () => {
  const original = mocks.request.getMockImplementation()!;
  mocks.request.mockImplementation((path: string, options?: { method?: string }) => {
    if (path.endsWith('/comments') && options?.method === 'POST') return Promise.reject(new Error('Unavailable'));
    return original(path, options);
  });
  await render('first');
  const input = await typeDiscussion('اكتب سؤالك أو تعليقك حول هذا الدرس...', 'Keep my real draft');
  await submitDiscussion();
  expect(mocks.request.mock.calls.filter(([path, options]) => path.endsWith('/comments') && options?.method === 'POST')).toHaveLength(1);
  expect(input.value).toBe('Keep my real draft');
  expect(mocks.toast).not.toHaveBeenCalledWith('تم إضافة تعليقك بنجاح', 'success');
  expect(mocks.toast).toHaveBeenCalledWith('تعذر نشر التعليق، حاول مجدداً', 'danger');
});

it('uses the persisted comment UUID for replies, never an invented local ID', async () => {
  const original = mocks.request.getMockImplementation()!;
  const id = '3b111111-2222-4333-8444-555555555555';
  mocks.request.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
    if (path.endsWith('/comments') && options?.method === 'POST') {
      const payload = JSON.parse(options.body!);
      return Promise.resolve({ id: payload.parent_id ? '6b111111-2222-4333-8444-555555555555' : id,
        author: 'Actual server author', is_teacher: true, is_mine: true, body: payload.body,
        created_at: '2026-10-08T04:00:00Z', replies: [] });
    }
    return original(path, options);
  });
  await render('first');
  await typeDiscussion('اكتب سؤالك أو تعليقك حول هذا الدرس...', 'Real parent');
  await submitDiscussion();
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent?.trim() === 'رد')!.click());
  await typeDiscussion('اكتب ردك هنا...', 'Real reply');
  const replyInput = host.querySelector<HTMLInputElement>('input[placeholder="اكتب ردك هنا..."]')!;
  await act(async () => {
    const composer = replyInput.closest('form') || replyInput.parentElement!;
    composer.querySelector('button')!.click();
  });
  const posts = mocks.request.mock.calls.filter(([path, options]) => path.endsWith('/comments') && options?.method === 'POST');
  expect(posts).toHaveLength(2);
  expect(JSON.parse(posts[1][1].body)).toEqual({ body: 'Real reply', parent_id: id });
  expect(host.textContent).toContain('Actual server author');
});

it.each(['resolve', 'reject'] as const)('ignores a late discussion save %s after account/lesson change', async outcome => {
  const original = mocks.request.getMockImplementation()!;
  let release: (value: unknown) => void = () => {};
  let reject: (error: Error) => void = () => {};
  mocks.request.mockImplementation((path: string, options?: { method?: string }) => {
    if (path.endsWith('/comments') && options?.method === 'POST') {
      return new Promise((resolve, fail) => { release = resolve; reject = fail; });
    }
    return original(path, options);
  });
  await render('first');
  await typeDiscussion('اكتب سؤالك أو تعليقك حول هذا الدرس...', 'Old account private draft');
  await act(async () => host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  await render('second', { ...teacher, id: 'new-account' });
  await act(async () => {
    if (outcome === 'reject') reject(new Error('Old account failed'));
    else release({ id: '3b111111-2222-4333-8444-555555555555', author: 'Old account author',
      body: 'Old account private draft', created_at: null, is_teacher: true, replies: [] });
  });
  expect(host.textContent).not.toContain('Old account author');
  expect(host.querySelector<HTMLInputElement>('input[placeholder="اكتب سؤالك أو تعليقك حول هذا الدرس..."]')!.value).toBe('');
  expect(mocks.toast).not.toHaveBeenCalled();
});

it('admits only one comment write while the actual save remains pending', async () => {
  const original = mocks.request.getMockImplementation()!;
  mocks.request.mockImplementation((path: string, options?: { method?: string }) => {
    if (path.endsWith('/comments') && options?.method === 'POST') return new Promise(() => {});
    return original(path, options);
  });
  await render('first');
  await typeDiscussion('اكتب سؤالك أو تعليقك حول هذا الدرس...', 'One pending save');
  await act(async () => {
    const form = host.querySelector('form')!;
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
  expect(mocks.request.mock.calls.filter(([path, options]) => path.endsWith('/comments') && options?.method === 'POST')).toHaveLength(1);
  expect([...host.querySelectorAll('button')].find(button => button.textContent === 'جاري النشر...')!.disabled).toBe(true);
});

it('shows failed discussion loading rather than claiming the lesson has no comments', async () => {
  const original = mocks.request.getMockImplementation()!;
  mocks.request.mockImplementation((path: string, options?: { method?: string }) => {
    if (path.endsWith('/comments')) return Promise.reject(new Error('Temporarily unavailable'));
    return original(path, options);
  });
  await render('first');
  expect(host.querySelector('[role="alert"]')?.textContent).toContain('تعذر تحميل المناقشة');
  expect(host.textContent).not.toContain('لا توجد تعليقات');
  expect(mocks.request.mock.calls.filter(([path]) => path.endsWith('/comments'))).toHaveLength(1);
});
