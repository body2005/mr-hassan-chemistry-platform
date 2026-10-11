import { afterEach, beforeEach, expect, it, vi } from 'vitest';

beforeEach(() => { vi.resetModules(); vi.stubEnv('VITE_API_URL', '/api/v1'); localStorage.clear(); });
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.restoreAllMocks(); });

const event = (ordinal: number) => ({ id: `calendar-${ordinal}`, course_id: null,
  title: `Calendar ${ordinal}`, description: null, event_type: 'lesson',
  starts_at: '2026-11-01T15:00:00Z', ends_at: null, is_published: true, cancelled_at: null });
const firstPage = () => Array.from({ length: 500 }, (_, ordinal) => event(ordinal));
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });

it('reads beyond500 in bounded pages and retains the real final event', async () => {
  const fetcher = vi.fn(async (input: string) => json(input.includes('offset=500') ? [event(500)] : firstPage()));
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  const rows = await calendarService.getCalendarEvents();
  expect(rows).toHaveLength(501);
  expect(rows.at(-1)?.id).toBe('calendar-500');
  expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
    '/api/v1/calendar?limit=500&offset=0', '/api/v1/calendar?limit=500&offset=500',
  ]);
});

it('uses an empty next page to terminate an exact500-record calendar', async () => {
  const fetcher = vi.fn(async (input: string) => json(input.includes('offset=500') ? [] : firstPage()));
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  expect(await calendarService.getCalendarEvents()).toHaveLength(500);
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it('does not report an empty/complete calendar or replay requests after a later-page429', async () => {
  let unavailable = true;
  const fetcher = vi.fn(async (input: string) => input.includes('offset=500')
    ? unavailable ? json({ detail: 'QA real rate window' }, 429) : json([event(500)])
    : json(firstPage()));
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  await expect(calendarService.getCalendarEvents()).rejects.toMatchObject({ status: 429 });
  await new Promise(resolve => setTimeout(resolve, 30));
  expect(fetcher).toHaveBeenCalledTimes(2);
  unavailable = false;
  expect(await calendarService.getCalendarEvents()).toHaveLength(501);
  expect(fetcher).toHaveBeenCalledTimes(3); // only explicit retry, cached successful page
});

it('does not put calendar data in a global cross-account localStorage cache', async () => {
  const fetcher = vi.fn(async () => json([event(1)]));
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  const { getCachedData, setApiAuthScope } = await import('./apiClient');
  setApiAuthScope('teacher-a');
  expect(await calendarService.getCalendarEvents()).toHaveLength(1);
  expect(localStorage.getItem('lms_calendar_events_cache')).toBeNull();
  expect(getCachedData('composed:/calendar')).toHaveLength(1);
  setApiAuthScope('teacher-b');
  expect(getCachedData('composed:/calendar')).toBeUndefined();
});

it('does not accept an ignored pagination cursor and loop forever', async () => {
  const fetcher = vi.fn(async () => json(firstPage()));
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  await expect(calendarService.getCalendarEvents()).rejects.toMatchObject({ code: 'INVALID_CALENDAR_PAGE' });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it('rejects duplicate records within a page instead of reporting a complete calendar', async () => {
  const fetcher = vi.fn(async () => json([event(1), event(1)]));
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  await expect(calendarService.getCalendarEvents()).rejects.toMatchObject({ code: 'INVALID_CALENDAR_PAGE' });
  expect(fetcher).toHaveBeenCalledTimes(1);
});
