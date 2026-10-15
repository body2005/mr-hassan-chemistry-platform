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
  await details();
  const input = host.querySelector<HTMLInputElement>('input[placeholder="أدخل اسم الاختبار هنا..."]')!;
  expect(input).not.toBeNull();
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  if (!value) {
    await click('رجوع للأسئلة');
    for (const button of host.querySelectorAll<HTMLButtonElement>('button[title="حذف هذا السؤال"]')) {
      await act(async () => button.click());
    }
  }
}
async function click(text: string) {
  const button = [...host.querySelectorAll('button')].find(item => item.textContent?.includes(text));
  expect(button, text).toBeDefined();
  await act(async () => button!.click());
}
async function details() {
  if (host.querySelector('input[placeholder="أدخل اسم الاختبار هنا..."]')) return;
  const begin = [...host.querySelectorAll('button')].find(item => item.textContent?.includes('بدء إضافة أسئلة'));
  if (begin) await act(async () => begin.click());
  await click('حفظ ونشر الاختبار');
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

it('validates the details step and repeats the reason on retry without publishing', async () => {
  await render([course]);
  expect(host.querySelector('.quiz-editor-journey button')).toBeNull();
  const action = (text: string) => [...host.querySelectorAll('button')].find(button => button.textContent?.includes(text))!;
  await act(async () => action('بدء إضافة أسئلة').click());
  await act(async () => action('حفظ ونشر الاختبار').click());
  await click('التالي: المواعيد');
  expect(document.body.querySelector('.toast-danger')?.textContent).toContain('اسم الاختبار');
  await act(async () => document.body.querySelector<HTMLButtonElement>('.toast-dismiss')!.click());
  expect(document.body.querySelector('.toast-danger')).toBeNull();
  await click('التالي: المواعيد');
  expect(document.body.querySelector('.toast-danger')?.textContent).toContain('اسم الاختبار');
});

it('saves and restores multiple units and lessons from the separate dropdowns', async () => {
  const populated = {...course, lessons: [
    {id:'one', moduleId:'unit-one', unitTitle:'الوحدة الأولى', title:'الدرس الأول'},
    {id:'two', moduleId:'unit-two', unitTitle:'الوحدة الثانية', title:'الدرس الثاني'},
  ]} as Course;
  await render([populated]);
  await title('اختبار متعدد الدروس والوحدات');
  for (const field of host.querySelectorAll('.assessment-scope-field')) {
    await act(async () => field.querySelector('summary')!.click());
    for (const checkbox of field.querySelectorAll<HTMLInputElement>('input')) {
      await act(async () => checkbox.click());
    }
  }
  const saved = JSON.parse(localStorage.getItem(key)!);
  expect(saved.selectedLessonIds).toEqual(['one','two']);
  expect(saved.selectedModuleIds).toEqual(['unit-one','unit-two']);
  expect(saved.selectedCourseId).toBe(course.id);
  await act(async () => root.unmount());
  root = createRoot(host);
  await render([populated]);
  await details();
  const fields = host.querySelectorAll('.assessment-scope-field');
  expect(fields[0].querySelectorAll('li')).toHaveLength(2);
  expect(fields[1].querySelectorAll('li')).toHaveLength(2);
  expect([...fields[0].querySelectorAll('input')].every(input => input.checked)).toBe(true);
  expect([...fields[1].querySelectorAll('input')].every(input => input.checked)).toBe(true);
});

it('shows file and questions first, then details, then schedule, and preserves questions on Back', async () => {
  const populated = { ...course, lessons: [{ id: 'one', title: 'First lesson' }] } as Course;
  await render([populated]);
  expect(host.querySelector('input[type="file"]')).not.toBeNull();
  expect(host.querySelector('.quiz-settings-panel')).toBeNull();
  expect(host.querySelector('.quiz-publication-fields')).toBeNull();
  await title('Wizard exam');
  expect(host.querySelector('input[type="file"]')).toBeNull();
  expect(host.querySelector('.assessment-scope-picker')).not.toBeNull();
  expect(host.querySelector('.quiz-publication-fields')).toBeNull();
  await act(async () => host.querySelector<HTMLInputElement>('.assessment-scope-field:last-of-type input')!.click());
  await click('التالي: المواعيد');
  expect(host.querySelector('.quiz-publication-fields')).not.toBeNull();
  expect(host.querySelector('.assessment-scope-picker')).toBeNull();
  expect(host.querySelector('input[type="number"]')).not.toBeNull();
  expect(document.body.querySelector('[role="dialog"]')).toBeNull();
  await click('رجوع لبيانات النشاط');
  expect(host.querySelector<HTMLInputElement>('input[placeholder="أدخل اسم الاختبار هنا..."]')?.value).toBe('Wizard exam');
  await click('رجوع للأسئلة');
  expect(host.querySelectorAll('button[title="حذف هذا السؤال"]')).toHaveLength(1);
  expect(host.querySelector('input[type="file"]')).not.toBeNull();
});

it('lets the teacher choose an assignment after preparing questions without requiring an exam answer key or timer', async () => {
  localStorage.setItem(key, JSON.stringify({ title: 'Manual assignment', selectedAcademicYear: '1st_secondary',
    questions: [{ id: 1, question_type: 'multiple_choice', question_text: 'Explain your choice', points: 5,
      topic: '', difficulty: 'medium', explanation: '', correct_answer: null,
      options: [{ key: 'A', text: 'First', is_correct: false }, { key: 'B', text: 'Second', is_correct: false }] }] }));
  const populated = { ...course, lessons: [{ id: 'one', title: 'First lesson' }] } as Course;
  await render([populated]); await details(); await click('واجب منزلي');
  expect(host.querySelector<HTMLInputElement>('input[placeholder="أدخل اسم الواجب هنا..."]')?.value).toBe('Manual assignment');
  await act(async () => host.querySelector<HTMLInputElement>('.assessment-scope-field:last-of-type input')!.click());
  await click('التالي: المواعيد');
  expect(host.querySelector('.quiz-publication-fields')).not.toBeNull();
  expect(host.querySelector('input[type="number"]')).toBeNull();
  expect(host.querySelectorAll('input[type="date"]')).toHaveLength(2);
});

it('restores the full original extraction filename inside the upload area', async () => {
  const filename = 'ورقة أسئلة الكيمياء - الفصل الأول - نسخة المدرس الأصلية.pdf';
  localStorage.setItem(key, JSON.stringify({ title: 'Saved extraction', questions: [], extractedFileName: filename,
    extractedFileFingerprint: 'source-fingerprint', extractedAt: '2026-10-15T08:00:00Z' }));
  await render();
  const uploader = host.querySelector('.assessment-file-panel')!;
  expect(uploader.textContent).toContain(filename);
  expect(uploader.textContent).toContain('source-fingerpri');
});
