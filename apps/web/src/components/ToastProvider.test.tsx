import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { reportRequestError } from '../services/errorFeedback';
import { ToastProvider, ToastRegion, useToast, noticeDuration } from './ToastProvider';
import { AccessibleDialog } from './AccessibleDialog';

let host: HTMLDivElement, root: Root;
function Action({ visible = true }: { visible?: boolean }) {
  const toast = useToast();
  return <section>{visible && <ToastRegion />}
    <button onClick={() => toast('لا تعِد نشر المحتوى؛ أعد محاولة إرسال الإشعار.', 'warning')}>تحذير</button>
    <button onClick={() => toast('تم الحفظ', 'success')}>نجاح</button>
    <button onClick={() => toast('تم تحديث البيانات', 'info')}>معلومة</button>
  </section>;
}
async function render(visible = true) { await act(async () => root.render(<ToastProvider><Action visible={visible} /></ToastProvider>)); }
async function click(text: string) { await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === text)!.click()); }
beforeEach(() => {
  vi.useFakeTimers(); vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it('keeps deduplicated warnings in one global host until explicitly dismissed', async () => {
  await render(); await click('تحذير'); await click('تحذير');
  await act(async () => vi.advanceTimersByTime(60000));
  expect(document.body.querySelectorAll('.toast-item')).toHaveLength(1);
  expect(host.querySelector('.toast-stack')).toBeNull();
  expect(document.body.querySelector('.toast-stack .toast-warning')).not.toBeNull();
  expect(document.body.querySelectorAll('[role="status"]')).toHaveLength(1);
  expect(host.querySelector('[role="alert"]')).toBeNull();
  await act(async () => document.body.querySelector<HTMLButtonElement>('[aria-label="إغلاق الرسالة"]')!.click());
  expect(document.body.querySelector('.toast-item')).toBeNull();
});
it('gives notices reading time and queues them without covering the action', async () => {
  await render(); await click('نجاح'); await click('معلومة');
  expect(document.body.querySelectorAll('.toast-item')).toHaveLength(1);
  await act(async () => vi.advanceTimersByTime(2000));
  expect(document.body.querySelector('.toast-item')!.textContent).toContain('تم الحفظ');
  await act(async () => vi.advanceTimersByTime(2500));
  expect(document.body.querySelector('.toast-item')!.textContent).toContain('تم تحديث البيانات');
  await act(async () => vi.advanceTimersByTime(4500));
  expect(document.body.querySelector('.toast-item')).toBeNull();
  expect(noticeDuration('ق'.repeat(200))).toBe(14000);
  expect(noticeDuration('تم')).toBe(4500);
});
it('keeps errors visible across page and action-region changes', async () => {
  await render(); await click('تحذير'); await render(false);
  expect(document.body.querySelector('.toast-item')).not.toBeNull();
});
it('clears the previous account notices and delayed request errors on account change', async () => {
  await render(); await click('تحذير'); await click('نجاح');
  await act(async () => reportRequestError(new Error('Previous account request')));
  await act(async () => window.dispatchEvent(new Event('lms_auth_scope_updated')));
  expect(document.body.querySelector('.toast-item')).toBeNull();
  expect(document.body.querySelector('[role="status"]')).toBeNull();
  await act(async () => vi.advanceTimersByTime(60000));
  expect(document.body.textContent).not.toContain('Previous account request');
  await click('معلومة');
  expect(document.body.querySelector('.toast-item')?.textContent).toContain('تم تحديث البيانات');
});
it('does not announce an empty or already dismissed action beside page loading status', async () => {
  await render();
  expect(document.body.querySelectorAll('[role="status"]')).toHaveLength(0);
  await click('تحذير');
  expect(document.body.querySelectorAll('[role="status"]')).toHaveLength(1);
  await act(async () => document.body.querySelector<HTMLButtonElement>('[aria-label="إغلاق الرسالة"]')!.click());
  expect(document.body.querySelectorAll('[role="status"]')).toHaveLength(0);
});

it('keeps one viewport host outside overlays even when the overlay closes', async () => {
  function Screen({ overlay }: { overlay: boolean }) {
    const toast = useToast();
    return <><ToastRegion label="رسائل المقرر" />{overlay && <section>
      <ToastRegion label="رسائل الواجب" />
      <button onClick={() => toast('تعذر تحميل ورقة الواجب', 'danger')}>تحميل</button>
    </section>}</>;
  }
  await act(async () => root.render(<ToastProvider><Screen overlay /></ToastProvider>));
  await click('تحميل');
  expect(document.body.querySelector('.toast-text')?.textContent).toBe('تعذر تحميل ورقة الواجب');
  expect(host.querySelector('[aria-label="رسائل المقرر"] .toast-item')).toBeNull();
  await act(async () => root.render(<ToastProvider><Screen overlay={false} /></ToastProvider>));
  expect(document.body.querySelectorAll('.toast-stack')).toHaveLength(1);
  expect(document.body.querySelector('.toast-item')).not.toBeNull();
});

it('provides a foreground request error fallback but prefers the action recovery message', async () => {
  await render();
  await act(async () => reportRequestError(new Error('فشل النشر')));
  await act(async () => vi.advanceTimersByTime(100));
  expect(document.body.querySelector('.toast-danger')?.textContent).toContain('فشل النشر');
  await act(async () => reportRequestError(new Error('Generic failure')));
  await click('تحذير');
  await act(async () => vi.advanceTimersByTime(100));
  expect(document.body.textContent).not.toContain('Generic failure');
  await act(async () => reportRequestError(Object.assign(new Error('Cancelled'), { code: 'REQUEST_CANCELLED' })));
  await act(async () => vi.advanceTimersByTime(100));
  expect(document.body.textContent).not.toContain('Cancelled');
});

it('shows background upload errors globally and keeps simultaneous failures', async () => {
  await render();
  await act(async () => {
    window.dispatchEvent(new CustomEvent('lms_toast_notification', { detail: { message: 'فشل رفع المذكرة', tone: 'danger' } }));
    reportRequestError(new Error('فشل الحفظ'));
    reportRequestError(new Error('فشل النشر'));
  });
  await act(async () => vi.advanceTimersByTime(100));
  expect(document.body.querySelectorAll('.toast-danger')).toHaveLength(3);
  expect(document.body.querySelector('.toast-text')?.textContent).toBe('فشل رفع المذكرة');
});

it('keeps errors accessible above a native modal and preserves them after closing it', async () => {
  const show = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
  const close = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function(this: HTMLDialogElement) { this.open = true; } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function(this: HTMLDialogElement) { this.open = false; } });
  function Screen({ open }: { open: boolean }) {
    const toast = useToast();
    return open && <AccessibleDialog labelledBy="test-title" onClose={() => {}}>
      <h2 id="test-title">تأكيد النشر</h2><button onClick={() => toast('تعذر النشر', 'danger')}>تأكيد</button>
    </AccessibleDialog>;
  }
  try {
    await act(async () => root.render(<ToastProvider><Screen open /></ToastProvider>));
    await click('تأكيد');
    expect(host.querySelector('dialog .toast-danger')?.textContent).toContain('تعذر النشر');
    expect(host.querySelector('dialog [role="status"]')).not.toBeNull();
    await act(async () => root.render(<ToastProvider><Screen open={false} /></ToastProvider>));
    expect(document.body.querySelectorAll('.toast-stack')).toHaveLength(1);
    expect(document.body.querySelector('.toast-danger')?.textContent).toContain('تعذر النشر');
    expect(host.querySelector('.toast-stack')).toBeNull();
  } finally {
    if (show) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', show); else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
    if (close) Object.defineProperty(HTMLDialogElement.prototype, 'close', close); else Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
  }
});
