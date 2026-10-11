import { getApiAuthGeneration, invalidateApiCache } from './apiClient';

let hintTimer: ReturnType<typeof setTimeout> | undefined;
export function assessmentsChanged() {
  for (const path of ['/users', '/reports', '/analytics', '/quizzes', '/assignments', '/courses', '/bootstrap', '/calendar', '/notifications']) invalidateApiCache(path);
  clearTimeout(hintTimer);
  hintTimer = setTimeout(() => {
    window.dispatchEvent(new Event('lms_assessments_updated'));
    window.dispatchEvent(new Event('lms_courses_updated'));
    window.dispatchEvent(new Event('lms_schedule_updated'));
    window.dispatchEvent(new Event('lms_notifications_updated'));
  }, 300);
}

let clock: { epoch: number; sampled: number } | undefined;
export function synchronizeServerTime(value: string) {
  const epoch = Date.parse(value);
  if (Number.isFinite(epoch)) clock = { epoch, sampled: performance.now() };
}
export function serverNow(): number | null {
  return clock ? clock.epoch + performance.now() - clock.sampled : null;
}

const timers = new Map<string, ReturnType<typeof setTimeout>>();
// Use the server's interval, never the device wall clock. This refresh is a
// hint only: the API still checks time, entitlement and publication on access.
export function armAvailabilityRefresh(courseId: string, serverTime: string, next: string | null) {
  synchronizeServerTime(serverTime);
  clearTimeout(timers.get(courseId));
  timers.delete(courseId);
  if (!next) return;
  const delay = Date.parse(next) - Date.parse(serverTime);
  if (!Number.isFinite(delay) || delay <= 0) return;
  const generation = getApiAuthGeneration();
  const wake = (remaining: number) => {
    timers.set(courseId, setTimeout(() => {
      if (generation !== getApiAuthGeneration()) { timers.delete(courseId); return; }
      // Browsers cap a single timer at about 24 days. Long waits are chunked,
      // without network polling or introducing a device-clock access check.
      if (remaining > 2_000_000_000) wake(remaining - 2_000_000_000);
      else { timers.delete(courseId); assessmentsChanged(); }
    }, Math.min(remaining, 2_000_000_000)));
  };
  wake(delay + 250);
}

if (typeof window !== 'undefined') window.addEventListener('lms_auth_scope_updated', () => {
  for (const timer of timers.values()) clearTimeout(timer);
  timers.clear();
  clearTimeout(hintTimer);
  clock = undefined;
});
