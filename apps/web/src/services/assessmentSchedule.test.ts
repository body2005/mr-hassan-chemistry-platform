import { describe, expect, it } from 'vitest';
import { assessmentTimestamp, assessmentWindow } from './assessmentSchedule';

describe('teacher schedule serialization', () => {
  it.each(['2026-10-04T3:00م:00', '2026-10-04T٣:٠٠م:00', '2026-10-04T3:00 PM:00', '2026-10-04T15:00:00'])('accepts %s without sending malformed ISO', value => {
    expect(assessmentTimestamp(value, 'النشر')).toBe(new Date(2026, 9, 4, 15, 0).toISOString());
  });
  it('handles noon/midnight and optional empty schedules', () => {
    expect(assessmentTimestamp('2026-10-04T12:00ص:00', 'النشر')).toBe(new Date(2026, 9, 4, 0, 0).toISOString());
    expect(assessmentTimestamp('2026-10-04T12:00م:00', 'النشر')).toBe(new Date(2026, 9, 4, 12, 0).toISOString());
    expect(assessmentTimestamp(null, 'النشر')).toBeNull();
    expect(assessmentTimestamp('2026-10-04T15:00:00+03:00', 'النشر')).toBe('2026-10-04T12:00:00.000Z');
  });
  it.each(['2026-02-30T15:00:00', '2026-02-30T15:00:00Z', '2026-10-04T24:00:00Z', '2026-10-04T15:00:00:00', '2026-10-04T25:00:00', '2026-10-04T13:00م:00', '2026-10-04T15:99:00', '2026-10-04Tabc:00'])('rejects %s before creating questions or assignments', value => {
    expect(() => assessmentTimestamp(value, 'النشر')).toThrow('غير صالح');
  });
  it('rejects reversed windows', () => {
    expect(() => assessmentWindow('2026-10-04T6:00م:00', '2026-10-04T3:00م:00')).toThrow('بعد');
  });
});
