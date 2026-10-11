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
  mocks.tasks = []; mocks.open.mockClear(); mocks.getCourses.mockReset(); mocks.unsubscribe.mockClear();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.useRealTimers();
});

it('replaces watch with byte progress, prevents opening the card, and restores watch only after processing completes', async () => {
  mocks.tasks = [task]; await render();
  expect(host.textContent).toContain('جارٍ رفع الفيديو 42٪');
  expect(host.textContent).not.toContain('مشاهدة الدرس');
  expect(host.textContent).not.toContain('تجهيز الجودات');
  expect(host.querySelector('progress')?.value).toBe(42);
  await act(async () => host.querySelector<HTMLElement>('[title="جارٍ رفع الفيديو 42٪"]')!.click());
  expect(mocks.open).not.toHaveBeenCalled();
  await act(async () => mocks.listener!([{ ...task, status: 'processing', uploadPercent: 100 }]));
  expect(host.querySelector('progress')?.hasAttribute('value')).toBe(false);
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
