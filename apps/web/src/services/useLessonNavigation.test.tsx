import { act, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useLessonNavigation } from './useLessonNavigation';
import type { Course, VideoLesson } from '../types/lms';

const lesson = { id: 'lesson', courseId: 'course', title: 'Restored video' } as VideoLesson;
const courses = [{ id: 'course', lessons: [lesson] }] as Course[];
let host: HTMLDivElement, root: Root;
let open: (value: VideoLesson | null) => void, close: () => void;
const admit = vi.fn(), restored = vi.fn();
function Probe({ user = 'student' }: { user?: string }) {
  const [selection, setSelection] = useState<VideoLesson | null>(null);
  open = setSelection;
  close = useLessonNavigation(selection, setSelection, { userId: user, courses, onRestore: restored, canRestore: admit });
  return <div>{selection?.title || 'List'}</div>;
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  window.history.replaceState(null, '', '/#mycourses');
  admit.mockReset().mockResolvedValue(true); restored.mockReset();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('puts only course and lesson identifiers into the player URL', async () => {
  await act(async () => root.render(<Probe />));
  await act(async () => open(lesson));
  expect(window.location.hash).toBe('#mycourses?course=course&lesson=lesson');
  expect(window.history.state.lessonListHash).toBe('#mycourses');
  expect(window.location.hash).not.toContain('student');
});
it('restores from the URL after mobile history state is lost, and checks admission again', async () => {
  window.history.replaceState(null, '', '/#mycourses?course=course&lesson=lesson');
  await act(async () => root.render(<Probe />));
  expect(admit).toHaveBeenCalledWith(lesson, courses[0]);
  expect(host.textContent).toBe('Restored video');
  expect(window.history.state.lessonCanGoBack).toBe(false);
  await act(async () => close());
  expect(window.location.hash).toBe('#mycourses');
  expect(host.textContent).toBe('List');
});
it('does not restore a revoked or unpaid lesson from a saved URL', async () => {
  admit.mockResolvedValue(false);
  window.history.replaceState(null, '', '/#mycourses?course=course&lesson=lesson');
  await act(async () => root.render(<Probe />));
  expect(host.textContent).toBe('List'); expect(restored).not.toHaveBeenCalled();
});
it('ignores late admission after leaving the player URL', async () => {
  let finish!: (allowed: boolean) => void;
  admit.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  window.history.replaceState(null, '', '/#mycourses?course=course&lesson=lesson');
  await act(async () => root.render(<Probe />));
  window.history.replaceState(null, '', '/#profile');
  await act(async () => finish(true));
  expect(host.textContent).toBe('List'); expect(restored).not.toHaveBeenCalled();
});
it('does not replay another account’s saved history entry', async () => {
  window.history.replaceState({ lmsLesson: lesson.id, lessonCourse: lesson.courseId, lessonUser: 'other', lessonOrigin: '#mycourses' }, '', '/#mycourses');
  await act(async () => root.render(<Probe />));
  expect(host.textContent).toBe('List'); expect(admit).not.toHaveBeenCalled();
});
it('returns to the list on Back and rechecks admission on Forward', async () => {
  await act(async () => root.render(<Probe />));
  await act(async () => open(lesson));
  await act(async () => { window.history.back(); await new Promise(resolve => setTimeout(resolve, 30)); });
  expect(host.textContent).toBe('List');
  expect(window.location.hash).toBe('#mycourses');
  admit.mockResolvedValue(false);
  await act(async () => { window.history.forward(); await new Promise(resolve => setTimeout(resolve, 30)); });
  expect(admit).toHaveBeenCalled();
  expect(host.textContent).toBe('List');
});
