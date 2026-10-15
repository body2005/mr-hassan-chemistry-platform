import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { DisplaySettings } from './DisplaySettings';
import { ScheduleBadges } from './ScheduleBadges';
import { useApplyDisplaySize } from '../services/displaySize';

let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); localStorage.clear();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); localStorage.clear(); vi.unstubAllGlobals(); });
function Preferences() { useApplyDisplaySize(); return <DisplaySettings lang="ar" />; }
it('persists a site display size and restores it after a reload/remount', async () => {
  await act(async () => root.render(<Preferences />));
  const select = host.querySelector('select')!;
  await act(async () => { select.value = '120'; select.dispatchEvent(new Event('change', { bubbles: true })); });
  expect(document.documentElement.style.zoom).toBe('1.2');
  expect(localStorage.getItem('lms_display_scale')).toBe('120');
  await act(async () => root.unmount()); root = createRoot(host);
  await act(async () => root.render(<Preferences />));
  expect(host.querySelector('select')?.value).toBe('120');
  expect(document.documentElement.style.zoom).toBe('1.2');
});
it('ignores invalid saved display sizes and syncs a valid change from another tab', async () => {
  localStorage.setItem('lms_display_scale', '-100');
  await act(async () => root.render(<Preferences />));
  expect(document.documentElement.style.zoom).toBe('1');
  await act(async () => { localStorage.setItem('lms_display_scale', '90'); window.dispatchEvent(new StorageEvent('storage', { key: 'lms_display_scale' })); });
  expect(host.querySelector('select')?.value).toBe('90');
});
it('shows real start/end dates and the actual availability window without inventing dates', async () => {
  await act(async () => root.render(<ScheduleBadges startsAt="2026-10-15T08:00:00Z" endsAt="2026-10-15T10:30:00Z" />));
  expect([...host.querySelectorAll('time')].map(item => item.dateTime)).toEqual(['2026-10-15T08:00:00.000Z', '2026-10-15T10:30:00.000Z']);
  expect(host.querySelector('small')?.textContent).toContain('مدة الإتاحة');
  await act(async () => root.render(<ScheduleBadges startsAt="invalid" />));
  expect(host.textContent).toBe('');
});
