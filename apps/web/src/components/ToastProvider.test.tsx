import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ToastProvider, ToastRegion, useToast, noticeDuration } from './ToastProvider';

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

it('keeps deduplicated warnings in the action region until explicitly dismissed', async () => {
  await render(); await click('تحذير'); await click('تحذير');
  await act(async () => vi.advanceTimersByTime(60000));
  expect(host.querySelectorAll('.toast-item')).toHaveLength(1);
  expect(host.querySelector('.action-feedback-region .toast-warning')).not.toBeNull();
  expect(host.querySelectorAll('[role="status"]')).toHaveLength(1);
  expect(host.querySelector('[role="alert"]')).toBeNull();
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="إغلاق الرسالة"]')!.click());
  expect(host.querySelector('.toast-item')).toBeNull();
});
it('gives notices reading time and queues them without covering the action', async () => {
  await render(); await click('نجاح'); await click('معلومة');
  expect(host.querySelectorAll('.toast-item')).toHaveLength(1);
  await act(async () => vi.advanceTimersByTime(2000));
  expect(host.querySelector('.toast-item')!.textContent).toContain('تم الحفظ');
  await act(async () => vi.advanceTimersByTime(2500));
  expect(host.querySelector('.toast-item')!.textContent).toContain('تم تحديث البيانات');
  await act(async () => vi.advanceTimersByTime(4500));
  expect(host.querySelector('.toast-item')).toBeNull();
  expect(noticeDuration('ق'.repeat(200))).toBe(14000);
  expect(noticeDuration('تم')).toBe(4500);
});
it('cleans up feedback from a departed action region', async () => {
  await render(); await click('تحذير'); await render(false);
  expect(host.querySelector('.toast-item')).toBeNull();
});
it('does not announce an empty or already dismissed action beside page loading status', async () => {
  await render();
  expect(host.querySelectorAll('[role="status"]')).toHaveLength(0);
  await click('تحذير');
  expect(host.querySelectorAll('[role="status"]')).toHaveLength(1);
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="إغلاق الرسالة"]')!.click());
  expect(host.querySelectorAll('[role="status"]')).toHaveLength(0);
});

it('places feedback inside the open overlay and removes it when that action closes', async () => {
  function Screen({ overlay }: { overlay: boolean }) {
    const toast = useToast();
    return <><ToastRegion label="رسائل المقرر" />{overlay && <section>
      <ToastRegion label="رسائل الواجب" />
      <button onClick={() => toast('تعذر تحميل ورقة الواجب', 'danger')}>تحميل</button>
    </section>}</>;
  }
  await act(async () => root.render(<ToastProvider><Screen overlay /></ToastProvider>));
  await click('تحميل');
  expect(host.querySelector('[aria-label="رسائل الواجب"] .toast-text')?.textContent).toBe('تعذر تحميل ورقة الواجب');
  expect(host.querySelector('[aria-label="رسائل المقرر"] .toast-item')).toBeNull();
  await act(async () => root.render(<ToastProvider><Screen overlay={false} /></ToastProvider>));
  expect(host.querySelector('.toast-item')).toBeNull();
  expect(host.querySelector('[role="status"]')).toBeNull();
});
