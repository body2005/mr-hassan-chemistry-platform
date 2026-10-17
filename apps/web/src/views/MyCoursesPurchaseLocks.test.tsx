import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MyCoursesView } from './MyCoursesView';
import { ToastProvider } from '../components/ToastProvider';
import type { Course, StudentProfile } from '../types/lms';

const mocks = vi.hoisted(() => ({ refs: vi.fn(), request: vi.fn(), checkout: vi.fn() }));
vi.mock('../services/lmsService', () => ({ courseService: {
  getCourseAssessmentRefs: mocks.refs, getLessonProgress: async () => [],
} }));
vi.mock('../services/paymentService', () => ({ lessonAccessService: { getMyRequests: async () => [], requestAccess: mocks.request } }));
vi.mock('../components/FloatingProgressFab', () => ({ FloatingProgressFab: () => null }));
const student = { id: 'student', role: 'student', academicYear: '1st_secondary' } as StudentProfile;
const course = { id: 'course', status: 'published', title: 'Chemistry course', academicYear: '1st_secondary', price: 0,
  lessons: [{ id: 'paid', courseId: 'course', title: 'Paid lecture', price: 50, materials: [], uploadedAt: '', order: 1 }],
  assessments: [
    { id: 'exam', kind: 'quiz', title: 'Linked exam', lessonId: 'paid', lessonIds: ['free', 'paid'], accessible: false, catalogOnly: true, requiresPurchase: true },
    { id: 'homework', kind: 'assignment', title: 'Linked homework', lessonId: 'paid', lessonIds: ['free', 'paid'], accessible: false, catalogOnly: true, requiresPurchase: true },
  ],
} as unknown as Course;
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); mocks.refs.mockReset(); mocks.checkout.mockClear(); mocks.request.mockReset();
  localStorage.clear(); sessionStorage.clear(); window.history.replaceState(null, '', '/#mycourses');
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function render() {
  await act(async () => root.render(<ToastProvider><MyCoursesView enrolledCourses={[course]} enrolledCourseIds={[]}
    currentUser={student} lang="ar" onCheckout={mocks.checkout} onNavigateToCatalog={vi.fn()} /></ToastProvider>));
}
async function tab(text: string) {
  const button = [...host.querySelectorAll('button')].find(button => button.textContent?.includes(text));
  expect(button).toBeDefined(); await act(async () => button!.click());
}
it('shows the locked lesson inside its course before any purchase without opening the player', async () => {
  await render();
  expect(host.textContent).toContain('Chemistry course'); expect(host.textContent).toContain('Paid lecture');
  expect(host.textContent).not.toContain('دروس صفك المتاحة للشراء');
  expect(host.querySelector('video')).toBeNull();
  expect(mocks.refs).not.toHaveBeenCalled();
});
it('shows the linked exam as a lock and chooses a missing paid lesson, never the free one', async () => {
  await render(); await tab('الامتحانات');
  expect(host.textContent).toContain('Linked exam');
  await tab('اشترِ الدرس');
  expect(mocks.checkout).toHaveBeenCalledWith({ productType: 'lesson', productId: 'paid' });
  expect(mocks.refs).not.toHaveBeenCalled(); expect(mocks.request).not.toHaveBeenCalled();
});
it('shows linked homework with the same paid-content lock', async () => {
  await render(); await tab('الواجبات');
  expect(host.textContent).toContain('Linked homework');
  await tab('اشترِ الدرس');
  expect(mocks.checkout).toHaveBeenCalledWith({ productType: 'lesson', productId: 'paid' });
});
