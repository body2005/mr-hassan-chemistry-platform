import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { FloatingProgressFab } from './FloatingProgressFab';
import type { Course, CurrentUser } from '../types/lms';

let root: Root, host: HTMLDivElement;
const user = { id: 'student', role: 'student' } as CurrentUser;
const course = {
  id: 'selected', title: 'المقرر المفتوح', lessons: [{ id: 'lesson' }],
  assessments: [
    { id: 'quiz', kind: 'quiz', attemptsUsed: 1, completed: true },
    { id: 'assignment', kind: 'assignment', completed: false },
  ],
} as Course;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function open() { await act(async () => host.querySelector('button')!.click()); }

it('includes the selected course assessment refs in the actual completion percentage', async () => {
  await act(async () => root.render(<FloatingProgressFab course={course} currentUser={user}
    completedLessonIds={['lesson', 'unrelated-course-lesson']} theme="dark" assessmentState="ready" />));
  expect(host.querySelector('button')?.textContent).toBe('67%');
  await open();
  expect(host.textContent).toContain('(100%) 1/1');
  expect(host.textContent).toContain('(0%) 0/1');
});

it('does not report100% or empty assessment totals while they are still loading', async () => {
  await act(async () => root.render(<FloatingProgressFab course={{ ...course, assessments: [] }} currentUser={user}
    completedLessonIds={['lesson']} theme="light" assessmentState="loading" />));
  expect(host.querySelector('button')?.textContent).toBe('—');
  await open();
  expect(host.querySelector('[role="status"]')?.textContent).toContain('جارٍ تحميل تقييمات المقرر');
  expect(host.textContent).not.toContain('0/0');
});

it('keeps failed assessment progress unknown and offers explicit retry', async () => {
  const retry = vi.fn();
  await act(async () => root.render(<FloatingProgressFab course={{ ...course, assessments: [] }} currentUser={user}
    completedLessonIds={['lesson']} theme="dark" assessmentState="error" onRetryAssessments={retry} />));
  expect(host.querySelector('button')?.textContent).toBe('—');
  await open();
  expect(host.querySelector('[role="alert"]')?.textContent).toContain('تعذر حساب الإنجاز الكامل');
  expect(retry).not.toHaveBeenCalled();
  await act(async () => Array.from(host.querySelectorAll('button')).find(button => button.textContent === 'إعادة تحميل بيانات الإنجاز')!.click());
  expect(retry).toHaveBeenCalledTimes(1);
});

it('switches all progress counts to the newly selected course, never the old course', async () => {
  await act(async () => root.render(<FloatingProgressFab course={course} currentUser={user}
    completedLessonIds={['lesson']} theme="light" />));
  await act(async () => root.render(<FloatingProgressFab course={{ ...course, id: 'other', title: 'المقرر الآخر',
    lessons: [], assessments: [{ id: 'other-quiz', title: 'Other', kind: 'quiz', attemptsUsed: 0, accessible: true }] }}
    currentUser={user} completedLessonIds={['lesson']} theme="light" />));
  expect(host.querySelector('button')?.textContent).toBe('0%');
  expect(host.querySelector('button')?.getAttribute('aria-label')).toContain('المقرر الآخر');
});

it('does not count a consumed but unsubmitted quiz attempt as complete', async () => {
  await act(async () => root.render(<FloatingProgressFab course={{ ...course, lessons: [], assessments: [
    { id: 'started', title: 'Started only', kind: 'quiz', attemptsUsed: 1, completed: false, accessible: true },
  ] }} currentUser={user} completedLessonIds={[]} theme="light" />));
  expect(host.querySelector('button')?.textContent).toBe('0%');
});
