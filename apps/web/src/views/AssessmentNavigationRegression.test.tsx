import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MyCoursesView } from './MyCoursesView';
import type { Course, CourseAssessmentRef, StudentProfile } from '../types/lms';

const mocks = vi.hoisted(() => ({ request: vi.fn(), refs: vi.fn(), toast: vi.fn() }));
vi.mock('../services/lmsService', () => ({ courseService: { getLessonProgress: async () => [], getCourseAssessmentRefs: mocks.refs } }));
vi.mock('../services/apiClient', () => ({ apiRequest: mocks.request, fetchApiBlob: vi.fn(), getApiAuthGeneration: () => 0 }));
vi.mock('../services/paymentService', () => ({ lessonAccessService: { getMyRequests: async () => [] } }));
vi.mock('../services/useCourseAssessments', () => ({ useCourseAssessments: () => ({ items: assessments, loading: false, error: false, restricted: false, retry: () => {} }) }));
vi.mock('../components/ToastProvider', () => ({ useToast: () => mocks.toast, ToastRegion: () => null }));
vi.mock('../components/LessonDiscussionBell', () => ({ LessonDiscussionBell: () => null }));
const assessments = [
  { id: 'quiz', title: 'Slow Exam', kind: 'quiz', accessible: true },
  { id: 'assignment', title: 'Slow assignment', kind: 'assignment', accessible: true },
] as CourseAssessmentRef[];
const course = { id: 'course', title: 'Chemistry', academicYear: '1st_secondary', lessons: [] } as unknown as Course;
const second = { ...course, id: 'second', title: 'Second course' };
const student = { id: 'one', role: 'student', name: 'Student', academicYear: '1st_secondary' } as StudentProfile;
let host: HTMLDivElement, root: Root;
const quizResponse = (title: string) => ({ server_time: new Date().toISOString(), quiz: { id: 'quiz', title, duration_seconds: 600, total_points: 1 }, attempt: null, questions: [] });
async function click(text: string) {
  const button = [...host.querySelectorAll('button')].find(el => el.textContent?.trim() === text);
  expect(button, text).toBeDefined(); await act(async () => button!.click());
}
async function render(extra = {}, user = student) {
  await act(async () => root.render(<MyCoursesView enrolledCourses={[course, second]} currentUser={user} lang="ar"
    onNavigateToCatalog={() => {}} onCheckout={() => {}} {...extra} />));
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  window.history.replaceState(null, '', '/#mycourses'); localStorage.clear();
  mocks.request.mockReset(); mocks.refs.mockReset(); mocks.toast.mockReset();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it('closes a pending quiz immediately and ignores the late response', async () => {
  let finish!: (value: unknown) => void;
  mocks.request.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await render(); await click('الامتحانات'); await click('بدء حل الاختبار');
  expect(host.textContent).toContain('جاري تحميل أسئلة الاختبار'); await click('خروج');
  expect(host.textContent).not.toContain('جاري تحميل أسئلة الاختبار');
  await act(async () => finish(quizResponse('Late quiz')));
  expect(host.textContent).not.toContain('Late quiz');
});
it('closes a pending assignment immediately and ignores its late failure', async () => {
  let fail!: (error: Error) => void;
  mocks.request.mockImplementation(() => new Promise((_resolve, reject) => { fail = reject; }));
  await render(); await click('الواجبات والتكليفات'); await click('فتح الواجب وتسليم الحل'); await click('خروج');
  expect(host.textContent).not.toContain('جاري تحميل الواجب');
  await act(async () => fail(new Error('Late assignment failure')));
  expect(host.textContent).not.toContain('Late assignment failure');
});
it('does not let an older quiz completion clear a reopened quiz loader', async () => {
  const finishes: Array<(value: unknown) => void> = [];
  mocks.request.mockImplementation(() => new Promise(resolve => { finishes.push(resolve); }));
  await render(); await click('الامتحانات'); await click('بدء حل الاختبار'); await click('خروج');
  await click('بدء حل الاختبار');
  await act(async () => finishes[0](quizResponse('Old quiz')));
  expect(host.textContent).toContain('جاري تحميل أسئلة الاختبار'); expect(host.textContent).not.toContain('Old quiz');
  await act(async () => finishes[1](quizResponse('Current quiz')));
  expect(host.textContent).toContain('Current quiz');
});
it('checks the precise assessment in a nonfirst course without starting an attempt', async () => {
  let admit!: (value: CourseAssessmentRef[]) => void;
  mocks.refs.mockImplementation(() => new Promise(resolve => { admit = resolve; }));
  const handled = vi.fn();
  await render({ initialAssessment: { courseId: 'second', assessmentId: 'quiz', kind: 'quiz' }, onInitialAssessmentHandled: handled });
  expect(mocks.refs).toHaveBeenCalledWith('second', expect.objectContaining({ skipCache: true }));
  expect(mocks.request).not.toHaveBeenCalled();
  await act(async () => admit(assessments));
  expect(host.textContent).toContain('Second course'); expect(host.textContent).toContain('Slow Exam');
  expect(mocks.request).not.toHaveBeenCalled(); expect(handled).toHaveBeenCalled();
});
