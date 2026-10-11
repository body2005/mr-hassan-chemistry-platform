import { beforeEach, expect, it } from 'vitest';
import { readCatalogState, readEnrollmentIntent, saveEnrollmentIntent } from './catalogState';
beforeEach(() => { sessionStorage.clear(); window.history.replaceState({}, '', '/'); });
it('keeps selection across authentication without storing auth or entitlement', () => {
  const selected = { id: 'selected-course', title: 'الكيمياء', academicYear: '3rd_secondary' as const };
  saveEnrollmentIntent(selected);
  expect(readEnrollmentIntent()).toEqual(selected);
  expect(sessionStorage.length).toBe(1);
  expect(sessionStorage.getItem(sessionStorage.key(0)!)).not.toMatch(/token|password|enrolled/);
  saveEnrollmentIntent(null);
  expect(readEnrollmentIntent()).toBeNull();
});
it('rejects malformed intent and unknown grade filter', () => {
  sessionStorage.setItem('lms_catalog_enrollment_intent', '{malformed');
  expect(readEnrollmentIntent()).toBeNull();
  window.history.replaceState({}, '', '/?catalog_grade=unknown');
  expect(readCatalogState().grade).toBe('');
});
