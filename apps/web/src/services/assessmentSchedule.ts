/** Normalize teacher-entered local schedule times before any server writes. */
export function assessmentTimestamp(value: string | null | undefined, field: string): string | null {
  if (!value?.trim()) return null;
  const source = value.trim().replace(/[٠-٩۰-۹]/g, char => {
    const code = char.charCodeAt(0);
    return String(code >= 0x6f0 ? code - 0x6f0 : code - 0x660);
  });
  // Already zoned timestamps remain zoned. Never silently repair bad dates.
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/i.test(source)) {
    const date = new Date(source);
    const [year, month, day] = source.slice(0, 10).split('-').map(Number);
    const calendar = new Date(Date.UTC(year, month - 1, day));
    const time = source.match(/T(\d{2}):(\d{2})(?::(\d{2}))?/i)!;
    if (!Number.isNaN(date.getTime()) && calendar.getUTCFullYear() === year
      && calendar.getUTCMonth() === month - 1 && calendar.getUTCDate() === day
      && Number(time[1]) < 24 && Number(time[2]) < 60 && Number(time[3] ?? 0) < 60) return date.toISOString();
  }
  // The current form appends ':00' even after a free-text AM/PM marker.
  const match = source.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*(ص|م|am|pm)(?::00)?)?$/i);
  if (match) {
    const [, year, month, day, hour, minute, second = '0', marker] = match;
    let h = Number(hour);
    if (marker && h >= 1 && h <= 12) h = h % 12 + (/^(م|pm)$/i.test(marker) ? 12 : 0);
    else if (marker) h = -1;
    const date = new Date(Number(year), Number(month) - 1, Number(day), h, Number(minute), Number(second));
    if (h >= 0 && h <= 23 && Number(minute) < 60 && Number(second) < 60
      && date.getFullYear() === Number(year) && date.getMonth() === Number(month) - 1 && date.getDate() === Number(day)) {
      return date.toISOString();
    }
  }
  throw new Error(`وقت ${field} غير صالح. استخدم مثلًا 15:00 أو 3:00م، وتأكد من التاريخ.`);
}

export function assessmentWindow(start: string | null | undefined, end: string | null | undefined) {
  const startsAt = assessmentTimestamp(start, 'بداية الإتاحة');
  const endsAt = assessmentTimestamp(end, 'التسليم');
  if (startsAt && endsAt && new Date(endsAt) <= new Date(startsAt)) {
    throw new Error('موعد الإغلاق يجب أن يكون بعد موعد بداية الإتاحة.');
  }
  return { startsAt, endsAt };
}
