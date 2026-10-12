/** HTTP denial is not an offline error; neither should cause a retry loop. */
export function playbackFailureMessage(error: unknown): string {
  const failure = error && typeof error === 'object' ? error as { status?: number; code?: string } : {};
  if (failure.status === 401) return 'انتهت جلسة تسجيل الدخول. سجّل الدخول مجددًا لتشغيل الفيديو.';
  if (failure.status === 403) return 'لا تملك صلاحية مشاهدة هذا الدرس. تحقق من اشتراكك أو تواصل مع المدرس.';
  if (failure.status === 404) return 'ملف الفيديو غير موجود في التخزين. يحتاج المدرس إلى إعادة رفعه بعد تفعيل التخزين الدائم.';
  if (failure.status === 503) return 'خدمة تخزين الفيديو غير متاحة مؤقتًا. أعد المحاولة لاحقًا.';
  if (failure.status === 429) return 'تعذر بدء التشغيل مؤقتًا. أعد المحاولة بعد قليل.';
  if (failure.code === 'REQUEST_CANCELLED') return 'تغيّرت الجلسة؛ افتح الدرس من حسابك الحالي.';
  return 'تعذر الاتصال لتشغيل الفيديو. تحقق من الإنترنت ثم أعد المحاولة؛ لا يلزم إعادة رفع الملف.';
}

export function materialFailureMessage(error: unknown): string {
  const status = error && typeof error === 'object' ? (error as { status?: number }).status : undefined;
  if (status === 404) return 'ملف المذكرة غير موجود في التخزين. يحتاج المدرس إلى إعادة رفعه بعد تفعيل التخزين الدائم.';
  if (status === 503) return 'خدمة تخزين الملفات غير متاحة مؤقتًا. أعد المحاولة لاحقًا.';
  return 'تعذر تنزيل المذكرة. تحقق من الاتصال وصلاحية الوصول ثم أعد المحاولة.';
}
