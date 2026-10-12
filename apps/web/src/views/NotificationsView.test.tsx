import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { NotificationsView } from './NotificationsView';
import { notificationService } from '../services/lmsService';
import type { NotificationItem, TeacherProfile } from '../types/lms';

vi.mock('../services/lmsService', () => ({
  calendarService: {
    getCachedCalendarEvents: () => [],
    getNotificationSchedules: async () => [],
    getCalendarEvents: async () => [],
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
