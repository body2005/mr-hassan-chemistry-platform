import { afterEach, beforeEach, expect, it, vi } from 'vitest';

beforeEach(() => { vi.resetModules(); vi.stubEnv('VITE_API_URL', '/api/v1'); localStorage.clear(); });
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.restoreAllMocks(); });

const event = (ordinal: number) => ({ id: `calendar-${ordinal}`, course_id: null,
  title: `Calendar ${ordinal}`, description: null, event_type: 'lesson',
  starts_at: '2026-11-01T15:00:00Z', ends_at: null, is_published: true, cancelled_at: null });
const firstPage = () => Array.from({ length: 500 }, (_, ordinal) => event(ordinal));
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });

it('requires an explicit confirmation retry after the server reports a time conflict', async () => {
  const fetcher = vi.fn(async (_url: string, init?: RequestInit) => {
    if (!init?.method) return json([]);
    return JSON.parse(init.body as string).confirm_time_conflict ? json(event(1))
      : json({detail:'Conflict',error:{code:'CALENDAR_TIME_CONFLICT',message:'Conflict'}}, 409);
  });
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  const draft = {id:'evt_conflict', academicYear:'1st_secondary' as const, date:'2035-05-13',
    dayName:'درس', time:'06:00 م', contentType:'lesson' as const};
  await expect(calendarService.saveCalendarEvent(draft, {checkTimeConflict:true})).rejects.toMatchObject({code:'CALENDAR_TIME_CONFLICT'});
  expect(fetcher).toHaveBeenCalledTimes(1);
  await calendarService.saveCalendarEvent(draft, {checkTimeConflict:true,confirmTimeConflict:true});
  const writes = fetcher.mock.calls.filter(([, init]) => init?.method);
  expect(writes).toHaveLength(2);
  expect(JSON.parse(writes[1][1]!.body as string)).toMatchObject({check_time_conflict:true,confirm_time_conflict:true,idempotency_key:draft.id});
});

it('retains a deliberately blank optional description after a server reload', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => json([{ ...event(1),
    title: 'درس — الأحد', description: JSON.stringify({ dayDescription: '' }) }])));
  const { calendarService } = await import('./lmsService');
  expect((await calendarService.getCalendarEvents())[0].dayDescription).toBe('');
});

it('persists the same Cairo publication instant used for the notification and clears it for immediate mode', async () => {
  const fetcher = vi.fn(async (_input: string, init?: RequestInit) => json(init?.method ? event(1) : []));
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  const draft = { id: 'evt_scheduled-calendar', academicYear: '1st_secondary' as const,
    date: '2035-05-14', dayName: 'موعد مجدول', time: '06:00 م', contentType: 'lesson' as const,
    isPublishedToStudents: true, publishStartDate: '2035-05-13', publishStartTime: '٠٦:٣٠ م' };
  await calendarService.saveCalendarEvent(draft);
  await calendarService.saveCalendarEvent({ ...draft, publishStartDate: undefined, publishStartTime: undefined });
  const writes = fetcher.mock.calls.filter(([, init]) => init?.method);
  expect(JSON.parse(writes[0][1]!.body as string).publish_at).toBe('2035-05-13T15:30:00.000Z');
  expect(JSON.parse(writes[1][1]!.body as string).publish_at).toBeNull();
});

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

it('cancels only the selected event, retaining its same-day siblings', async () => {
  const fetcher = vi.fn(async (_input: string, init?: RequestInit) =>
    json(init?.method === 'POST' ? event(1) : [event(1), event(2)]));
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  expect(await calendarService.cancelCalendarEvent('calendar-1')).toHaveLength(2);
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST').map(([url]) => url))
    .toEqual(['/api/v1/calendar/calendar-1/cancel']);
});

it('saves a new same-day appointment with POST and preserves Arabic clock minutes on edit', async () => {
  const fetcher = vi.fn(async (_input: string, init?: RequestInit) => json(init?.method ? event(1) : [event(1), event(2)]));
  vi.stubGlobal('fetch', fetcher);
  const { calendarService } = await import('./lmsService');
  const draft = { id: 'evt_new-independent-event', academicYear: '1st_secondary' as const,
    date: '2035-05-13', dayName: 'Independent new lesson', time: '٩:٤٥ ص', contentType: 'lesson' as const };
  await calendarService.saveCalendarEvent(draft);
  const [, init] = fetcher.mock.calls.find(([, options]) => options?.method)!;
  expect(init?.method).toBe('POST');
  expect(JSON.parse(init!.body as string).starts_at).toBe('2035-05-13T06:45:00.000Z');
  expect(JSON.parse(init!.body as string).idempotency_key).toBe(draft.id);
});
