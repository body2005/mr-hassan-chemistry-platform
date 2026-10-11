export type ClockParts = { hour: string; minute: string; period: 'ص' | 'م'; invalid: boolean };
export function clockParts(value: string): ClockParts {
  const normalized = value.trim().replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 1632))
    .replace(/[۰-۹]/g, d => String(d.charCodeAt(0) - 1776));
  if (!normalized) return { hour: '', minute: '', period: 'م', invalid: false };
  const match = normalized.match(/^(\d{0,2}):(\d{0,2})\s*(ص|م|am|pm)?$/i);
  if (!match) return { hour: '', minute: '', period: 'م', invalid: true };
  let hour = match[1];
  const minute = match[2];
  const marker = match[3]?.toLowerCase();
  let period: 'ص' | 'م' = marker === 'ص' || marker === 'am' ? 'ص' : 'م';
  if (!marker && hour && minute && +hour <= 23 && +minute <= 59) {
    period = +hour >= 12 ? 'م' : 'ص';
    hour = String(+hour % 12 || 12).padStart(2, '0');
  }
  const invalid = !!hour && (+hour < 1 || +hour > 12) || !!minute && +minute > 59;
  return { hour, minute, period, invalid };
}
export function clockValue(parts: Pick<ClockParts, 'hour' | 'minute' | 'period'>): string {
  return `${parts.hour}:${parts.minute} ${parts.period}`;
}
export function clockLabel(value: string): string {
  const parts = clockParts(value);
  return parts.invalid || !parts.hour || !parts.minute ? value :
    clockValue({ ...parts, hour: parts.hour.padStart(2, '0'), minute: parts.minute.padStart(2, '0') });
}
