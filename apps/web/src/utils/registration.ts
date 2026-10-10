export const GOVERNORATES = [
  ["ALEXANDRIA", "الإسكندرية", "Alexandria"], ["ASWAN", "أسوان", "Aswan"], ["ASIUT", "أسيوط", "Asiut"],
  ["BEHEIRA", "البحيرة", "Beheira"], ["BENI_SUEF", "بني سويف", "Beni Suef"], ["CAIRO", "القاهرة", "Cairo"],
  ["DAKAHLIA", "الدقهلية", "Dakahlia"], ["DAMIETTA", "دمياط", "Damietta"], ["FAYOUM", "الفيوم", "Fayoum"],
  ["GHARBIA", "الغربية", "Gharbia"], ["GIZA", "الجيزة", "Giza"], ["ISMAILIA", "الإسماعيلية", "Ismailia"],
  ["KAFR_EL_SHEIKH", "كفر الشيخ", "Kafr El Sheikh"], ["LUXOR", "الأقصر", "Luxor"], ["MATROUH", "مطروح", "Matrouh"],
  ["MINYA", "المنيا", "Minya"], ["MONUFIA", "المنوفية", "Monufia"], ["NEW_VALLEY", "الوادي الجديد", "New Valley"],
  ["NORTH_SINAI", "شمال سيناء", "North Sinai"], ["PORT_SAID", "بورسعيد", "Port Said"], ["QALYUBIA", "القليوبية", "Qalyubia"],
  ["QENA", "قنا", "Qena"], ["RED_SEA", "البحر الأحمر", "Red Sea"], ["SHARQIA", "الشرقية", "Sharqia"],
  ["SOHAG", "سوهاج", "Sohag"], ["SOUTH_SINAI", "جنوب سيناء", "South Sinai"], ["SUEZ", "السويس", "Suez"],
] as const;

export type RegistrationData = {
  firstName: string; middleName: string; lastName: string;
  gender: '' | 'MALE' | 'FEMALE';
  academicYear: '' | '1st_secondary' | '2nd_secondary' | '3rd_secondary';
  educationDivision: 'GENERAL' | 'AZHAR'; specialization: 'SCIENCE' | 'MATH';
  studentPhone: string; guardianPhone: string; motherPhone: string;
  governorate: string; city: string; schoolName: string; email: string;
  password: string; confirmation: string;
};
export const emptyRegistration: RegistrationData = {
  firstName: '', middleName: '', lastName: '', gender: '', academicYear: '',
  educationDivision: 'GENERAL', specialization: 'SCIENCE',
  studentPhone: '', guardianPhone: '', motherPhone: '', governorate: '',
  city: '', schoolName: '', email: '', password: '', confirmation: '',
};
export type RegistrationErrors = Partial<Record<keyof RegistrationData, string>>;
export function sanitizeRegistrationField(key: keyof RegistrationData, value: string): string {
  if (['firstName', 'middleName', 'lastName'].includes(key)) return value.replace(/[^\p{L}\p{M} ]/gu, '');
  if (['studentPhone', 'guardianPhone', 'motherPhone'].includes(key)) return normalizePhone(value).replace(/[^0-9]/g, '');
  return value;
}
export function normalizePhone(value: string): string {
  return value.replace(/[٠-٩۰-۹]/g, digit => String('٠١٢٣٤٥٦٧٨٩'.includes(digit)
    ? '٠١٢٣٤٥٦٧٨٩'.indexOf(digit) : '۰۱۲۳۴۵۶۷۸۹'.indexOf(digit)))
    .replace(/[\s()-]/g, '');
}
export function validateRegistration(data: RegistrationData, step: 1 | 2 | 'all', arabic = true): RegistrationErrors {
  const errors: RegistrationErrors = {};
  const message = (ar: string, en: string) => arabic ? ar : en;
  if (step === 1 || step === 'all') {
    for (const field of ['firstName', 'middleName', 'lastName'] as const) {
      if (!/^[\p{L}][\p{L}\p{M} ]{1,49}$/u.test(data[field].trim()))
        errors[field] = message('أدخل اسمًا صحيحًا من حرفين إلى 50 حرفًا', 'Enter a valid name (2–50 characters)');
    }
    if (!data.gender) errors.gender = message('اختر النوع', 'Select gender');
    if (!data.academicYear) errors.academicYear = message('اختر السنة الدراسية', 'Select school year');
  }
  if (step === 2 || step === 'all') {
    for (const field of ['studentPhone', 'guardianPhone', 'motherPhone'] as const) {
      if (field === 'motherPhone' && !data[field].trim()) continue;
      if (!/^01[0125]\d{8}$/.test(normalizePhone(data[field])))
        errors[field] = message('أدخل رقم موبايل مصري صحيحًا من 11 رقمًا', 'Enter a valid 11-digit Egyptian mobile number');
    }
    if (!GOVERNORATES.some(([code]) => code === data.governorate))
      errors.governorate = message('اختر المحافظة', 'Select governorate');
    if (data.city.trim().length < 2 || data.city.trim().length > 100)
      errors.city = message('أدخل المدينة أو المنطقة (2–100 حرف)', 'Enter city/district (2–100 characters)');
    if (data.schoolName.trim().length < 2 || data.schoolName.trim().length > 200)
      errors.schoolName = message('أدخل اسم المدرسة (2–200 حرف)', 'Enter school name (2–200 characters)');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email.trim()))
      errors.email = message('أدخل بريدًا إلكترونيًا صحيحًا لاسترجاع الحساب', 'Enter a valid email for account recovery');
    if (data.password.length < 10 || data.password.length > 128)
      errors.password = message('كلمة المرور من 10 إلى 128 حرفًا', 'Use 10–128 characters');
    else if (['password123', '1234567890', 'qwerty1234'].includes(data.password.toLowerCase()))
      errors.password = message('اختر كلمة مرور يصعب تخمينها', 'Choose a less predictable password');
    if (data.confirmation !== data.password || !data.confirmation)
      errors.confirmation = message('كلمتا المرور غير متطابقتين', 'Passwords do not match');
  }
  return errors;
}
