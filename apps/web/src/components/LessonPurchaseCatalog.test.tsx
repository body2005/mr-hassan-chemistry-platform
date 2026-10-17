import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LessonPurchaseCatalog } from './LessonPurchaseCatalog';
import type { Course } from '../types/lms';

const course = {
  id: 'first-year', title: 'First year chemistry', status: 'published', academicYear: '1st_secondary',
  lessons: [{ id: 'paid-lesson', title: 'Paid geology lesson', price: 50, uploadedAt: '', order: 1,
    videoUrl: '/private-video', materials: [{ filename: 'private.pdf' }] }],
  assessments: [{ title: 'Private exam' }],
} as unknown as Course;
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

it('shows the published paid lesson before enrollment and opens its existing checkout without playback', async () => {
  const checkout = vi.fn();
  await act(async () => root.render(<LessonPurchaseCatalog courses={[course]} year="1st_secondary" enrolledIds={[]} lang="ar" onCheckout={checkout} />));
  expect(host.textContent).toContain('Paid geology lesson');
  expect(host.textContent).toContain('يلزم شراء الدرس');
  expect(host.textContent).not.toContain('Private exam');
  expect(host.innerHTML).not.toContain('/private-video');
  expect(host.innerHTML).not.toContain('private.pdf');
  expect(host.querySelector('video')).toBeNull();
  await act(async () => host.querySelector<HTMLButtonElement>('button')!.click());
  expect(checkout).toHaveBeenCalledWith({ productType: 'lesson', productId: 'paid-lesson' });
});

it('does not display lessons from another grade, drafts, or already enrolled courses', async () => {
  await act(async () => root.render(<LessonPurchaseCatalog
    courses={[course, { ...course, id: 'draft', status: 'draft' }, { ...course, id: 'other-grade', academicYear: '2nd_secondary' }]}
    year="1st_secondary" enrolledIds={[course.id]} lang="en" onCheckout={vi.fn()} fallback={<p>No lessons for this grade</p>} />));
  expect(host.textContent).toBe('No lessons for this grade');
});

it('uses English sales labels and does not recreate the removed free-course panel', async () => {
  await act(async () => root.render(<LessonPurchaseCatalog courses={[{ ...course, lessons: [...course.lessons, { ...course.lessons[0], id: 'free', title: 'Free lesson', price: 0 }] }]}
    year="1st_secondary" enrolledIds={[]} lang="en" onCheckout={vi.fn()} />));
  expect(host.textContent).toContain('Purchase lesson');
  expect(host.textContent).toContain('50 EGP');
  expect(host.textContent).not.toContain('Free lesson');
});
