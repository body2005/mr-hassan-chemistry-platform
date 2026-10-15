import { useEffect, useSyncExternalStore } from 'react';

const key = 'lms_display_scale';
const event = 'lms_display_scale_changed';
export const displaySizes = [90, 100, 110, 120] as const;
function read() {
  try {
    const value = Number(localStorage.getItem(key));
    return displaySizes.some(size => size === value) ? value : 100;
  } catch { return 100; }
}
function subscribe(listener: () => void) {
  window.addEventListener(event, listener);
  const stored = (change: StorageEvent) => { if (change.key === key || change.key === null) listener(); };
  window.addEventListener('storage', stored);
  return () => { window.removeEventListener(event, listener); window.removeEventListener('storage', stored); };
}
export function setDisplaySize(size: number) {
  if (!displaySizes.some(value => value === size)) return;
  try { localStorage.setItem(key, String(size)); } catch { return; }
  window.dispatchEvent(new Event(event));
}
export function useDisplaySize() {
  return useSyncExternalStore(subscribe, read, () => 100);
}
/** Browser layout zoom also scales fixed-pixel text while preserving its hierarchy. */
export function useApplyDisplaySize() {
  const size = useDisplaySize();
  useEffect(() => {
    document.documentElement.style.zoom = String(size / 100);
    return () => { document.documentElement.style.removeProperty('zoom'); };
  }, [size]);
}
