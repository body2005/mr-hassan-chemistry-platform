/** Match the reporting API: percentage, never raw marks or a clamped result. */
export function assessmentPercent(score: number | null | undefined, total: number | null | undefined): number | null {
  if (score == null || total == null || !Number.isFinite(score) || !Number.isFinite(total)
    || total <= 0 || score < 0 || score > total) return null;
  return Math.round(score / total * 1000) / 10;
}

export function assessmentBand(percent: number | null): string {
  if (percent == null) return 'النتيجة غير قابلة للحساب — تحتاج مراجعة';
  if (percent >= 90) return 'ممتاز';
  if (percent >= 80) return 'جيد جداً';
  if (percent >= 70) return 'جيد';
  if (percent >= 60) return 'مقبول';
  return 'ضعيف — راجع الدرس لتحسين مستواك';
}
