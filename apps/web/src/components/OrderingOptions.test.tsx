import { act, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { OrderingOptions } from './OrderingOptions';
import type { CourseOption } from '../types/quiz';

let host: HTMLDivElement, root: Root, latest: CourseOption[];
const initial = [{ key: 'x', text: 'First', is_correct: false }, { key: 'y', text: 'Second', is_correct: false }, { key: 'z', text: 'Third', is_correct: false }];
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); localStorage.clear();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove(); localStorage.clear(); vi.unstubAllGlobals();
  Reflect.deleteProperty(document, 'elementFromPoint');
});
async function render(editable = false, disabled = false) {
  function Probe() {
    const [items, setItems] = useState(initial); latest = items;
    return <OrderingOptions items={items} editable={editable} disabled={disabled} onChange={setItems} />;
  }
  await act(async () => root.render(<Probe />));
}
it('moves choices by keyboard while retaining item identities and boundaries', async () => {
  await render();
  const handle = host.querySelector<HTMLButtonElement>('button[aria-label^="اسحب الاختيار 1"]')!;
  await act(async () => handle.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })));
  expect(latest.map(item => item.key)).toEqual(['y', 'x', 'z']);
  expect(host.querySelector('[role="status"]')?.textContent).toContain('2');
  const up = host.querySelector<HTMLButtonElement>('button[aria-label="تحريك الاختيار 1 لأعلى"]')!;
  expect(up.disabled).toBe(true);
});
it.each(['touch', 'mouse'])('lifts, previews and then drops a choice using %s pointer events', async pointerType => {
  await render();
  const handle = host.querySelector<HTMLButtonElement>('button[aria-label^="اسحب الاختيار 1"]')!;
  const list = host.querySelector('ol')!;
  list.setPointerCapture = vi.fn(); list.hasPointerCapture = () => true; list.releasePointerCapture = vi.fn();
  let targetIndex = 1;
  Object.defineProperty(document, 'elementFromPoint', { configurable: true, value: () => host.querySelectorAll('li')[targetIndex] });
  const pointer = (name: string, y = 120) => {
    const event = new MouseEvent(name, { bubbles: true, button: 0, clientX: 10, clientY: y });
    Object.defineProperties(event, { pointerId: { value: 1 }, pointerType: { value: pointerType } });
    return event;
  };
  await act(async () => handle.dispatchEvent(pointer('pointerdown', 20)));
  expect(document.querySelector('.ordering-drag-ghost')?.textContent).toContain('First');
  expect(host.querySelector('.ordering-item--placeholder')?.getAttribute('data-drop-label')).toBe('ضع الاختيار هنا');
  // Replacing touch's implicit capture on the handle must not cancel the list capture.
  await act(async () => handle.dispatchEvent(pointer('lostpointercapture')));
  expect(document.querySelector('.ordering-drag-ghost')).not.toBeNull();
  await act(async () => list.dispatchEvent(pointer('pointermove')));
  expect(latest.map(item => item.key)).toEqual(['x', 'y', 'z']);
  expect([...host.querySelectorAll('li')].map(row => row.dataset.orderKey)).toEqual(['y', 'x', 'z']);
  targetIndex = 2;
  await act(async () => list.dispatchEvent(pointer('pointermove', 190)));
  await act(async () => list.dispatchEvent(pointer('pointerup')));
  expect(latest.map(item => item.key)).toEqual(['y', 'z', 'x']);
  expect(list.setPointerCapture).toHaveBeenCalledWith(1);
  expect(list.releasePointerCapture).toHaveBeenCalledWith(1);
  expect(document.querySelector('.ordering-drag-ghost')).toBeNull();
  expect(host.querySelector('.ordering-item--placeholder')).toBeNull();
});

it.each(['pointercancel', 'escape', 'outside'])('restores the initial order when a drag ends through %s', async reason => {
  await render();
  const list = host.querySelector('ol')!;
  list.setPointerCapture = vi.fn(); list.hasPointerCapture = () => true; list.releasePointerCapture = vi.fn();
  Object.defineProperty(document, 'elementFromPoint', { configurable: true, value: () => reason === 'outside' ? document.body : host.querySelectorAll('li')[2] });
  const event = (name: string, y: number) => {
    const result = new MouseEvent(name, { bubbles: true, button: 0, clientX: 10, clientY: y });
    Object.defineProperty(result, 'pointerId', { value: 1 }); return result;
  };
  await act(async () => host.querySelector('button')!.dispatchEvent(event('pointerdown', 20)));
  await act(async () => list.dispatchEvent(event('pointermove', 160)));
  if (reason === 'escape') await act(async () => list.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
  else await act(async () => list.dispatchEvent(event(reason === 'outside' ? 'pointerup' : 'pointercancel', 160)));
  expect(latest.map(item => item.key)).toEqual(['x', 'y', 'z']);
  expect([...host.querySelectorAll('li')].map(row => row.dataset.orderKey)).toEqual(['x', 'y', 'z']);
  expect(document.querySelector('.ordering-drag-ghost')).toBeNull();
});

it('commits the last pointer position when movement and release occur before a React render', async () => {
  await render();
  const list = host.querySelector('ol')!;
  list.setPointerCapture = vi.fn(); list.hasPointerCapture = () => true; list.releasePointerCapture = vi.fn();
  Object.defineProperty(document, 'elementFromPoint', { configurable: true, value: () => host.querySelectorAll('li')[2] });
  const event = (name: string, y: number) => {
    const result = new MouseEvent(name, { bubbles: true, button: 0, clientX: 10, clientY: y });
    Object.defineProperty(result, 'pointerId', { value: 1 }); return result;
  };
  await act(async () => host.querySelector('button')!.dispatchEvent(event('pointerdown', 20)));
  await act(async () => {
    list.dispatchEvent(event('pointermove', 180));
    list.dispatchEvent(event('pointerup', 180));
  });
  expect(latest.map(item => item.key)).toEqual(['y', 'z', 'x']);
});
it('adds and removes teacher choices without inventing text or changing surviving identities', async () => {
  await render(true);
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'إضافة اختيار')!.click());
  expect(latest).toHaveLength(4); expect(latest[3].text).toBe('');
  expect(latest[3].key).not.toBe('z');
  await act(async () => host.querySelector<HTMLButtonElement>('button[aria-label="حذف الاختيار 2"]')!.click());
  expect(latest.slice(0, 2).map(item => item.key)).toEqual(['x', 'z']);
});
it('localizes controls and does not allow moves while disabled', async () => {
  localStorage.setItem('lms_lang', 'en'); await render(false, true);
  expect(host.querySelector('ol')?.getAttribute('aria-label')).toBe('Ordering question choices');
  const move = host.querySelector<HTMLButtonElement>('button[aria-label="Move choice 1 down"]')!;
  expect(move.disabled).toBe(true); await act(async () => move.click());
  expect(latest.map(item => item.key)).toEqual(['x', 'y', 'z']);
});
