export function formatGrade(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? `${value}%` : '—';
}

export function followUpLabel(value: number | null | undefined, threshold: number): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return value < threshold ? 'تحت المعدل الأدنى' : 'أعلى من الحد الأدنى';
}
