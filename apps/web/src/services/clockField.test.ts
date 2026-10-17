import { expect, it } from 'vitest';
import { clockParts, clockLabel, clockValue } from './clockField';
import { assessmentTimestamp } from './assessmentSchedule';
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
  expect(clockParts('').hour).toBe('');
});
it('defaults omitted clock minutes to zero without supplying a missing hour', () => {
  expect(clockParts('3: م').minute).toBe('00');
  expect(clockLabel('3: م')).toBe('03:00 م');
  expect(clockLabel('15:')).toBe('03:00 م');
  const value = clockValue({ hour: '3', minute: '', period: 'م' });
  expect(value).toBe('3:00 م');
  expect(assessmentTimestamp(`2099-01-01T${value}:00`, 'النشر'))
    .toBe(assessmentTimestamp('2099-01-01T15:00', 'النشر'));
  expect(clockValue({ hour: '', minute: '', period: 'م' })).toBe(': م');
  expect(() => assessmentTimestamp('2099-01-01T:00 م:00', 'النشر')).toThrow();
});
