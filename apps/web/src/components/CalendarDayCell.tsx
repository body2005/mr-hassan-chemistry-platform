import { useEffect, useLayoutEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { CalendarScheduleEvent } from '../types/lms';
import { CALENDAR_TYPES, calendarEventTime } from '../utils/calendarDay';
import './CalendarDayCell.css';

// Points cover the entire cell. CSS clip-path also clips each button's hit area.
const partitions = [
  ['0,0 100,0 100,100 0,100'],
  ['0,0 50,0 50,100 0,100', '50,0 100,0 100,100 50,100'],
  ['0,0 50,0 0,100', '50,0 100,100 0,100', '50,0 100,0 100,100'],
  ['0,0 50,0 50,50 0,50', '50,0 100,0 100,50 50,50',
    '0,50 50,50 50,100 0,100', '50,50 100,50 100,100 50,100'],
];
const anchors = [
  [[.5, .5]], [[.25, .5], [.75, .5]],
  [[1 / 6, 1 / 3], [.5, 2 / 3], [5 / 6, 1 / 3]],
  [[.25, .25], [.75, .25], [.25, .75], [.75, .75]],
];

export function CalendarDayCell({ date, day, weekday, events, selected, today, onSelect, onOpen, lang = 'ar' }: {
  date: string; day: number; weekday: string; events: CalendarScheduleEvent[];
  selected: boolean; today: boolean; onSelect: () => void;
  onOpen: (event?: CalendarScheduleEvent) => void; lang?: string;
}) {
  const id = useId();
  const cell = useRef<HTMLDivElement>(null);
  const tooltip = useRef<HTMLDivElement>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pointerType = useRef('mouse');
  const [active, setActive] = useState<number | null>(null);
  const [position, setPosition] = useState({ left: 0, top: 0, arrow: 40, below: false });
  const visible = events.slice(0, 4);
  const points = partitions[Math.max(0, visible.length - 1)];
  const clearHide = () => clearTimeout(hideTimer.current);
  const show = (index: number) => { clearHide(); setActive(index); };
  const hideSoon = () => { clearHide(); hideTimer.current = setTimeout(() => {
    if (!cell.current?.contains(document.activeElement)) setActive(null);
  }, 120); };

  useEffect(() => () => clearTimeout(hideTimer.current), []);
  useLayoutEffect(() => {
    if (active === null) return;
    if (!events[active]) { setActive(null); return; }
    const place = () => {
      const rect = cell.current!.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > window.innerHeight) { setActive(null); return; }
      const [x] = anchors[Math.min(events.length, 4) - 1][active];
      const anchorX = rect.left + rect.width * x;
      const width = tooltip.current?.offsetWidth || 100, height = tooltip.current?.offsetHeight || 32;
      const left = Math.max(8, Math.min(anchorX - width / 2, window.innerWidth - width - 8));
      const below = rect.top - height - 10 < 8;
      setPosition({ left, top: Math.max(8, Math.min(below ? rect.bottom + 10 : rect.top - height - 10,
        window.innerHeight - height - 8)), arrow: Math.max(8, Math.min(anchorX - left, width - 8)), below });
    };
    place();
    const dismiss = (e: Event) => {
      if (e.type === 'keydown' && (e as KeyboardEvent).key !== 'Escape') return;
      if (e.type === 'pointerdown' && (cell.current?.contains(e.target as Node) || tooltip.current?.contains(e.target as Node))) return;
      setActive(null);
    };
    document.addEventListener('pointerdown', dismiss);
    document.addEventListener('keydown', dismiss);
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => {
      document.removeEventListener('pointerdown', dismiss);
      document.removeEventListener('keydown', dismiss);
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    };
  }, [active, events]);

  return <div ref={cell} className={`calendar-cell calendar-day-cell${visible.length ? ' has-events' : ''}${selected ? ' is-selected' : ''}${today ? ' is-today' : ''}`}
    role="group" aria-label={`${weekday} ${date}${today ? ' — اليوم' : ''}${selected ? ' — اليوم المحدد' : ''}`} data-date={date}>
    {visible.length ? visible.map((event, index) => <button key={event.id} type="button"
      className="calendar-event-segment" data-event-id={event.id}
      style={{ background: CALENDAR_TYPES[event.contentType].color,
        clipPath: `polygon(${points[index].split(' ').map(p => p.split(',').map(v => `${v}%`).join(' ')).join(', ')})` }}
      aria-label={`${event.dayName} — ${CALENDAR_TYPES[event.contentType].label} — ${date}`}
      aria-describedby={active === index ? id : undefined}
      onPointerDown={e => { pointerType.current = e.pointerType; }}
      onPointerEnter={e => { if (e.pointerType !== 'touch') show(index); }} onPointerLeave={e => { if (e.pointerType !== 'touch') hideSoon(); }}
      onFocus={() => show(index)} onBlur={hideSoon}
      onClick={() => {
        onSelect();
        if (pointerType.current === 'touch') show(index);
        else { setActive(null); onOpen(event); }
        pointerType.current = 'mouse';
      }} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') pointerType.current = 'keyboard'; }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <polygon points={points[index]} />
      </svg>
    </button>) : <button type="button" className="calendar-empty-day-button" aria-label={`${weekday} ${date}`}
      aria-pressed={selected} onClick={() => { onSelect(); onOpen(); }} />}
    <span className="calendar-day-caption" aria-hidden="true"><span className="calendar-cell-weekday">{weekday}</span>
      <span className="calendar-cell-day">{day}</span></span>
    {active !== null && visible[active] && createPortal(<div ref={tooltip} id={id} role="tooltip"
      className={`calendar-time-tooltip${position.below ? ' below' : ''}`}
      style={{ left: position.left, top: position.top }} onPointerEnter={clearHide} onPointerLeave={hideSoon}>
      {calendarEventTime(visible[active], lang)}<span className="calendar-tooltip-arrow" style={{ left: position.arrow }} />
    </div>, document.body)}
  </div>;
}
