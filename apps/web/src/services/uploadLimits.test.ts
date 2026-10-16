import { expect, it } from 'vitest';
import { validateLessonTitle, validateLessonUpload } from './uploadLimits';

it('accepts long Arabic lesson titles and video filenames without changing them', () => {
  const title = 'عنوان درس طويل '.repeat(20);
  const file = new File(['video'], `${title}.mp4`, { type: 'video/mp4' });
  expect(title.length).toBeGreaterThan(200);
  expect(() => validateLessonTitle(title)).not.toThrow();
  expect(() => validateLessonUpload(file, 'video')).not.toThrow();
  expect(file.name).toBe(`${title}.mp4`);
});

it('counts Unicode characters consistently with the API and rejects out-of-range titles', () => {
  expect(() => validateLessonTitle('أ'.repeat(998) + '🔥🔥')).not.toThrow();
  expect(() => validateLessonTitle('أ'.repeat(1001))).toThrow('1000');
  expect(() => validateLessonTitle(' أ ')).toThrow('حرفين');
  expect(() => validateLessonTitle('أ'.repeat(1001), 'en')).toThrow('2–1000');
});
