import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ToastProvider } from '../components/ToastProvider';
import { QuizGeneratorView } from './QuizGeneratorView';
import type { Course, TeacherProfile } from '../types/lms';

vi.mock('../services/quizHistoryService', () => ({
  quizHistoryService: { getHistory: () => [], subscribe: () => () => undefined },
}));

const teacher: TeacherProfile = {
  id: 'qa-draft-owner', name: 'QA Teacher', email: 'draft@example.test', role: 'teacher',
  nationalId: '', phone: '', teachingYear: 'all', teachingYearLabel: '', subject: 'chemistry',
  contractAgreed: true, joinedDate: '',
};
const course: Course = {
  id: 'late-course', title: 'QA Course', subject: 'chemistry', academicYear: '1st_secondary',
  academicYearLabel: '', teacherName: '', teacherTitle: '', description: '', thumbnailColor: '',
  lessonsCount: 0, totalDurationFormatted: '', lessons: [], enrolledStudentsCount: 0,
};
const key = `lms_quiz_maker_unuploaded_draft_v2:${teacher.id}`;
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  localStorage.clear();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove(); localStorage.clear(); vi.unstubAllGlobals();
});
async function render(courses: Course[] = []) {
  await act(async () => root.render(<ToastProvider><QuizGeneratorView courses={courses} currentUser={teacher} /></ToastProvider>));
}
async function title(value: string) {
  const input = host.querySelector<HTMLInputElement>('input[placeholder="أدخل اسم الاختبار هنا..."]')!;
  expect(input).not.toBeNull();
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
function saveOtherTab() {
  const serialized = JSON.stringify({ title: 'Newer other-tab draft', questions: [], selectedAcademicYear: '1st_secondary' });
  localStorage.setItem(key, serialized);
  return serialized;
}

it('does not erase another tab\'s draft when a blank editor receives a late course', async () => {
  await render();
  const newer = saveOtherTab();
  await render([course]); // Real mounted autosave reruns when course hydration completes.
  expect(localStorage.getItem(key)).toBe(newer);
});
it('still removes this editor\'s own saved draft when its last content is cleared', async () => {
  await render([course]); await title('Own draft');
  expect(JSON.parse(localStorage.getItem(key)!).title).toBe('Own draft');
  await title('');
  expect(localStorage.getItem(key)).toBeNull();
});
it('does not erase a newer other-tab draft when an older editor is cleared', async () => {
  await render([course]); await title('Older own draft');
  const newer = saveOtherTab();
  await title('');
  expect(localStorage.getItem(key)).toBe(newer);
});
it('does not overwrite a newer other-tab draft on late course hydration and reports the conflict', async () => {
  await render(); await title('Older own draft');
  const newer = saveOtherTab();
  await render([course]);
  expect(localStorage.getItem(key)).toBe(newer);
  expect(host.querySelector('[role="alert"]')?.textContent).toContain('مسودة أحدث');
  expect(host.querySelector<HTMLInputElement>('input[placeholder="أدخل اسم الاختبار هنا..."]')?.value).toBe('Older own draft');
});

it('removes stage buttons and repeats the reason when an invalid publish is retried', async () => {
  await render([course]);
  expect(host.querySelector('.quiz-editor-journey button')).toBeNull();
  const action = (text: string) => [...host.querySelectorAll('button')].find(button => button.textContent?.includes(text))!;
  await act(async () => action('بدء إضافة أسئلة').click());
  await act(async () => action('حفظ ونشر الاختبار').click());
  expect(document.body.querySelector('.toast-danger')?.textContent).toContain('اسم الاختبار');
  await act(async () => document.body.querySelector<HTMLButtonElement>('.toast-dismiss')!.click());
  expect(document.body.querySelector('.toast-danger')).toBeNull();
  await act(async () => action('حفظ ونشر الاختبار').click());
  expect(document.body.querySelector('.toast-danger')?.textContent).toContain('اسم الاختبار');
});
