import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MySubmissionsView } from './MySubmissionsView';
import { submissionService } from '../services/lmsService';
import type { StudentProfile } from '../types/lms';

const mocks = vi.hoisted(() => ({ request: vi.fn(), excel: vi.fn() }));
vi.mock('../services/apiClient', () => ({ apiRequest: mocks.request, apiUrl: (value: string) => value }));
vi.mock('../utils/exportEngine', () => ({ exportToDocx: vi.fn(), exportToExcel: mocks.excel, exportToPrintPdf: vi.fn() }));
const student = { id: 'student', role: 'student', name: 'Student' } as StudentProfile;
const base = { assignment_id: 'assignment', student_id: 'student', submitted_at: '2026-10-15', max_score: 100, answer_text: 'Answer' };
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); mocks.request.mockReset(); mocks.excel.mockReset();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); localStorage.clear(); vi.unstubAllGlobals(); });
it('preserves pending null while retaining an approved real zero in API mapping', async () => {
  mocks.request.mockResolvedValue([
    { ...base, id: 'pending', final_score: null, status: 'submitted' },
    { ...base, id: 'zero', final_score: 0, status: 'approved' },
  ]);
  const rows = await submissionService.getStudentSubmissions();
  expect(rows[0].finalScore).toBeNull();
  expect(rows[1].finalScore).toBe(0);
});
it('hides pending and unapproved scores and averages only approved results, including real zero', async () => {
  mocks.request.mockResolvedValue([
    { ...base, id: 'pending', assignment_title: 'Pending assignment', final_score: null, status: 'submitted' },
    { ...base, id: 'unapproved', assignment_title: 'Unapproved assignment', final_score: 10, status: 'graded' },
    { ...base, id: 'full', assignment_title: 'Full score', final_score: 100, status: 'approved' },
    { ...base, id: 'zero', assignment_title: 'Real zero', final_score: 0, status: 'approved' },
  ]);
  await act(async () => root.render(<MySubmissionsView currentUser={student} />));
  const card = (title: string) => [...host.querySelectorAll('h3')].find(el => el.textContent === title)!.parentElement!.parentElement!;
  expect(card('Pending assignment').textContent).toContain('بانتظار التصحيح');
  expect(card('Unapproved assignment').textContent).toContain('بانتظار اعتماد المعلم');
  expect(card('Real zero').textContent).toContain('0 / 100');
  await act(async () => [...host.querySelectorAll('button')].find(el => el.textContent?.includes('تصدير التقرير'))!.click());
  await act(async () => [...host.querySelectorAll('button')].find(el => el.textContent?.includes('Excel'))!.click());
  const payload = mocks.excel.mock.calls[0][0];
  expect(payload.summaryStats).toContainEqual({ label: 'متوسط الدرجات', value: '50%' });
  expect(payload.rows[0][3]).toBe('بانتظار التصحيح');
  expect(payload.rows[1][3]).toBe('بانتظار اعتماد المعلم');
});
it('exports no fabricated average when all scores are pending, in English too', async () => {
  localStorage.setItem('lms_lang', 'en');
  mocks.request.mockResolvedValue([{ ...base, id: 'pending', final_score: null, status: 'submitted' }]);
  await act(async () => root.render(<MySubmissionsView currentUser={student} />));
  expect(host.textContent).toContain('Awaiting grading');
  await act(async () => [...host.querySelectorAll('button')].find(el => el.textContent?.includes('تصدير التقرير'))!.click());
  await act(async () => [...host.querySelectorAll('button')].find(el => el.textContent?.includes('Excel'))!.click());
  expect(mocks.excel.mock.calls[0][0].summaryStats).toContainEqual({ label: 'متوسط الدرجات', value: '—' });
  expect(mocks.excel.mock.calls[0][0].rows[0][3]).toBe('Awaiting grading');
});
