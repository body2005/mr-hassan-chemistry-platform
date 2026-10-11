import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ToastProvider } from '../components/ToastProvider';
import { PaymentView } from './PaymentView';
import { PaymentManagementView } from './PaymentManagementView';
import { apiUrl, clearApiCache, markBrowserSessionActive, setApiAuthScope, setCachedData } from '../services/apiClient';
import { realtimeService } from '../services/realtimeService';
import type { PaymentOrder } from '../services/paymentService';
import type { StudentProfile } from '../types/lms';

vi.mock('../components/ConfirmWizard', () => ({ useConfirm: () => vi.fn() }));

const student: StudentProfile = {
  id: 'qa-payment-owner', name: 'QA Student', email: 'payment@example.test', role: 'student',
  nationalId: '', studentPhone: '', guardianPhone: '', age: 17, academicYear: '1st_secondary',
  academicYearLabel: '', interestedSubjects: [], joinedDate: '',
};
const pending: PaymentOrder = {
  id: 'qa-order', student_id: student.id, product_type: 'lesson', product_id: 'qa-lesson',
  product_name: 'QA Paid Lesson', amount_egp: 25, payment_method: 'instapay', status: 'pending',
  has_receipt: false, created_at: '2026-10-08T00:00:00Z',
};
let host: HTMLDivElement, root: Root, orders: PaymentOrder[], orderReads: number, failOrders: boolean;
let sources: Array<{ onopen?: () => void }>;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  clearApiCache(); setApiAuthScope(student.id, true); markBrowserSessionActive(true);
  orders = [{ ...pending }]; orderReads = 0; failOrders = false; sources = [];
  class ObservedEventSource {
    static OPEN = 1;
    readyState = 1;
    onopen?: () => void;
    constructor() { sources.push(this); }
    addEventListener() {}
    close() { this.readyState = 2; }
  }
  vi.stubGlobal('EventSource', ObservedEventSource);
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith('/payments/config')) return Response.json({ currency: 'EGP', methods: [] });
    if (path.endsWith('/payments/me/entitlements')) return Response.json([]);
    if (path.endsWith('/auth/me')) return Response.json({ id: student.id });
    if (path.endsWith('/payments/me/orders')) {
      orderReads++;
      return failOrders
        ? Response.json({ detail: 'QA payment read unavailable' }, { status: 503 })
        : Response.json(orders);
    }
    if (path.endsWith('/payments/orders')) {
      orderReads++;
      return failOrders
        ? Response.json({ detail: 'QA payment read unavailable' }, { status: 503 })
        : Response.json(orders);
    }
    throw new Error(`Unexpected payment test path: ${path}`);
  }));
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  realtimeService.disconnect();
  await act(async () => root.unmount()); host.remove(); clearApiCache(); vi.unstubAllGlobals();
});
async function render() {
  await act(async () => root.render(<ToastProvider><PaymentView courses={[]} currentUser={student} /></ToastProvider>));
}
async function refresh() {
  await act(async () => host.querySelector<HTMLButtonElement>('button[aria-label="تحديث"]')!.click());
}
async function renderManager() {
  await act(async () => root.render(<ToastProvider><PaymentManagementView courses={[]} onCoursesChanged={() => undefined} /></ToastProvider>));
}
function rejected() { orders = [{ ...pending, status: 'rejected', review_note: 'QA rejection' }]; }

it('updates the actual payment history after a review hint without fabricating access', async () => {
  await render(); expect(host.textContent).toContain('بانتظار رفع الإيصال');
  rejected();
  await act(async () => window.dispatchEvent(new CustomEvent('lms_payment_updated', { detail: orders[0] })));
  expect(host.textContent).toContain('مرفوض');
  expect(host.textContent).not.toContain('هذا الدرس تم شراؤه');
  expect(orderReads).toBe(2);
});
it('reconciles a missed review from authoritative reads when SSE reconnects, not cached pending state', async () => {
  await render(); expect(orderReads).toBe(1); rejected();
  const unlock = vi.fn(); window.addEventListener('lms_lesson_unlocked', unlock);
  try {
    await act(async () => realtimeService.connect());
    await vi.waitFor(() => expect(sources).toHaveLength(1));
    await act(async () => sources[0].onopen?.());
    expect(host.textContent).toContain('مرفوض'); expect(orderReads).toBe(2);
    expect(unlock).not.toHaveBeenCalled();
  } finally { window.removeEventListener('lms_lesson_unlocked', unlock); }
});
it('manual refresh bypasses the payment TTL cache immediately', async () => {
  await render(); setCachedData(`GET:${apiUrl('/payments/me/orders')}`, [{ ...pending }], 15_000);
  rejected(); await refresh();
  expect(orderReads).toBe(2); expect(host.textContent).toContain('مرفوض');
});
it('does not resurrect the old pending cache when the payment view is reopened after manual refresh', async () => {
  await render(); rejected(); await refresh();
  expect(host.textContent).toContain('مرفوض');
  await act(async () => root.render(null));
  await render();
  expect(host.textContent).toContain('مرفوض'); expect(orderReads).toBe(3);
});
it('shows a failed initial payment read honestly and recovers only on explicit retry', async () => {
  failOrders = true; await render();
  expect(host.querySelector('[role="alert"]')?.textContent).toContain('QA payment read unavailable');
  expect(host.textContent).not.toContain('لا توجد وسائل دفع مفعلة');
  expect(host.textContent).not.toContain('لا توجد طلبات دفع'); expect(orderReads).toBe(1);
  failOrders = false; rejected(); await refresh();
  expect(host.querySelector('[role="alert"]')).toBeNull();
  expect(host.textContent).toContain('مرفوض'); expect(orderReads).toBe(2);
});
it('teacher receives new orders in the already-mounted review list', async () => {
  orders = []; await renderManager(); expect(host.textContent).toContain('لا توجد طلبات');
  orders = [{ ...pending }];
  await act(async () => window.dispatchEvent(new CustomEvent('lms_payment_updated', { detail: pending })));
  expect(host.textContent).toContain(pending.product_name); expect(orderReads).toBe(2);
});
it('teacher manual refresh does not reuse the stale list TTL cache', async () => {
  await renderManager(); setCachedData(`GET:${apiUrl('/payments/orders')}`, [{ ...pending }], 15_000);
  rejected(); await refresh();
  expect(host.querySelector('.review-amount')?.textContent).toContain('rejected'); expect(orderReads).toBe(2);
});
it('teacher sees a failed read instead of a fabricated empty review list, then can retry', async () => {
  failOrders = true; await renderManager();
  expect(host.querySelector('[role="alert"]')?.textContent).toContain('QA payment read unavailable');
  expect(host.textContent).not.toContain('لا توجد طلبات'); expect(orderReads).toBe(1);
  failOrders = false; await refresh();
  expect(host.querySelector('[role="alert"]')).toBeNull();
  expect(host.textContent).toContain(pending.product_name); expect(orderReads).toBe(2);
});
for (const manager of [false, true]) it(`${manager ? 'teacher' : 'student'} ignores a delayed older read after a newer review and reopening`, async () => {
  const original = vi.mocked(fetch).getMockImplementation()!;
  let release: ((response: Response) => void) | undefined;
  const path = manager ? '/payments/orders' : '/payments/me/orders';
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    if (String(input).endsWith(path) && !release) {
      orderReads++;
      return new Promise<Response>(resolve => { release = resolve; });
    }
    return original(input);
  }));
  const mount = manager ? renderManager : render;
  await mount(); expect(release).toBeDefined(); rejected();
  await act(async () => window.dispatchEvent(new CustomEvent('lms_payment_updated', { detail: orders[0] })));
  expect(host.textContent).toContain(manager ? 'rejected' : 'مرفوض');
  await act(async () => release!(Response.json([{ ...pending }])));
  expect(host.textContent).toContain(manager ? 'rejected' : 'مرفوض');
  await act(async () => root.render(null)); await mount();
  expect(host.textContent).toContain(manager ? 'rejected' : 'مرفوض'); expect(orderReads).toBe(3);
});
