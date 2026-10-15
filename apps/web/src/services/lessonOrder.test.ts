import { expect, it } from 'vitest';
import type { VideoLesson } from '../types/lms';
import { newestLessonsFirst } from './lessonOrder';

it('orders uploads across units by their own date without mutating curriculum order', () => {
  const lessons = [
    { id: 'older-high-position', uploadedAt: '2026-10-01T12:00:00Z', order: 99, moduleId: 'second' },
    { id: 'newer-low-position', uploadedAt: '2026-10-15T12:00:00Z', order: 1, moduleId: 'first' },
    { id: 'middle', uploadedAt: '2026-10-12T12:00:00Z', order: 8, moduleId: 'third' },
  ] as VideoLesson[];
  expect(newestLessonsFirst(lessons).map(lesson => lesson.id))
    .toEqual(['newer-low-position', 'middle', 'older-high-position']);
  expect(lessons[0].id).toBe('older-high-position');
});

it('keeps valid dates first and falls back deterministically for undated legacy entries', () => {
  const lessons = [
    { id: 'undated', uploadedAt: '', order: 1 },
    { id: 'invalid', uploadedAt: 'invalid', order: 2 },
    { id: 'dated', uploadedAt: '2026-10-01T12:00:00Z', order: 0 },
  ] as VideoLesson[];
  expect(newestLessonsFirst(lessons).map(lesson => lesson.id)).toEqual(['dated', 'invalid', 'undated']);
});
