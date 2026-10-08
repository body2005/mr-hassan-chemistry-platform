import { describe, expect, it } from 'vitest';
import { emptyRegistration, normalizePhone, validateRegistration } from './registration';

const valid = { ...emptyRegistration, firstName: 'أحمد', middleName: 'محمد', lastName: 'حسن',
  gender: 'MALE' as const, academicYear: '3rd_secondary' as const, studentPhone: '01012345678',
  guardianPhone: '01112345678', governorate: 'CAIRO', city: 'البساتين', schoolName: 'مدرسة الاختبار',
  email: 'synthetic@example.com', password: 'Registration-QA-2026!', confirmation: 'Registration-QA-2026!' };
describe('registration wizard validation', () => {
  it('requires personal details before advancing', () => {
    expect(Object.keys(validateRegistration(emptyRegistration, 1))).toHaveLength(5);
    expect(validateRegistration(valid, 1)).toEqual({});
  });
  it('normalizes Arabic and Persian digits, not letters', () => {
    expect(normalizePhone('٠١٠ ١٢٣٤-٥٦٧٨')).toBe('01012345678');
    expect(normalizePhone('۰۱۱۱۲۳۴۵۶۷۸')).toBe('01112345678');
    expect(validateRegistration({ ...valid, studentPhone: '010garbage' }, 2)).toHaveProperty('studentPhone');
  });
  it('allows omitted mother phone, but rejects an invalid supplied phone', () => {
    expect(validateRegistration(valid, 2)).toEqual({});
    expect(validateRegistration({ ...valid, motherPhone: '123' }, 2)).toHaveProperty('motherPhone');
  });
  it('enforces API password policy, match, email and location', () => {
    const errors = validateRegistration({ ...valid, password: '12345678', confirmation: 'different',
      email: 'bad', city: '', governorate: 'MOON' }, 2);
    expect(Object.keys(errors).sort()).toEqual(['city', 'confirmation', 'email', 'governorate', 'password']);
    expect(validateRegistration({ ...valid, password: 'password123', confirmation: 'password123' }, 'all')).toHaveProperty('password');
  });
  it('revalidates both steps before account creation without OTP', () => {
    expect(validateRegistration(valid, 'all')).toEqual({});
    const errors = validateRegistration({ ...valid, firstName: '<script>', confirmation: 'wrong' }, 'all');
    expect(errors).toHaveProperty('firstName');
    expect(errors).toHaveProperty('confirmation');
    expect(valid).not.toHaveProperty('otp');
  });
});
