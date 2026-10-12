import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LessonScheduleFields } from './LessonScheduleFields';

beforeEach(() => vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true));
afterEach(() => vi.unstubAllGlobals());

it('requires a complete start while allowing an open-ended lesson', async () => {
  const host = document.createElement('form');
  const root = createRoot(host);
  const props = { start: '', end: '', announce: false, onStart: () => {}, onEnd: () => {}, onAnnounce: () => {} };
  try {
    await act(async () => root.render(<LessonScheduleFields {...props} />));
    expect(host.checkValidity()).toBe(false);
    await act(async () => root.render(<LessonScheduleFields {...props} start="2026-10-14T18:00" />));
    expect(host.checkValidity()).toBe(true);
    await act(async () => root.render(<LessonScheduleFields {...props} start="2026-10-14T" />));
    expect(host.checkValidity()).toBe(false);
  } finally { await act(async () => root.unmount()); }
});

it('requires both end fields only when an end boundary is supplied', async () => {
  const host = document.createElement('form');
  const root = createRoot(host);
  const props = { start: '2026-10-14T18:00', announce: true, onStart: () => {}, onEnd: () => {}, onAnnounce: () => {} };
  try {
    for (const end of ['2026-10-15T', 'T19:00']) {
      await act(async () => root.render(<LessonScheduleFields {...props} end={end} />));
      expect(host.checkValidity()).toBe(false);
    }
    await act(async () => root.render(<LessonScheduleFields {...props} end="2026-10-15T19:00" />));
    expect(host.checkValidity()).toBe(true);
  } finally { await act(async () => root.unmount()); }
});
