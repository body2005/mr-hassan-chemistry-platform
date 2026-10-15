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
  expect(host.querySelector('select')?.value).toBe('second');
  await click('فتح التقييم');
  expect(mocks.request).toHaveBeenCalledWith('/quizzes/quiz/solve', expect.anything());
});
it.each(['quiz', 'assignment'] as const)('ignores a former account’s late %s solve response', async kind => {
  let finish!: (value: unknown) => void;
  mocks.request.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await render(); await click(kind === 'quiz' ? 'الامتحانات' : 'الواجبات والتكليفات');
  await click(kind === 'quiz' ? 'بدء حل الاختبار' : 'فتح الواجب وتسليم الحل');
  await render({}, { ...student, id: 'two' });
  await act(async () => finish(kind === 'quiz' ? quizResponse('Former account quiz') : { id: 'assignment', title: 'Former account assignment' }));
  expect(host.textContent).not.toContain('Former account');
  expect(host.textContent).not.toContain('جاري تحميل أسئلة الاختبار');
  expect(host.textContent).not.toContain('جاري تحميل الواجب');
});
it('ignores an older quiz error and finally after another solve opens', async () => {
  let rejectOld!: (error: Error) => void;
  mocks.request.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectOld = reject; }))
    .mockResolvedValueOnce(quizResponse('Current quiz'));
  await render(); await click('الامتحانات'); await click('بدء حل الاختبار'); await click('خروج'); await click('بدء حل الاختبار');
  await act(async () => rejectOld(new Error('Stale error')));
  expect(host.textContent).toContain('Current quiz'); expect(host.textContent).not.toContain('Stale error');
});
it.each(['deleted', 'restricted', 'scheduled', 'closed'] as const)('does not open a %s assessment from a link', async state => {
  mocks.refs.mockResolvedValue(state === 'deleted' ? [] : [{ ...assessments[0], accessible: state !== 'restricted', availabilityState: state === 'scheduled' || state === 'closed' ? state : 'open' }]);
  const handled = vi.fn();
  await render({ initialAssessment: { courseId: 'second', assessmentId: 'quiz', kind: 'quiz' }, onInitialAssessmentHandled: handled });
  expect(host.querySelector('[role="region"][aria-label="Slow Exam"]')).toBeNull();
  expect(mocks.request).not.toHaveBeenCalled(); expect(handled).toHaveBeenCalled();
  expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ tone: 'warning' }));
});
it('does not apply an old notification response after switching accounts', async () => {
  let finish!: (value: CourseAssessmentRef[]) => void;
  mocks.refs.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; })).mockResolvedValueOnce([]);
  const target = { initialAssessment: { courseId: 'second', assessmentId: 'quiz', kind: 'quiz' } };
  await render(target); await render(target, { ...student, id: 'two' });
  await act(async () => finish(assessments));
  expect(host.querySelector('[role="region"][aria-label="Slow Exam"]')).toBeNull(); expect(mocks.request).not.toHaveBeenCalled();
});
it('handles failed admission without loading a solve or starting an attempt', async () => {
  mocks.refs.mockRejectedValue(new Error('offline'));
  await render({ initialAssessment: { courseId: 'second', assessmentId: 'quiz', kind: 'quiz' } });
  expect(mocks.request).not.toHaveBeenCalled();
  expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ tone: 'danger' }));
});
it('selects the assignment tab for a linked assignment and waits for an explicit open', async () => {
  mocks.refs.mockResolvedValue(assessments);
  await render({ initialAssessment: { courseId: 'second', assessmentId: 'assignment', kind: 'assignment' } });
  expect(host.querySelector('[role="region"][aria-label="Slow assignment"]')).not.toBeNull();
  expect(host.querySelector('select')?.value).toBe('second');
  expect(mocks.request).not.toHaveBeenCalled();
  await click('فتح التقييم');
  expect(mocks.request).toHaveBeenCalledWith('/assignments/assignment/solve');
});
it('rejects a target outside the account catalog without any assessment request', async () => {
  await render({ initialAssessment: { courseId: 'unrelated', assessmentId: 'quiz', kind: 'quiz' } });
  expect(mocks.refs).not.toHaveBeenCalled(); expect(mocks.request).not.toHaveBeenCalled();
  expect(host.textContent).not.toContain('جارٍ التحقق من إتاحة التقييم');
  expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ tone: 'warning' }));
});
