import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { QuizPublishConfirmation, type QuizPublishConfirmationProps } from './QuizPublishConfirmation';

let root: Root, host: HTMLDivElement, opener: HTMLButtonElement;
const onCancel = vi.fn(), onConfirm = vi.fn();
const originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
const originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');
const defaults: QuizPublishConfirmationProps = {
  assessmentType: 'quiz', title: '  اختبار الكيمياء  ', academicYear: '1st_secondary',
  questionCount: 12, totalPoints: 27, startDate: '2026-10-07', startTime: '15:05',
  deadlineDate: '2026-10-08', deadlineTime: '6:30م', durationMinutes: 45,
  notifyStudents: true, busy: false, error: null, onCancel, onConfirm,
};
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  onCancel.mockReset(); onConfirm.mockReset();
  // jsdom cannot implement native focus containment/inertness. Browser QA
  // separately proves those semantics; these mocks only model open/close.
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function(this: HTMLDialogElement) { this.open = true; } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function(this: HTMLDialogElement) { this.open = false; } });
  opener = document.createElement('button'); document.body.append(opener); opener.focus();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove(); opener.remove();
  for (const [name, descriptor] of [['showModal', originalShowModal], ['close', originalClose]] as const) {
    if (descriptor) Object.defineProperty(HTMLDialogElement.prototype, name, descriptor);
    else Reflect.deleteProperty(HTMLDialogElement.prototype, name);
  }
  vi.unstubAllGlobals();
});
async function render(overrides: Partial<QuizPublishConfirmationProps> = {}) {
  await act(async () => root.render(<QuizPublishConfirmation {...defaults} {...overrides} />));
}
function button(text: string) { return [...host.querySelectorAll('button')].find(item => item.textContent === text)!; }
function value(label: string) { return [...host.querySelectorAll('dt')].find(item => item.textContent === label)!.nextElementSibling!.textContent; }

it('shows the quiz summary and Arabic 12-hour times without changing the draft', async () => {
  await render();
  expect(host.querySelector('dialog')?.getAttribute('aria-labelledby')).toBe('quiz-publish-heading');
  expect(value('العنوان:')).toBe('اختبار الكيمياء');
  expect(value('عدد الأسئلة والدرجات:')).toBe('12 سؤال (27 درجة)');
  expect(value('موعد البدء والنشر:')).toBe('2026-10-07 (03:05 م)');
  expect(value('موعد الإغلاق:')).toBe('2026-10-08 (06:30 م)');
  expect(value('مدة حل الاختبار:')).toBe('45 دقيقة');
  expect(value('إشعار الطلاب:')).toBe('✓ سيتم إرسال إشعار فوري');
  expect(defaults.title).toBe('  اختبار الكيمياء  ');
  expect(onConfirm).not.toHaveBeenCalled();
});
it('shows assignment semantics, no quiz duration and no notification when disabled', async () => {
  await render({ assessmentType: 'assignment', title: ' ', notifyStudents: false });
  expect(host.querySelector('h3')?.textContent).toBe('تأكيد رفع واعتماد الواجب');
  expect(value('العنوان:')).toBe('واجب جديد');
  expect(value('آخر موعد للتسليم:')).toBe('2026-10-08 (06:30 م)');
  expect(host.textContent).not.toContain('مدة حل الاختبار');
  expect(value('إشعار الطلاب:')).toBe('بدون إشعار');
});
it('renders untrusted titles and server errors as text, never HTML', async () => {
  const input = '<img src=x onerror="alert(1)">';
  await render({ title: input, error: input });
  expect(value('العنوان:')).toBe(input);
  expect(host.querySelector('[role="alert"]')?.textContent).toBe(input);
  expect(host.querySelector('img')).toBeNull();
});
it('does not invent a duration while the existing draft field is empty', async () => {
  await render({ durationMinutes: '' });
  expect(value('مدة حل الاختبار:')).toBe(' دقيقة');
  expect(onConfirm).not.toHaveBeenCalled();
});
it('delegates confirm, cancel, close and Escape to the existing lifecycle', async () => {
  await render();
  await act(async () => button('تأكيد الرفع والنشر الآن').click());
  expect(onConfirm).toHaveBeenCalledTimes(1);
  await act(async () => button('إلغاء').click());
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="إغلاق تأكيد النشر"]')!.click());
  const event = new Event('cancel', { bubbles: true, cancelable: true });
  await act(async () => host.querySelector('dialog')!.dispatchEvent(event));
  expect(event.defaultPrevented).toBe(true);
  expect(onCancel).toHaveBeenCalledTimes(3);
});
it('blocks all write/close actions while busy, including native Escape cancellation', async () => {
  await render({ busy: true });
  expect(host.querySelector('section')?.getAttribute('aria-busy')).toBe('true');
  expect(host.textContent).toContain('جاري الرفع والنشر...');
  const buttons = [...host.querySelectorAll('button')];
  expect(buttons).toHaveLength(3);
  expect(buttons.every(item => item.disabled)).toBe(true);
  await act(async () => {
    for (const item of buttons) item.click();
    host.querySelector('dialog')!.dispatchEvent(new Event('cancel', { bubbles: true, cancelable: true }));
  });
  expect(onCancel).not.toHaveBeenCalled(); expect(onConfirm).not.toHaveBeenCalled();
});
it('unlocks an existing dialog after a failure without replacing it or publishing again', async () => {
  await render({ busy: true });
  const dialog = host.querySelector('dialog');
  await render({ error: 'تعذّر النشر، حاول مرة أخرى.' });
  expect(host.querySelector('dialog')).toBe(dialog);
  expect(host.querySelector('[role="alert"]')?.textContent).toContain('تعذّر النشر');
  expect(button('تأكيد الرفع والنشر الآن').disabled).toBe(false);
  expect(onConfirm).not.toHaveBeenCalled();
});
it('restores the opening control on unmount', async () => {
  await render();
  button('إلغاء').focus();
  await act(async () => root.render(null));
  expect(document.activeElement).toBe(opener);
});
it.each([
  ['1st_secondary', 'الصف الأول الثانوي'], ['2nd_secondary', 'الصف الثاني الثانوي'], ['3rd_secondary', 'الصف الثالث الثانوي'],
] as const)('retains the selected academic year %s', async (academicYear, label) => {
  await render({ academicYear });
  expect(value('الصف الدراسي:')).toBe(label);
});
