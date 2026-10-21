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
    await change(host.querySelector<HTMLInputElement>('input[placeholder="مثال: الثلاثاء - المحاضرة الأسبوعية"]')!, 'موعد مستقل');
    await act(async () => button('التالي: تحديد التوقيت').click());
    await act(async () => button('التالي: مراجعة وحفظ').click());
    await act(async () => button('تأكيد وحفظ الموعد في الجدول').click());
  }
  const calls = vi.mocked(calendarService.saveCalendarEvent).mock.calls;
  expect(calls).toHaveLength(2);
  expect(calls[0][0].id).not.toBe(calls[1][0].id);
  expect(host.querySelectorAll('.calendar-day-event')).toHaveLength(2);
});
