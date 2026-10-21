import type { CalendarScheduleEvent } from '../types/lms';
import { cairoLocalValue } from './cairoTime';

export const CALENDAR_TYPES = {
  lesson: { color: '#10b981', label: 'درس' },
  quiz: { color: '#ef4444', label: 'اختبار' },
  assignment: { color: '#f59e0b', label: 'واجب' },
  general: { color: '#3b82f6', label: 'تنبيه عام' },
  review: { color: '#3b82f6', label: 'مراجعة' },
} as const;

// Original calendar tints and selection colors, shared by every partition.
export const CALENDAR_TINTS = {
  lesson: { background: 'rgba(16, 185, 129, 0.18)', selected: 'rgba(16, 185, 129, 0.32)', text: '#059669', border: '#047857' },
  quiz: { background: 'rgba(239, 68, 68, 0.18)', selected: 'rgba(239, 68, 68, 0.32)', text: '#dc2626', border: '#b91c1c' },
  assignment: { background: 'rgba(245, 158, 11, 0.18)', selected: 'rgba(245, 158, 11, 0.32)', text: '#d97706', border: '#b45309' },
  general: { background: 'rgba(59, 130, 246, 0.16)', selected: 'rgba(59, 130, 246, 0.32)', text: '#2563eb', border: '#1d4ed8' },
  review: { background: 'rgba(59, 130, 246, 0.16)', selected: 'rgba(59, 130, 246, 0.32)', text: '#2563eb', border: '#1d4ed8' },
} as const;

export function calendarEventTooltip(event: CalendarScheduleEvent, lang = 'ar') {
  const label = lang === 'en' ? { lesson: 'Lesson', quiz: 'Exam', assignment: 'Assignment',
    review: 'Review', general: 'Announcement' }[event.contentType] : CALENDAR_TYPES[event.contentType].label;
  return `${label} · ${calendarEventTime(event, lang)}`;
}

export function calendarDay(event: CalendarScheduleEvent): string {
  return event.startsAt ? cairoLocalValue(event.startsAt).slice(0, 10) : event.date.split('T')[0];
}

export function calendarClock(value: string): string {
  const normalized = value.replace(/[٠-٩۰-۹]/g, c => String(c.charCodeAt(0) - (c >= '۰' ? 0x6f0 : 0x660)));
  const match = normalized.match(/(\d{1,2}):(\d{2})/);
  if (!match) return '18:00';
  let hour = Number(match[1]);
  if (/م|pm/i.test(normalized)) hour = hour % 12 + 12;
  else if (/ص|am/i.test(normalized)) hour %= 12;
  return `${String(hour).padStart(2, '0')}:${match[2]}`;
}

export function calendarTimeConflicts(events: CalendarScheduleEvent[], target: CalendarScheduleEvent, creatorId: string) {
  const clock = (event: CalendarScheduleEvent) => event.startsAt
    ? cairoLocalValue(event.startsAt).slice(11, 16) : calendarClock(event.time);
  return events.filter(event => event.id !== target.id && !event.isCancelled
    && (event.creatorId || creatorId) === creatorId
    && (event.academicYear === target.academicYear || event.academicYear === 'all' || target.academicYear === 'all')
    && calendarDay(event) === calendarDay(target) && clock(event) === clock(target));
}

export function sortCalendarEvents(events: CalendarScheduleEvent[]) {
  return [...events].sort((a, b) => {
    if (a.startsAt && b.startsAt) return Date.parse(a.startsAt) - Date.parse(b.startsAt) || a.id.localeCompare(b.id);
    const time = (e: CalendarScheduleEvent) => e.startsAt
      ? cairoLocalValue(e.startsAt) : `${calendarDay(e)}T${calendarClock(e.time)}`;
    return time(a).localeCompare(time(b)) || (a.startsAt || '').localeCompare(b.startsAt || '') || a.id.localeCompare(b.id);
  });
}

export function calendarEventTime(event: CalendarScheduleEvent, lang = 'ar') {
  const locale = lang === 'en' ? 'en-GB' : 'ar-EG';
  const format = (value: string) => new Intl.DateTimeFormat(locale, {
    timeZone: 'Africa/Cairo', hour: 'numeric', minute: '2-digit', hour12: true,
  }).format(new Date(value));
  const start = event.startsAt ? format(event.startsAt) : event.time;
  return event.endsAt ? `${start} – ${format(event.endsAt)}` : start;
}
