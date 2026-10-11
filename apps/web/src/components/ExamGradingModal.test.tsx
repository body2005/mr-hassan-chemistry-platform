import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { ExamGradingModal } from './ExamGradingModal';
import type { StudentRecord } from '../types/lms';
const request = vi.hoisted(() => vi.fn());
vi.mock('../services/apiClient', () => ({apiRequest:request}));
const student = {id:'student', name:'Student'} as StudentRecord;
let host: HTMLDivElement, root: ReturnType<typeof createRoot>;
const approve = vi.fn(), close = vi.fn();
let graded: boolean;
const solution = () => ({student_id:'student',student_name:'Student',quiz:{id:'quiz',title:'Quiz'},
  attempt:{id:'attempt',attempt_number:1,submitted_at:null,duration_seconds:20},score:0,total_points:10,
  history_state:'frozen', grading_status:graded ? 'complete':'pending', approval_status:'pending',
  summary:{correct:0,wrong:0,skipped:0,total:1}, questions:[{id:'essay',question_type:'essay',prompt:'Explain',
    points:10,awarded:0,state:graded?'wrong':'pending',answered:true,student_answer:'Different valid wording',
    correct_answer:'Model answer',options:[]}]});
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true); graded=false; request.mockReset(); approve.mockReset(); close.mockReset();
  request.mockImplementation((path:string) => {
    if(path.endsWith('/grade')) {graded=true; return Promise.resolve({});}
    if(path.endsWith('/approve')) return Promise.resolve({approval_status:'approved'});
    return Promise.resolve(solution());
  });
  host=document.createElement('div'); document.body.append(host); root=createRoot(host);
});
afterEach(async () => {await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals();});
const render = async () => act(async () => root.render(<ExamGradingModal student={student} onClose={close} onApproveGrade={approve} />));
const save = async () => act(async () => [...host.querySelectorAll('button')].find(button => button.textContent?.includes('اعتماد وإظهار النتيجة'))!.click());
async function markZero() {
  const input=host.querySelector<HTMLInputElement>('input[aria-label="درجة السؤال 1"]')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'0');
    input.dispatchEvent(new Event('input',{bubbles:true}));
  });
}
it('keeps unmarked essays pending and does not release or dismiss them', async () => {
  await render(); await save();
  expect(host.textContent).toContain('توجد إجابات بانتظار التصحيح');
  expect(request.mock.calls.some(([path])=>path.endsWith('/approve'))).toBe(false);
  expect(approve).not.toHaveBeenCalled(); expect(close).not.toHaveBeenCalled();
});
it('distinguishes an explicit zero from unmarked and calls the server release action', async () => {
  await render(); await markZero(); await save();
  const grading = request.mock.calls.find(([path])=>path.endsWith('/grade'))!;
  expect(JSON.parse(grading[1].body).awarded_points).toBe(0);
  expect(request.mock.calls.some(([path])=>path==='/quiz-attempts/attempt/approve')).toBe(true);
  expect(approve).toHaveBeenCalledWith('student',0,''); expect(close).toHaveBeenCalledTimes(1);
});
it('approves newly marked answers even when a previous pending solution is cached', async () => {
  const cachedPending = solution();
  const original = request.getMockImplementation()!;
  request.mockImplementation((path: string, init?: { skipCache?: boolean }) => {
    // The real API client caches GETs for 15 seconds. A first approval with
    // an unmarked essay must not make the next successful marking look stale.
    if (path.includes('/quiz-solution') && !init?.skipCache)
      return Promise.resolve(cachedPending);
    return original(path, init);
  });
  await render(); await save();
  expect(close).not.toHaveBeenCalled();
  await markZero(); await save();
  expect(request.mock.calls.filter(([path]) => path.endsWith('/grade'))).toHaveLength(1);
  expect(request.mock.calls.filter(([path]) => path.endsWith('/approve'))).toHaveLength(1);
  expect(approve).toHaveBeenCalledWith('student',0,'');
  expect(close).toHaveBeenCalledTimes(1);
});
it('does not report approval when the server rejects release', async () => {
  const original=request.getMockImplementation()!;
  request.mockImplementation((path:string, ...args:unknown[]) => path.endsWith('/approve') ? Promise.reject(new Error('Release failed')) : original(path,...args));
  await render(); await markZero(); await save();
  expect(host.textContent).toContain('Release failed');
  expect(approve).not.toHaveBeenCalled(); expect(close).not.toHaveBeenCalled();
});

it('keeps an already approved result read-only after reopening', async () => {
  graded = true;
  request.mockResolvedValue({...solution(), approval_status:'approved'});
  await render();
  expect(host.querySelector<HTMLInputElement>('input[aria-label="درجة السؤال 1"]')!.disabled).toBe(true);
  const button = [...host.querySelectorAll('button')].find(item => item.textContent?.includes('النتيجة معتمدة'))!;
  expect(button.disabled).toBe(true);
  await act(async () => button.click());
  expect(request.mock.calls.some(([path]) => path.endsWith('/approve') || path.endsWith('/grade'))).toBe(false);
});
