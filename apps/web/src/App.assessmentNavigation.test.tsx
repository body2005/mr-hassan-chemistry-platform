import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { sharedAssessmentUrl, type SharedAssessment } from './utils/sharedAssessment';
import type { Course, NotificationItem } from './types/lms';

const mocks = vi.hoisted(() => ({ bootstrap: vi.fn(), received: vi.fn(), catalogReceived: vi.fn(), cachedUser: vi.fn(), catalogPage: vi.fn() }));
vi.mock('./services/lmsService', () => ({
  ApiClientError: class extends Error {}, authService: { getCachedUser: mocks.cachedUser },
  bootstrapService: { getBootstrap: mocks.bootstrap }, courseService: { getCachedCourses: () => [], getCatalogPage: mocks.catalogPage },
  notificationService: { markAsRead: async () => [], getNotifications: async () => [] },
}));
vi.mock('./services/realtimeService', () => ({ realtimeService: { connect: () => {}, disconnect: () => {} } }));
vi.mock('./components/GlobalUploadWidget', () => ({ GlobalUploadWidget: () => null }));
vi.mock('./components/LessonAccessModal', () => ({ LessonAccessModal: () => null }));
vi.mock('./components/Sidebar', () => ({ Sidebar: () => null }));
vi.mock('./components/Header', () => ({ Header: ({ notifications, onSelectNotification }: { notifications: NotificationItem[]; onSelectNotification: (notification: NotificationItem) => void }) =>
  <button onClick={() => onSelectNotification(notifications[0])}>Open notification</button> }));
vi.mock('./views/LandingPageView', () => ({ LandingPageView: () => <p>Landing</p> }));
vi.mock('./views/AuthView', () => ({ AuthView: () => <p>Sign in</p> }));
vi.mock('./views/MyCoursesView', () => ({ MyCoursesView: (props: { initialAssessment?: SharedAssessment; onInitialAssessmentHandled: () => void; catalogCourses: Course[] }) => {
  mocks.received(props.initialAssessment);
  mocks.catalogReceived(props.catalogCourses);
  return <div><p>Courses view</p><button onClick={props.onInitialAssessmentHandled}>Handled</button></div>;
} }));
const target: SharedAssessment = { courseId: '11111111-1111-4111-8111-111111111111', assessmentId: '22222222-2222-4222-8222-222222222222', kind: 'quiz' };
const student = { id: 'student', name: 'Student', role: 'student' };
const authenticated = () => ({ authenticated: true, user: student, courses: [], notifications: [], enrolledCourseIds: [], entitlements: [] });
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); mocks.bootstrap.mockReset(); mocks.received.mockClear();
  mocks.catalogReceived.mockClear(); mocks.cachedUser.mockReset().mockReturnValue(null); mocks.catalogPage.mockReset();
  localStorage.clear(); sessionStorage.clear(); window.history.replaceState(null, '', '/#mycourses');
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });
async function render() { await act(async () => { root.render(<App />); await new Promise(resolve => setTimeout(resolve, 0)); }); }
it('passes a direct assessment target into the authenticated course view and clears it after handling', async () => {
  window.history.replaceState(null, '', sharedAssessmentUrl(target)); mocks.bootstrap.mockResolvedValue(authenticated());
  await render(); expect(mocks.received).toHaveBeenLastCalledWith(target);
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'Handled')!.click());
  expect(mocks.received).toHaveBeenLastCalledWith(undefined); expect(window.location.hash).not.toContain('assessment=');
});
it('preserves an unauthenticated assessment target through bootstrap sign-in', async () => {
  window.history.replaceState(null, '', sharedAssessmentUrl(target)); mocks.bootstrap.mockResolvedValueOnce({ authenticated: false });
  await render(); expect(host.textContent).toContain('Sign in');
  mocks.bootstrap.mockResolvedValue(authenticated());
  await act(async () => { window.dispatchEvent(new Event('lms_user_updated')); await new Promise(resolve => setTimeout(resolve, 10)); });
  expect(mocks.received).toHaveBeenLastCalledWith(target);
});
it('notification actionUrl reaches the parser even when actionTab is absent', async () => {
  mocks.bootstrap.mockResolvedValue({ ...authenticated(), notifications: [{ id: 'notice', type: 'quiz', actionUrl: sharedAssessmentUrl(target) }] });
  await render();
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'Open notification')!.click());
  expect(mocks.received).toHaveBeenLastCalledWith(target);
});
it('shows an unavailable message for a legacy or malformed assessment URL', async () => {
  window.history.replaceState(null, '', '#mycourses?assessment=missing-course&kind=quiz');
  mocks.bootstrap.mockResolvedValue(authenticated()); await render();
  expect(host.querySelector('[role="alert"]')?.textContent).toContain('هذا التقييم غير متاح');
  expect(mocks.received).toHaveBeenLastCalledWith(undefined);
});

it('keeps purchasable lessons after realtime refresh and includes older courses from later pages', async () => {
  const available = { id: 'available', lessons: [{ id: 'paid', price: 50 }] } as Course;
  const older = { id: 'older-enrollment', lessons: [] } as unknown as Course;
  mocks.cachedUser.mockReturnValue(student);
  mocks.bootstrap.mockResolvedValue({ ...authenticated(), courses: [available] });
  mocks.catalogPage.mockImplementation(async (page: number) => ({ courses: page === 1 ? [available] : [older], pages: 2 }));
  await render();
  await act(async () => { window.dispatchEvent(new Event('lms_courses_updated')); await new Promise(resolve => setTimeout(resolve, 10)); });
  expect(mocks.catalogReceived).toHaveBeenLastCalledWith([available, older]);
  expect(mocks.catalogPage.mock.calls).toEqual([[1, { skipCache: true }], [2, { skipCache: true }]]);
});
