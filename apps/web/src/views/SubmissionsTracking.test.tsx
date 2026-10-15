import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { SubmissionsView } from './SubmissionsView';

const mocks = vi.hoisted(() => ({ request: vi.fn(), students: vi.fn(), toast: vi.fn(), scope: 'teacher-a', generation: 1 }));
vi.mock('../services/apiClient', () => ({
  apiRequest: mocks.request, getCachedData: () => null, invalidateApiCache: () => {},
  getApiAuthScope: () => mocks.scope, getApiAuthGeneration: () => mocks.generation,
}));
vi.mock('../services/lmsService', () => ({
  submissionService: { getTeacherSubmissions: async () => [] },
  userService: { getStudents: mocks.students },
}));
vi.mock('../components/ToastProvider', () => ({ useToast: () => mocks.toast }));
vi.mock('../components/AssignmentModal', () => ({ AssignmentModal: () => null }));
vi.mock('../components/ExamGradingModal', () => ({ ExamGradingModal: () => null }));
vi.mock('../components/StudentDetailWizard', () => ({ StudentDetailWizard: () => null }));
vi.mock('../utils/exportEngine', () => ({ exportToDocx: vi.fn(), exportToExcel: vi.fn(), exportToPrintPdf: vi.fn() }));

const definition = { id: 'column-one', name: 'Guardian note', data_type: 'text', academic_year: '1st_secondary', table_context: 'submissions', created_at: '2026-10-15' };
let saved = { columns: [definition], values: { student: { 'column-one': 'Called guardian' } } };
let host: HTMLDivElement, root: Root;
async function render() { await act(async () => root.render(<SubmissionsView />)); }
const cell = () => host.querySelector<HTMLInputElement>('input[aria-label="Guardian note — Student"]');
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  mocks.scope = 'teacher-a'; mocks.generation = 1;
  mocks.students.mockResolvedValue([{ id: 'student', display_name: 'Student', email: 'student@test', is_active: true }]);
  saved = { columns: [definition], values: { student: { 'column-one': 'Called guardian' } } };
  mocks.toast.mockReset();
  mocks.request.mockReset().mockImplementation(async (_path: string, init?: RequestInit) => {
    if (init?.method === 'PUT') { saved.values.student['column-one'] = JSON.parse(String(init.body)).value; return { value: saved.values.student['column-one'] }; }
    return structuredClone(saved);
  });
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function editCell(value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(cell()!, value);
    cell()!.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
it('hydrates saved definitions and values and preserves them after grade events and remount/login', async () => {
  await render(); expect(cell()?.value).toBe('Called guardian');
  await act(async () => { window.dispatchEvent(new Event('lms_submission_graded')); await new Promise(resolve => setTimeout(resolve, 350)); });
  expect(cell()?.value).toBe('Called guardian');
  await act(async () => root.unmount()); root = createRoot(host); await render();
  expect(cell()?.value).toBe('Called guardian');
  mocks.scope = 'anonymous'; mocks.generation++;
  await act(async () => window.dispatchEvent(new Event('lms_auth_scope_updated')));
  expect(cell()).toBeNull();
  mocks.scope = 'teacher-a'; mocks.generation++;
  await act(async () => window.dispatchEvent(new Event('lms_auth_scope_updated')));
  expect(cell()?.value).toBe('Called guardian');
});
it('ignores a former teacher late hydration after account switch', async () => {
  let finish!: (value: typeof saved) => void;
  mocks.request.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; })).mockResolvedValue({ columns: [], values: {} });
  await render(); expect(mocks.request).toHaveBeenCalled(); mocks.scope = 'teacher-b'; mocks.generation++;
  await act(async () => window.dispatchEvent(new Event('lms_auth_scope_updated')));
  await act(async () => finish(saved));
  expect(host.textContent).not.toContain('Guardian note');
});
it('reports failed hydration and provides an actual retry', async () => {
  mocks.request.mockRejectedValueOnce(new Error('offline'));
  await render();
  expect(host.textContent).toContain('تعذر تحميل الأعمدة المخصصة');
  const retry = [...host.querySelectorAll('button')].find(button => button.textContent === 'إعادة تحميل المتابعة');
  expect(retry).toBeDefined();
  await act(async () => retry!.click()); expect(cell()?.value).toBe('Called guardian');
});
it('saves a changed cell only after API acknowledgement and restores it on remount', async () => {
  await render(); await editCell('Updated note');
  expect(host.textContent).toContain('تعديل غير محفوظ');
  let finish!: (value: { value: string }) => void;
  mocks.request.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'حفظ القيمة')!.click());
  expect(host.textContent).toContain('جارٍ الحفظ'); expect(host.textContent).not.toContain('تم الحفظ');
  saved.values.student['column-one'] = 'Updated note';
  await act(async () => finish({ value: 'Updated note' }));
  expect(host.textContent).toContain('تم الحفظ');
  await act(async () => root.unmount()); root = createRoot(host); await render();
  expect(cell()?.value).toBe('Updated note');
});
it('keeps a failed edit visibly unsaved and retries the same value', async () => {
  await render(); await editCell('Retry note');
  mocks.request.mockRejectedValueOnce(new Error('offline'));
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'حفظ القيمة')!.click());
  expect(host.textContent).toContain('القيمة غير محفوظة'); expect(cell()?.value).toBe('Retry note');
  expect(saved.values.student['column-one']).toBe('Called guardian');
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'إعادة محاولة الحفظ')!.click());
  expect(host.textContent).toContain('تم الحفظ'); expect(saved.values.student['column-one']).toBe('Retry note');
});
it('ignores a former account late save and does not mark a new teacher cell saved', async () => {
  await render(); await editCell('Teacher A private note');
  let finish!: (value: { value: string }) => void;
  mocks.request.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'حفظ القيمة')!.click());
  mocks.request.mockResolvedValue({ columns: [], values: {} }); mocks.scope = 'teacher-b'; mocks.generation++;
  await act(async () => window.dispatchEvent(new Event('lms_auth_scope_updated')));
  await act(async () => finish({ value: 'Teacher A private note' }));
  expect(host.textContent).not.toContain('تم الحفظ'); expect(cell()).toBeNull();
});
it('does not dismiss column creation or claim success before save, and retains form on failure', async () => {
  await render();
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent?.includes('إضافة عمود مخصص'))!.click());
  const name = host.querySelector<HTMLInputElement>('input[placeholder="مثال: ملاحظات السلوك، تاريخ التواصل..."]')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(name, 'New column');
    name.dispatchEvent(new Event('input', { bubbles: true }));
  });
  mocks.request.mockRejectedValueOnce(new Error('offline'));
  await act(async () => host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  expect(host.textContent).toContain('تعذر حفظ العمود'); expect(name.value).toBe('New column');
  expect(mocks.toast).not.toHaveBeenCalledWith(expect.objectContaining({ message: 'تم حفظ العمود المخصص' }));
});
it('does not lose a newly saved column when an older refresh finishes after creation', async () => {
  await render();
  let finishAdd!: (value: typeof definition) => void;
  let finishSnapshot!: (value: typeof saved) => void;
  mocks.request.mockImplementation((_path: string, init?: RequestInit) => init?.method === 'POST'
    ? new Promise(resolve => { finishAdd = resolve; })
    : new Promise(resolve => { finishSnapshot = resolve; }));
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent?.includes('إضافة عمود مخصص'))!.click());
  const name = host.querySelector<HTMLInputElement>('input[placeholder="مثال: ملاحظات السلوك، تاريخ التواصل..."]')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(name, 'New column');
    name.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await act(async () => host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  await act(async () => { window.dispatchEvent(new Event('lms_submission_graded')); await new Promise(resolve => setTimeout(resolve, 350)); });
  await act(async () => finishAdd({ ...definition, id: 'new-column', name: 'New column' }));
  expect(host.querySelector('thead')?.textContent).toContain('New column');
  await act(async () => finishSnapshot(saved));
  expect(host.querySelector('thead')?.textContent).toContain('New column');
});
it('does not resurrect a deleted column when an older refresh finishes after deletion', async () => {
  await render();
  let finishDelete!: (value?: unknown) => void;
  let finishSnapshot!: (value: typeof saved) => void;
  mocks.request.mockImplementation((_path: string, init?: RequestInit) => init?.method === 'DELETE'
    ? new Promise(resolve => { finishDelete = resolve; })
    : new Promise(resolve => { finishSnapshot = resolve; }));
  await act(async () => host.querySelector<HTMLButtonElement>('button[title="حذف هذا العمود المخصص"]')!.click());
  await act(async () => { window.dispatchEvent(new Event('lms_submission_graded')); await new Promise(resolve => setTimeout(resolve, 350)); });
  await act(async () => finishDelete()); expect(cell()).toBeNull();
  await act(async () => finishSnapshot(saved)); expect(cell()).toBeNull();
});
