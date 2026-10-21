import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { installModalScrollLock } from './modalScrollLock';

let stop: (() => void) | undefined;
const settle = async () => { await Promise.resolve(); await Promise.resolve(); };
beforeEach(() => {
  document.body.innerHTML = '';
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  vi.stubGlobal('scrollX', 0); vi.stubGlobal('scrollY', 480);
});
afterEach(() => {
  stop?.(); stop = undefined;
  document.body.innerHTML = ''; document.body.removeAttribute('style');
  document.body.classList.remove('modal-open'); document.documentElement.classList.remove('modal-open');
  document.documentElement.removeAttribute('style');
  vi.restoreAllMocks(); vi.unstubAllGlobals();
});
function overlay(attributes = 'class="modal-overlay"') {
  const element = document.createElement('div');
  element.innerHTML = `<div ${attributes}><div style="overflow-y:auto;max-height:100px">Scrollable wizard</div></div>`;
  document.body.append(element);
  return element;
}

it('freezes the existing page position, keeps the wizard scrollable and restores prior styles on close', async () => {
  document.body.style.setProperty('overflow', 'auto', 'important');
  document.body.style.width = '92%';
  document.documentElement.style.scrollBehavior = 'smooth';
  stop = installModalScrollLock();
  const modal = overlay('role="dialog" aria-modal="true"'); await settle();
  expect(document.body.style.position).toBe('fixed');
  expect(document.body.style.top).toBe('-480px');
  expect(document.documentElement.classList.contains('modal-open')).toBe(true);
  expect(modal.querySelector<HTMLElement>('[style]')?.style.overflowY).toBe('auto');
  modal.remove(); await settle();
  expect(document.body.style.position).toBe('');
  expect(document.body.style.width).toBe('92%');
  expect(document.body.style.overflow).toBe('auto');
  expect(document.body.style.getPropertyPriority('overflow')).toBe('important');
  expect(document.documentElement.style.scrollBehavior).toBe('smooth');
  expect(window.scrollTo).toHaveBeenCalledWith(0, 480);
});

it('keeps the background locked until the final nested wizard closes', async () => {
  const first = overlay('data-modal-overlay="true"');
  stop = installModalScrollLock();
  const second = overlay('class="confirm-wizard-overlay"'); await settle();
  first.remove(); await settle();
  expect(document.body.style.position).toBe('fixed');
  expect(window.scrollTo).not.toHaveBeenCalled();
  second.remove(); await settle();
  expect(document.body.style.position).toBe('');
  expect(window.scrollTo).toHaveBeenCalledTimes(1);
});

it('ignores hidden overlays and closed native dialogs, and observes their opening and closing', async () => {
  const hidden = overlay('class="modal-overlay" hidden');
  const dialog = document.createElement('dialog'); dialog.setAttribute('aria-modal', 'true'); document.body.append(dialog);
  stop = installModalScrollLock();
  expect(document.body.style.position).toBe('');
  dialog.open = true; await settle();
  expect(document.body.style.position).toBe('fixed');
  dialog.open = false; await settle();
  expect(document.body.style.position).toBe('');
  hidden.querySelector('[hidden]')?.removeAttribute('hidden'); await settle();
  expect(document.body.style.position).toBe('fixed');
});
