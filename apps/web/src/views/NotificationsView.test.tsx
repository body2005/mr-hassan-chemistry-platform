import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { NotificationsView } from './NotificationsView';
import { calendarService, notificationService } from '../services/lmsService';
import type { CalendarScheduleEvent, NotificationItem, TeacherProfile } from '../types/lms';

vi.mock('../services/lmsService', () => ({
  calendarService: {
    getCachedCalendarEvents: () => [],
    getNotificationSchedules: async () => [],
    getCalendarEvents: vi.fn(async () => []),
    saveCalendarEvent: vi.fn(async () => []),
  },
  notificationService: { getNotifications: vi.fn(async () => []) },
}));
vi.mock('../components/InvoiceModal', () => ({ InvoiceModal: () => null }));
vi.mock('../components/LessonAccessModal', () => ({ LessonAccessModal: () => null }));

const teacher: TeacherProfile = {
  id: 'qa-teacher', name: 'QA Teacher', email: 'teacher@example.test', role: 'teacher',
  nationalId: '', phone: '', teachingYear: 'all', teachingYearLabel: '', subject: '',
  contractAgreed: true, joinedDate: '',
};
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.mocked(notificationService.getNotifications).mockResolvedValue([]);
  vi.mocked(calendarService.getCalendarEvents).mockResolvedValue([]);
  vi.mocked(calendarService.saveCalendarEvent).mockReset();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals();
});
function button(text: string) {
  return [...host.querySelectorAll('button')].find(el => el.textContent?.trim() === text)!;
}
async function change(el: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype
    : el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(el, value);
    el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }));
  });
}
it('sends manual broadcasts to Notifications even when the teacher selects quiz content', async () => {
  const add = vi.fn<(item: NotificationItem) => Promise<void>>(async () => undefined);
  const navigate = vi.fn();
  const props = { notifications: [], currentUser: teacher, onMarkNotificationRead: vi.fn(),
    onNavigateToTab: navigate, onAddNotification: add };
  await act(async () => root.render(<NotificationsView {...props} />));
  await act(async () => button('إرسال إشعار فوري للطلاب').click());
  expect(host.textContent).not.toContain('زر الانتقال المباشر');
  await change(host.querySelector<HTMLInputElement>('input[placeholder="مثال: تنبيه هام حول موعد حل الاختبار القادم"]')!, 'تنبيه اختبار');
  await change(host.querySelector<HTMLTextAreaElement>('textarea')!, 'راجع تفاصيل الإشعار');
  const typeSelect = [...host.querySelectorAll('select')].find(el => el.querySelector('option[value="warning"]'))!;
  await change(typeSelect, 'quiz');
  await act(async () => button('إرسال الإشعار الآن').click());
  expect(add).toHaveBeenCalledWith(expect.objectContaining({ type: 'quiz', actionTab: 'Notifications', title: 'تنبيه اختبار' }));

  const sent = add.mock.calls[0][0];
  vi.mocked(notificationService.getNotifications).mockResolvedValue([sent]);
  await act(async () => window.dispatchEvent(new Event('lms_notifications_updated')));
  await act(async () => button('عرض الإشعارات').click());
  expect(navigate).toHaveBeenCalledWith('Notifications');
});

it('adds two same-day appointments with distinct identities even when their forms are identical', async () => {
  const rows: CalendarScheduleEvent[] = [];
  vi.mocked(calendarService.getCalendarEvents).mockImplementation(async () => [...rows]);
  vi.mocked(calendarService.saveCalendarEvent).mockImplementation(async event => {
    rows.push({ ...event, id: `saved-${rows.length + 1}` }); return [...rows];
  });
  await act(async () => root.render(<NotificationsView notifications={[]} currentUser={teacher}
    onMarkNotificationRead={vi.fn()} onNavigateToTab={vi.fn()} onAddNotification={async () => undefined} />));
  for (let i = 0; i < 2; i++) {
    await act(async () => button('إضافة موعد جديد').click());
    await change(host.querySelector<HTMLInputElement>('input[placeholder="مثال: مراجعة الفصل الأول قبل الاختبار"]')!, 'موعد مستقل');
    await act(async () => button('التالي: تحديد التوقيت').click());
    await act(async () => button('التالي: مراجعة وحفظ').click());
    await act(async () => button('تأكيد وحفظ الموعد في الجدول').click());
  }
  const calls = vi.mocked(calendarService.saveCalendarEvent).mock.calls;
  expect(calls).toHaveLength(2);
  expect(calls[0][0].id).not.toBe(calls[1][0].id);
  expect(host.querySelectorAll('.calendar-day-event')).toHaveLength(2);
});

it('allows an optional description and makes immediate, scheduled and private publication exclusive', async () => {
  const add = vi.fn<(item: NotificationItem) => Promise<void>>(async () => undefined);
  vi.mocked(calendarService.saveCalendarEvent).mockResolvedValue([]);
  await act(async () => root.render(<NotificationsView notifications={[]} currentUser={teacher}
    onMarkNotificationRead={vi.fn()} onNavigateToTab={vi.fn()} onAddNotification={add} />));
  await act(async () => button('إضافة موعد جديد').click());
  expect(button('التالي: تحديد التوقيت').disabled).toBe(false);
  expect(host.querySelector('#calendar-title-help')?.textContent).toContain('يمكنك تركه فارغًا');
  const title = host.querySelector<HTMLInputElement>('input[placeholder="مثال: مراجعة الفصل الأول قبل الاختبار"]')!;
  await change(title, 'س');
  expect(button('التالي: تحديد التوقيت').disabled).toBe(false);
  await change(title, 'مراجعة الجدولة');
  expect(button('التالي: تحديد التوقيت').disabled).toBe(false);
  const immediate = host.querySelector<HTMLInputElement>('input[value="immediate"]')!;
  const scheduled = host.querySelector<HTMLInputElement>('input[value="scheduled"]')!;
  const privateOption = host.querySelector<HTMLInputElement>('input[value="private"]')!;
  expect(immediate.checked).toBe(true);
  await act(async () => scheduled.click());
  expect(immediate.checked).toBe(false);
  expect(scheduled.checked).toBe(true);
  await act(async () => privateOption.click());
  expect(scheduled.checked).toBe(false);
  await act(async () => scheduled.click());
  await change(host.querySelector<HTMLInputElement>('input[type="date"]')!, '2035-05-13');
  await act(async () => button('التالي: تحديد التوقيت').click());
  await act(async () => button('التالي: مراجعة وحفظ').click());
  expect(host.textContent).toContain('ظهور الموعد والإشعار: 2035-05-13');
  await act(async () => button('تأكيد وحفظ الموعد في الجدول').click());
  expect(calendarService.saveCalendarEvent).toHaveBeenCalledWith(expect.objectContaining({
    isPublishedToStudents: true, publishStartDate: '2035-05-13', publishStartTime: '06:00 م',
  }));
  expect(add).toHaveBeenCalledWith(expect.objectContaining({ scheduledFor: '2035-05-13T15:00:00.000Z', message: expect.stringContaining('مراجعة الجدولة') }));
});

it('closes promptly while saving, restores a failed draft, and retries without a new event key', async () => {
  let rejectSave!: (error: Error) => void;
  const pending = new Promise<CalendarScheduleEvent[]>((_, reject) => { rejectSave = reject; });
  vi.mocked(calendarService.saveCalendarEvent).mockReturnValueOnce(pending).mockResolvedValue([]);
  await act(async () => root.render(<NotificationsView notifications={[]} currentUser={teacher}
    onMarkNotificationRead={vi.fn()} onNavigateToTab={vi.fn()} onAddNotification={async () => undefined} />));
  await act(async () => button('إضافة موعد جديد').click());
  // Blank description is optional and must still produce a valid server title.
  await act(async () => button('التالي: تحديد التوقيت').click());
  await act(async () => button('التالي: مراجعة وحفظ').click());
  await act(async () => button('تأكيد وحفظ الموعد في الجدول').click());
  expect(button('تأكيد وحفظ الموعد في الجدول')).toBeUndefined();
  expect(host.querySelector('[role="status"]')?.textContent).toContain('جارٍ حفظ');
  await act(async () => button('إضافة موعد جديد').click());
  expect(button('تأكيد وحفظ الموعد في الجدول')).toBeUndefined();
  await act(async () => rejectSave(new Error('QA save unavailable')));
  expect(button('تأكيد وحفظ الموعد في الجدول')).toBeDefined();
  expect(host.querySelector('[role="alert"]')?.textContent).toContain('QA save unavailable');
  await act(async () => button('تأكيد وحفظ الموعد في الجدول').click());
  const calls = vi.mocked(calendarService.saveCalendarEvent).mock.calls;
  expect(calls).toHaveLength(2);
  expect(calls[0][0].id).toBe(calls[1][0].id);
  expect(calls[0][0].dayDescription).toBe('');
  expect(calls[0][0].dayName.length).toBeGreaterThan(2);
});

it('adds another appointment from the existing event editor without replacing the original', async () => {
  const date = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Cairo' }).format(new Date());
  const rows: CalendarScheduleEvent[] = [{ id: 'stored-original', creatorId: teacher.id,
    academicYear: '1st_secondary', date, dayName: 'الموعد المحفوظ', time: '06:00 م', contentType: 'lesson' }];
  vi.mocked(calendarService.getCalendarEvents).mockImplementation(async () => [...rows]);
  vi.mocked(calendarService.saveCalendarEvent).mockImplementation(async event => {
    rows.push({ ...event, id: 'stored-second' }); return [...rows];
  });
  await act(async () => root.render(<NotificationsView notifications={[]} currentUser={teacher}
    onMarkNotificationRead={vi.fn()} onNavigateToTab={vi.fn()} onAddNotification={async () => undefined} />));
  expect(button('إضافة موعد في هذا اليوم')).toBeDefined();
  await act(async () => button('تعديل الموعد').click());
  expect(host.querySelector<HTMLInputElement>('#calendar-day-description')?.value).toBe('الموعد المحفوظ');
  await act(async () => button('إضافة موعد آخر لنفس اليوم').click());
  expect(host.querySelector<HTMLInputElement>('#calendar-day-description')?.value).toBe('');
  await act(async () => button('التالي: تحديد التوقيت').click());
  await act(async () => button('التالي: مراجعة وحفظ').click());
  await act(async () => button('تأكيد وحفظ الموعد في الجدول').click());
  const sent = vi.mocked(calendarService.saveCalendarEvent).mock.calls[0][0];
  expect(sent.id).toMatch(/^evt_/);
  expect(sent.date).toBe(date);
  expect(rows).toHaveLength(2);
  expect(rows[0].dayName).toBe('الموعد المحفوظ');
});
