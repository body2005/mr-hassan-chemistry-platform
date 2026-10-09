import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useCourseAssessments } from './useCourseAssessments';
import type { CourseAssessmentRef } from '../types/lms';

const mocks = vi.hoisted(() => ({ read: vi.fn() }));
vi.mock('./lmsService', () => ({ courseService: { getCourseAssessmentRefs: mocks.read } }));
let root: Root, host: HTMLDivElement;
let state: ReturnType<typeof useCourseAssessments>;
function Probe({ course = 'selected', user = 'student', access = '' }: { course?: string; user?: string; access?: string }) {
  state = useCourseAssessments(course, user, access);
  return <div>{state.loading ? 'loading' : state.error ? 'error' : state.items.map(item => item.title).join(',')}</div>;
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  mocks.read.mockReset();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
const refs = (id: string): CourseAssessmentRef[] => [{ id, title: id, kind: 'quiz', accessible: true }];

it('loads only the selected course immediately, not every enrollment', async () => {
  mocks.read.mockResolvedValue(refs('published-quiz'));
  await act(async () => root.render(<Probe />));
  expect(host.textContent).toBe('published-quiz');
  expect(mocks.read).toHaveBeenCalledTimes(1);
  expect(mocks.read.mock.calls[0][0]).toBe('selected');
});
it('cancels a former course or account and ignores its late response', async () => {
  let finishOld: (items: CourseAssessmentRef[]) => void = () => {};
  mocks.read.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; }))
    .mockResolvedValueOnce(refs('new-account-quiz'));
  await act(async () => root.render(<Probe />));
  const oldSignal: AbortSignal = mocks.read.mock.calls[0][1].signal;
  await act(async () => root.render(<Probe course="other" user="other-student" />));
  expect(oldSignal.aborted).toBe(true);
  await act(async () => finishOld(refs('private-old-quiz')));
  expect(host.textContent).toBe('new-account-quiz');
});
it('preserves a failed read as an error and retries only on manual action', async () => {
  mocks.read.mockRejectedValueOnce({ status: 429 }).mockResolvedValueOnce(refs('recovered'));
  await act(async () => root.render(<Probe />));
  expect(host.textContent).toBe('error');
  await act(async () => new Promise(resolve => setTimeout(resolve, 30)));
  expect(mocks.read).toHaveBeenCalledTimes(1);
  await act(async () => state.retry());
  expect(host.textContent).toBe('recovered');
  expect(mocks.read.mock.calls[1][1].skipCache).toBe(true);
});
it('refreshes only this course after a real course/access update and cleans up listeners', async () => {
  mocks.read.mockResolvedValue(refs('initial'));
  await act(async () => root.render(<Probe />));
  mocks.read.mockResolvedValue(refs('new-access'));
  await act(async () => window.dispatchEvent(new Event('lms_lesson_unlocked')));
  expect(host.textContent).toBe('new-access');
  expect(mocks.read.mock.calls.every(call => call[0] === 'selected')).toBe(true);
  await act(async () => root.render(null));
  window.dispatchEvent(new Event('lms_lesson_unlocked'));
  expect(mocks.read).toHaveBeenCalledTimes(2);
});
it('does not replay429 on SSE reconnect, but reconciles authoritative access changes', async () => {
  mocks.read.mockRejectedValueOnce({ status: 429 }).mockResolvedValueOnce(refs('actual-access'));
  await act(async () => root.render(<Probe />));
  await act(async () => window.dispatchEvent(new CustomEvent('lms_payment_updated')));
  expect(mocks.read).toHaveBeenCalledTimes(1);
  expect(host.textContent).toBe('error');
  await act(async () => root.render(<Probe access="new-entitlement" />));
  expect(mocks.read).toHaveBeenCalledTimes(2);
  expect(host.textContent).toBe('actual-access');
});
