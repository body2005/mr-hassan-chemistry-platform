import { expect, it } from 'vitest';
import { assessmentBand, assessmentPercent } from './assessmentOutcome';
it.each([[10, 10, 100], [5, 10, 50], [80, 200, 40], [0, 10, 0]])('converts %s/%s to %s percent', (score, total, expected) => {
  expect(assessmentPercent(score, total)).toBe(expected);
});
it.each([[0, 0], [5, null], [20, 10], [-1, 10], [NaN, 10], [10, Infinity]])('does not classify or clamp invalid %s/%s', (score, total) => {
  expect(assessmentPercent(score, total)).toBeNull();
  expect(assessmentBand(assessmentPercent(score, total))).toContain('غير قابلة للحساب');
});
it.each([[90, 'ممتاز'], [80, 'جيد جداً'], [70, 'جيد'], [60, 'مقبول']])('uses API classification at %s percent', (percent, expected) => {
  expect(assessmentBand(percent)).toBe(expected);
});
