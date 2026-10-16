import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LessonManagementView } from './LessonManagementView';
import type { Course, CurrentUser } from '../types/lms';
import type { UploadTask } from '../services/uploadManager';

const mocks = vi.hoisted(() => ({ tasks: [] as UploadTask[], listener: undefined as ((tasks: UploadTask[]) => void) | undefined,
  getCourses: vi.fn(), open: vi.fn(), unsubscribe: vi.fn() }));
vi.mock('../services/uploadManager', () => ({ uploadManager: {
  getTasks: () => mocks.tasks,
  subscribe: (listener: (tasks: UploadTask[]) => void) => { mocks.listener = listener; listener(mocks.tasks); return mocks.unsubscribe; },
} }));
vi.mock('../services/apiClient', () => ({ getApiAuthScope: () => 'teacher', fetchApiBlob: vi.fn() }));
vi.mock('../services/lmsService', () => ({ courseService: { getCourses: mocks.getCourses, getCourseContent: async () => ({ modules: [] }) } }));
vi.mock('../components/ConfirmWizard', () => ({ useConfirm: () => vi.fn() }));
vi.mock('../components/ToastProvider', () => ({ useToast: () => vi.fn() }));
vi.mock('../utils/i18nContext', () => ({ useTranslation: () => ({ lang: 'ar' }) }));
vi.mock('../utils/exportEngine', () => ({ exportToDocx: vi.fn(), exportToExcel: vi.fn(), exportToPrintPdf: vi.fn() }));
vi.mock('../components/VideoLessonPage', () => ({ VideoLessonPage: () => { mocks.open(); return <div>مشغل اختبار</div>; } }));

const teacher = { id: 'teacher', role: 'teacher' } as CurrentUser;
const course = { id: 'course', title: 'الكيمياء', academicYear: '1st_secondary', lessons: [
  { id: 'lesson', courseId: 'course', title: 'بنية الذرة', videoUrl: '/protected', hasUploadedVideo: true, materials: [] },
] } as unknown as Course;
const task = { id: 'task', lessonId: 'lesson', ownerScope: 'teacher', type: 'lesson_video', createdAt: Date.now(),
  uploadPercent: 42, status: 'uploading' } as UploadTask;
let host: HTMLDivElement;
let root: Root;
const onCoursesChanged = vi.fn();
async function render(courses = [course]) {
  await act(async () => root.render(<LessonManagementView currentUser={teacher} courses={courses} onCoursesChanged={onCoursesChanged} />));
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  window.history.replaceState(null, '', '/');
  mocks.tasks = []; mocks.open.mockClear(); mocks.getCourses.mockReset(); mocks.unsubscribe.mockClear();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.useRealTimers();
});

it('lists newest lessons first across courses and units', async () => {
  const older = { ...course.lessons[0], id: 'older', title: 'Older upload', uploadedAt: '2026-10-01T12:00:00Z', order: 99, moduleId: 'unit-two' };
  const newer = { ...course.lessons[0], id: 'newer', title: 'Newer upload', uploadedAt: '2026-10-15T12:00:00Z', order: 1, moduleId: 'unit-one' };
  const middle = { ...older, id: 'middle', title: 'Middle upload', uploadedAt: '2026-10-10T12:00:00Z', courseId: 'another-course' };
  await render([{ ...course, lessons: [newer, older] }, { ...course, id: 'another-course', lessons: [middle] }]);
  const headings = [...host.querySelectorAll('h3')].map(heading => heading.textContent);
  expect(headings.indexOf('Newer upload')).toBeGreaterThan(-1);
  expect(headings.indexOf('Newer upload')).toBeLessThan(headings.indexOf('Middle upload'));
  expect(headings.indexOf('Middle upload')).toBeLessThan(headings.indexOf('Older upload'));
});

it('shows one unified progress bar and restores watch only after processing completes', async () => {
  mocks.tasks = [task]; await render();
  expect(host.textContent).toContain('جاري رفع الفيديو…');
  expect(host.textContent).toContain('4٪');
  expect(host.textContent).not.toContain('مشاهدة الدرس');
  expect(host.textContent).not.toContain('تجهيز الجودات');
  expect(host.querySelectorAll('[role="progressbar"]')).toHaveLength(1);
  expect(host.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')).toBe('4');
  await act(async () => host.querySelector<HTMLElement>('[title="جاري رفع الفيديو…"]')!.click());
  expect(mocks.open).not.toHaveBeenCalled();
  await act(async () => mocks.listener!([{ ...task, status: 'processing', uploadPercent: 100 }]));
  expect(host.querySelectorAll('[role="progressbar"]')).toHaveLength(1);
  expect(host.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')).toBe('10');
  expect(host.textContent).not.toContain('مشاهدة الدرس');
  await act(async () => mocks.listener!([{ ...task, status: 'completed', uploadPercent: 100 }]));
  const watch = [...host.querySelectorAll('button')].find(button => button.textContent === 'مشاهدة الدرس')!;
  expect(watch).toBeDefined();
  await act(async () => watch.click()); expect(mocks.open).toHaveBeenCalled();
});

it('recovers a server processing job after reload and refreshes readiness without a manual prepare button', async () => {
  vi.useFakeTimers();
  mocks.getCourses.mockResolvedValue([course]);
  const pending = { ...course, lessons: [{ ...course.lessons[0], videoUpload: { id: 'job', status: 'processing', createdAt: new Date().toISOString() } }] };
  await render([pending]);
  expect(host.textContent).not.toContain('مشاهدة الدرس');
  await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
  expect(mocks.getCourses).toHaveBeenCalledWith({ skipCache: true });
  expect(host.textContent).toContain('مشاهدة الدرس');
});
