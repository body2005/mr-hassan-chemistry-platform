import { expect, it } from 'vitest';
import { clockParts, clockLabel } from './clockField';
it('displays midnight/noon and 24-hour persisted drafts as a 12-hour Arabic clock', () => {
  expect(clockLabel('00:00')).toBe('12:00 ص');
  expect(clockLabel('12:00')).toBe('12:00 م');
  expect(clockLabel('23:59')).toBe('11:59 م');
  expect(clockLabel('٣:٠٥ م')).toBe('03:05 م');
});
it('preserves invalid and incomplete schedules instead of silently inventing a time', () => {
  expect(clockLabel('not a time')).toBe('not a time');
  expect(clockParts('00:00 م').invalid).toBe(true);
  expect(clockParts('12:60 ص').invalid).toBe(true);
  expect(clockParts('3: م').minute).toBe('');
  expect(clockParts('').hour).toBe('');
});
