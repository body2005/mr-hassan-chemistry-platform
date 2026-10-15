import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MyCoursesView } from './MyCoursesView';
import type { Course, StudentProfile } from '../types/lms';

const mocks = vi.hoisted(() => ({ progress: vi.fn(), toast: vi.fn() }));
vi.mock('../services/lmsService', () => ({ courseService: { getLessonProgress: mocks.progress } }));
vi.mock('../services/paymentService', () => ({ lessonAccessService: { getMyRequests: async () => [] } }));
vi.mock('../services/useCourseAssessments', () => ({ useCourseAssessments: () => ({ items: [], loading: false, error: false, restricted: false, retry: () => {} }) }));
vi.mock('../components/ToastProvider', () => ({ useToast: () => mocks.toast, ToastRegion: () => null }));
vi.mock('../components/VideoLessonPage', () => ({ VideoLessonPage: ({ onClose }: { onClose: () => void }) => <button onClick={onClose}>Close video</button> }));
const course: Course = {
  id: 'course', title: 'Chemistry', subject: 'Chemistry', academicYear: '1st_secondary', academicYearLabel: '',
  teacherName: '', teacherTitle: '', description: '', thumbnailColor: '', lessonsCount: 1, totalDurationFormatted: '',
  enrolledStudentsCount: 0, lessons: [{ id: 'lesson', courseId: 'course', title: 'Video lesson', description: '',
    academicYear: '1st_secondary', durationMinutes: 10, durationFormatted: '10:00', videoUrl: '', materials: [],
    uploadedByTeacherName: '', uploadedAt: '', order: 1, price: 0 }],
};
const student = { id: 'one', role: 'student', name: 'Student', academicYear: '1st_secondary' } as StudentProfile;
let host: HTMLDivElement, root: Root;
async function render(user = student) {
  await act(async () => root.render(<MyCoursesView enrolledCourses={[course]} currentUser={user} lang="ar"
    onNavigateToCatalog={() => {}} onCheckout={() => {}} />));
}
const rows = (percent: number) => [{ lesson_id: 'lesson', completion_percent: percent }];
const progress = () => host.querySelector('.lesson-card-watch-progress [role="progressbar"]');
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  window.history.replaceState(null, '', '/#mycourses'); localStorage.clear();
  mocks.progress.mockReset();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it('shows saved watch percentage on the lesson card and refreshes after a saved telemetry batch', async () => {
  mocks.progress.mockResolvedValueOnce(rows(24.6)).mockResolvedValueOnce(rows(38));
  await render();
  expect(progress()?.getAttribute('aria-valuenow')).toBe('25');
  await act(async () => window.dispatchEvent(new Event('lms_video_progress_updated')));
  expect(progress()?.getAttribute('aria-valuenow')).toBe('38');
  expect(mocks.progress.mock.calls.every(call => call[0].skipCache)).toBe(true);
});
it('does not display fake zero progress during loading or an API failure', async () => {
  let fail!: (error: Error) => void;
  mocks.progress.mockImplementation(() => new Promise((_resolve, reject) => { fail = reject; }));
  await render(); expect(progress()).toBeNull();
  expect(host.textContent).toContain('جارٍ تحميل تقدم المشاهدة');
  await act(async () => fail(new Error('offline')));
  expect(progress()).toBeNull(); expect(host.textContent).toContain('تعذر تحميل تقدم المشاهدة');
});
it('ignores a former account’s late progress response', async () => {
  let finish!: (value: ReturnType<typeof rows>) => void;
  mocks.progress.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }))
    .mockResolvedValueOnce(rows(3));
  await render(); await render({ ...student, id: 'two' });
  await act(async () => finish(rows(95)));
  expect(progress()?.getAttribute('aria-valuenow')).toBe('3');
});
it('refreshes saved progress after closing the lesson without a page reload', async () => {
  mocks.progress.mockResolvedValueOnce(rows(10)).mockResolvedValueOnce(rows(20));
  await render();
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'مشاهدة الدرس')!.click());
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'Close video')!.click());
  await act(async () => new Promise(resolve => setTimeout(resolve, 30)));
  expect(progress()?.getAttribute('aria-valuenow')).toBe('20');
});
