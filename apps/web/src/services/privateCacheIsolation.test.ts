// Regression source only; not executed in the source-only review.
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

beforeEach(() => { vi.resetModules(); localStorage.clear(); });
afterEach(() => { vi.restoreAllMocks(); });

it('never treats an old browser profile as a verified login on reload', async () => {
  localStorage.setItem('lms_cached_user', JSON.stringify({ id: 'previous-teacher', role: 'teacher', name: 'Old profile' }));
  const { authService } = await import('./lmsService');
  expect(authService.getCachedUser()).toBeNull();
  // Preserve the old blob without silently attributing it to a new session.
  expect(localStorage.getItem('lms_cached_user')).toContain('previous-teacher');
});

it('does not reuse legacy or another accounts local notification schedules', async () => {
  localStorage.setItem('lms_notification_schedules_v1', JSON.stringify([{ title: 'Unattributed old notice' }]));
  const { setApiAuthScope } = await import('./apiClient');
  const { calendarService, notificationScheduleStorageKey } = await import('./lmsService');
  setApiAuthScope('owner-a');
  const ownerKey = notificationScheduleStorageKey()!;
  localStorage.setItem(ownerKey, JSON.stringify([{ title: 'Private notice A' }]));
  expect(await calendarService.getNotificationSchedules()).toEqual([{ title: 'Private notice A' }]);
  setApiAuthScope('owner-b');
  expect(await calendarService.getNotificationSchedules()).toEqual([]);
  expect(notificationScheduleStorageKey()).not.toBe(ownerKey);
  setApiAuthScope('anonymous');
  expect(await calendarService.getNotificationSchedules()).toEqual([]);
});
