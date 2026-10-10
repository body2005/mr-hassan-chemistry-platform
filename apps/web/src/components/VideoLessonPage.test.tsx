import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { VideoLessonPage } from './VideoLessonPage';
import type { Course, CurrentUser, StudentProfile, TeacherProfile, VideoLesson } from '../types/lms';

const mocks = vi.hoisted(() => ({ request: vi.fn(), toast: vi.fn(), attach: vi.fn(), detach: vi.fn() }));
vi.mock('../services/apiClient', () => ({ apiRequest: mocks.request, apiUrl: (url: string) => url,
  getApiAuthGeneration: () => 0, getApiAuthScope: () => 'teacher' }));
vi.mock('./ToastProvider', () => ({ useToast: () => mocks.toast, ToastRegion: () => null }));
vi.mock('../services/videoTelemetry', () => ({
  VideoTelemetryTracker: class { attach = mocks.attach; detach = mocks.detach; },
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
const student: StudentProfile = {
  id: 'student', name: 'Student', email: 'student@example.test', role: 'student', nationalId: '',
  studentPhone: '', guardianPhone: '', age: 16, academicYear: '1st_secondary', academicYearLabel: '',
  interestedSubjects: [], joinedDate: '',
};
async function render(id: string, account: CurrentUser = teacher) {
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
  mocks.attach.mockReset();
  mocks.detach.mockReset();
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {});
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
  vi.restoreAllMocks();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it('tracks student playback once across ordinary rerenders and never tracks management previews', async () => {
  await render('first'); await resolve(0, '/teacher.mp4');
  expect(mocks.attach).not.toHaveBeenCalled();
  await render('first', student); await resolve(1, '/student.mp4');
  expect(mocks.attach).toHaveBeenCalledTimes(1);
  await render('first', student);
  expect(mocks.attach).toHaveBeenCalledTimes(1);
  await render('first', teacher);
  expect(mocks.detach).toHaveBeenCalledTimes(1);
});

it.each(['teacher', 'institution_admin', 'platform_admin'] as const)('allows %s to seek forward and back without a student watch restriction', async role => {
  await render('first', { ...teacher, role }); await resolve(0, '/teacher.mp4');
  const video = host.querySelector('video')!;
  Object.defineProperty(video, 'duration', { configurable: true, value: 60 });
  await act(async () => video.dispatchEvent(new Event('loadedmetadata')));
  expect(host.querySelector('.lesson-seek-button')).toBeNull();
  await act(async () => host.querySelector('.lesson-video-player')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })));
  expect(video.currentTime).toBe(10);
  await act(async () => host.querySelector('.lesson-video-player')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true })));
  expect(video.currentTime).toBe(0);
  video.currentTime = 45;
  await act(async () => video.dispatchEvent(new Event('timeupdate')));
  expect(video.currentTime).toBe(45);
  expect(mocks.toast).not.toHaveBeenCalled();
});

it('preserves the student forward-seek restriction', async () => {
  await render('first', student); await resolve(0, '/student.mp4');
  const video = host.querySelector('video')!;
  video.currentTime = 45;
  await act(async () => video.dispatchEvent(new Event('timeupdate')));
  expect(video.currentTime).toBe(0);
  expect(host.querySelector('[aria-label="تقديم 10 ثواني"]')).toBeNull();
  await act(async () => host.querySelector('.lesson-video-player')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })));
  expect(video.currentTime).toBe(0);
});

it('shows actual keyboard movement on the correct side, accumulates it and clears it automatically', async () => {
  await render('first'); await resolve(0, '/teacher.mp4');
  vi.useFakeTimers();
  const video = host.querySelector('video')!;
  Object.defineProperty(video, 'duration', {configurable:true, value:60});
  await act(async () => video.dispatchEvent(new Event('loadedmetadata')));
  const press = async (key: string) => act(async () => host.querySelector('.lesson-video-player')!
    .dispatchEvent(new KeyboardEvent('keydown', {key, bubbles:true})));
  await press('ArrowRight'); await press('ArrowRight');
  expect(video.currentTime).toBe(20); // One seek per key, not two handlers.
  expect(host.querySelector('.lesson-seek-feedback-forward')?.textContent).toContain('+20');
  await press('ArrowLeft');
  expect(host.querySelector('.lesson-seek-feedback-forward')).toBeNull();
  expect(host.querySelector('.lesson-seek-feedback-backward')?.textContent).toContain('−10');
  await act(async () => vi.advanceTimersByTime(800));
  expect(host.querySelector('.lesson-seek-feedback')).toBeNull();
  video.currentTime = 58;
  await press('ArrowRight');
  expect(host.querySelector('.lesson-seek-feedback-forward')?.textContent).toContain('+2');
  await press('ArrowRight');
  expect(video.currentTime).toBe(60);
  expect(host.querySelector('.lesson-seek-feedback-forward')?.textContent).toContain('+2');
  await act(async () => vi.advanceTimersByTime(800));
  video.currentTime = 3;
  await press('ArrowLeft');
  expect(host.querySelector('.lesson-seek-feedback-backward')?.textContent).toContain('−3');
});

it.each(['input', 'textarea'] as const)('leaves arrow keys in a %s to the editor', async tag => {
  await render('first'); await resolve(0, '/teacher.mp4');
  const player = host.querySelector('.lesson-video-player')!;
  const editor = document.createElement(tag);
  player.append(editor);
  const key = new KeyboardEvent('keydown', {key:'ArrowRight', bubbles:true, cancelable:true});
  await act(async () => editor.dispatchEvent(key));
  expect(key.defaultPrevented).toBe(false);
  expect(host.querySelector('video')!.currentTime).toBe(0);
  expect(host.querySelector('.lesson-seek-feedback')).toBeNull();
});

it('never claims a student skipped into unwatched content', async () => {
  await render('first', student); await resolve(0, '/student.mp4');
  const video = host.querySelector('video')!;
  Object.defineProperty(video, 'duration', {configurable:true, value:60});
  await act(async () => video.dispatchEvent(new Event('loadedmetadata')));
  await act(async () => host.querySelector('.lesson-video-player')!
    .dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowRight', bubbles:true})));
  expect(video.currentTime).toBe(0);
  expect(host.querySelector('.lesson-seek-feedback')).toBeNull();
});

it('updates an initially unknown WebM duration when the browser discovers its end', async () => {
  await render('first'); await resolve(0, '/recorded.webm');
  const video = host.querySelector('video')!;
  Object.defineProperty(video, 'duration', { configurable: true, value: Infinity });
  await act(async () => video.dispatchEvent(new Event('loadedmetadata')));
  expect(host.textContent).not.toContain('Infinity');
  Object.defineProperty(video, 'duration', { configurable: true, value: 20 });
  await act(async () => video.dispatchEvent(new Event('durationchange')));
  await act(async () => host.querySelector('.lesson-video-player')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })));
  expect(video.currentTime).toBe(10);
  expect(host.textContent).toContain('00:20');
});

it('does not intercept arrow keys in inputs or outside the player and clamps keyboard seeking', async () => {
  await render('first'); await resolve(0, '/teacher.mp4');
  const video = host.querySelector('video')!;
  Object.defineProperty(video, 'duration', { configurable: true, value: 15 });
  await act(async () => video.dispatchEvent(new Event('loadedmetadata')));
  const player = host.querySelector('.lesson-video-player')!;
  const range = player.querySelector('input')!;
  const nativeArrow = new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true });
  await act(async () => range.dispatchEvent(nativeArrow));
  expect(nativeArrow.defaultPrevented).toBe(false);
  await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })));
  expect(video.currentTime).toBe(0);
  for (const key of ['ArrowRight', 'ArrowRight']) {
    await act(async () => player.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true })));
  }
  expect(video.currentTime).toBe(15);
  for (const key of ['ArrowLeft', 'ArrowLeft']) {
    await act(async () => player.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true })));
  }
  expect(video.currentTime).toBe(0);
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

it('shows an access denial rather than a missing-upload message when admission rejects playback', async () => {
  await render('locked-paid-video');
  await act(async () => pending[0].reject(Object.assign(new Error('Lesson not unlocked'), { status: 403 })));
  expect(host.textContent).toContain('لا تملك صلاحية مشاهدة هذا الدرس');
  expect(host.textContent).not.toContain('لا يوجد فيديو جاهز');
  expect(host.querySelector('video')).toBeNull();
  expect(pending).toHaveLength(1);
});

it('honors Retry-After and stops automatic token retries after a rate-limit response', async () => {
  await render('first');
  await resolve(0, '/first.mp4');
  await act(async () => host.querySelector('video')!.dispatchEvent(new Event('error')));
  await act(async () => pending[1].reject(Object.assign(new Error('Limit'), { status: 429, retryAfterMs: 60000 })));
  expect(host.querySelector('.lesson-playback-error')).toBeNull();
  expect(host.textContent).not.toContain('طلبات كثيرة');
  await act(async () => {
    host.querySelector('video')!.dispatchEvent(new Event('error'));
    [...host.querySelectorAll('button')].find(button => button.textContent?.trim() === 'استئناف الفيديو')!.click();
  });
  expect(pending).toHaveLength(2);
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
