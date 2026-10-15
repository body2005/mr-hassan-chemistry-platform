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
  mocks.request.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === 'PUT') { saved.values.student['column-one'] = JSON.parse(String(init.body)).value; return { value: saved.values.student['column-one'] }; }
    return structuredClone(saved);
  });
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
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
