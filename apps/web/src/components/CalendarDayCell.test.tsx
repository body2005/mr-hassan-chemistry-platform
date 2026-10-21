import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { CalendarDayCell } from './CalendarDayCell';
import { calendarClock, calendarDay, sortCalendarEvents } from '../utils/calendarDay';
import type { CalendarScheduleEvent } from '../types/lms';

const event = (i: number): CalendarScheduleEvent => ({ id: `event-${i}`, academicYear: '1st_secondary',
  date: '2035-05-13', dayName: `موعد ${i}`, contentType: ['lesson', 'quiz', 'assignment', 'review'][i] as CalendarScheduleEvent['contentType'],
  time: `${i + 4}:30 م`, startsAt: `2035-05-13T${i + 13}:30:00Z` });
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function render(count: number, onOpen = vi.fn()) {
  await act(async () => root.render(<CalendarDayCell date="2035-05-13" day={13} weekday="الأحد"
    events={Array.from({ length: count }, (_, i) => event(i))} selected today onSelect={vi.fn()} onOpen={onOpen} />));
}
it.each([1, 2, 3, 4])('renders%s separately focusable regions and a legible day above them', async count => {
  await render(count);
  expect(host.querySelectorAll('button.calendar-event-segment')).toHaveLength(count);
  expect(host.querySelector('.calendar-cell-day')?.textContent).toBe('13');
  expect(host.querySelector('.is-today.is-selected')).not.toBeNull();
  expect(host.textContent).not.toContain('30');
});
it('uses the exact three nonoverlapping triangles and per-event time on focus', async () => {
  await render(3);
  const buttons = [...host.querySelectorAll('button')];
  expect(buttons.map(b => b.style.clipPath)).toEqual([
    'polygon(0% 0%, 50% 0%, 0% 100%)', 'polygon(50% 0%, 100% 100%, 0% 100%)', 'polygon(50% 0%, 100% 0%, 100% 100%)',
  ]);
  await act(async () => buttons[0].focus());
  expect(document.querySelector('[role="tooltip"]')?.textContent).toBe('درس · ٤:٣٠ م');
  expect(host.querySelector('[role="tooltip"]')).toBeNull(); // Portal escapes clipping ancestors.
  await act(async () => buttons[1].focus());
  expect(document.querySelector('[role="tooltip"]')?.textContent).toBe('اختبار · ٥:٣٠ م');
  await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
  expect(document.querySelector('[role="tooltip"]')).toBeNull();
});
it('shows time on touch without opening the editor and opens it on keyboard activation', async () => {
  const open = vi.fn(); await render(1, open);
  const button = host.querySelector('button')!;
  const touch = new Event('pointerdown', { bubbles: true }); Object.defineProperty(touch, 'pointerType', { value: 'touch' });
  await act(async () => { button.dispatchEvent(touch); button.click(); });
  expect(document.querySelector('[role="tooltip"]')?.textContent).toBe('درس · ٤:٣٠ م');
  expect(open).not.toHaveBeenCalled();
  await act(async () => { button.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); button.click(); });
  expect(open).toHaveBeenCalledWith(event(0));
  expect(document.querySelector('[role="tooltip"]')).toBeNull();
});
it('groups by Cairo day and sorts Arabic12-hour values numerically', () => {
  expect(calendarDay({ ...event(0), startsAt: '2035-05-12T21:30:00Z' })).toBe('2035-05-13');
  expect(calendarClock('١٢:٠٥ ص')).toBe('00:05');
  const events = [{ ...event(0), startsAt: undefined, time: '١٠:٣٠ ص' },
    { ...event(1), startsAt: undefined, time: '٩:١٥ ص' }];
  expect(sortCalendarEvents(events).map(e => e.id)).toEqual(['event-1', 'event-0']);
});

it('keeps same-color appointments separate and identifies each one by type and time', async () => {
  await act(async () => root.render(<CalendarDayCell date="2035-05-13" day={13} weekday="الأحد"
    events={[{ ...event(0), contentType: 'quiz' }, { ...event(1), contentType: 'quiz' }]}
    selected={false} today={false} onSelect={vi.fn()} onOpen={vi.fn()} />));
  expect(host.querySelector('.has-multiple-events')).not.toBeNull();
  const buttons = [...host.querySelectorAll<HTMLButtonElement>('.calendar-event-segment')];
  expect(buttons[0].style.background).toBe(buttons[1].style.background);
  expect(buttons[0].style.clipPath).not.toBe(buttons[1].style.clipPath);
  await act(async () => buttons[0].focus());
  expect(document.querySelector('[role="tooltip"]')?.textContent).toBe('اختبار · ٤:٣٠ م');
  await act(async () => buttons[1].focus());
  expect(document.querySelector('[role="tooltip"]')?.textContent).toBe('اختبار · ٥:٣٠ م');
});

it.each([0, 1])('selects with one mouse click and opens with double-click (%s events)', async count => {
  const open = vi.fn(); await render(count, open);
  const button = host.querySelector('button')!;
  await act(async () => button.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 1 })));
  expect(open).not.toHaveBeenCalled();
  await act(async () => {
    button.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 2 }));
    button.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 }));
  });
  expect(open).toHaveBeenCalledTimes(1);
  expect(open).toHaveBeenCalledWith(count ? event(0) : undefined);
});

it('opens on a second touch of the same region, while touching a different region only selects it', async () => {
  const open = vi.fn(); await render(2, open);
  const buttons = [...host.querySelectorAll('button')];
  const tap = async (index: number) => act(async () => {
    const touch = new Event('pointerdown', { bubbles: true }); Object.defineProperty(touch, 'pointerType', { value: 'touch' });
    buttons[index].dispatchEvent(touch); buttons[index].click();
  });
  await tap(0); await tap(1);
  expect(open).not.toHaveBeenCalled();
  await tap(1);
  expect(open).toHaveBeenCalledTimes(1);
  expect(open).toHaveBeenCalledWith(event(1));
});
