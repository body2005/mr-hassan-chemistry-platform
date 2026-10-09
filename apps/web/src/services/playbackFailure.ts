/** HTTP denial is not an offline error; neither should cause a retry loop. */
export function playbackFailureMessage(error: unknown): string {
  const failure = error && typeof error === 'object' ? error as { status?: number; code?: string } : {};
  if (failure.status === 401) return 'انتهت جلسة تسجيل الدخول. سجّل الدخول مجددًا لتشغيل الفيديو.';
  if (failure.status === 403) return 'لا تملك صلاحية مشاهدة هذا الدرس. تحقق من اشتراكك أو تواصل مع المدرس.';
  if (failure.status === 429) return 'طلبات كثيرة في وقت قصير. انتظر قليلًا ثم أعد المحاولة يدويًا.';
  if (failure.code === 'REQUEST_CANCELLED') return 'تغيّرت الجلسة؛ افتح الدرس من حسابك الحالي.';
  return 'تعذر الاتصال لتشغيل الفيديو. تحقق من الإنترنت ثم أعد المحاولة؛ لا يلزم إعادة رفع الملف.';
}
