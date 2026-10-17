import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ToastProvider } from '../components/ToastProvider';
import { QuizGeneratorView } from './QuizGeneratorView';
import type { Course, TeacherProfile } from '../types/lms';
import { validateAssessmentPublication } from '../services/assessmentPublication';

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

it('edits and restores ordering choices and their correct sequence, without offering matching', async () => {
  localStorage.setItem(key, JSON.stringify({ title: 'Typed question', questions: [{ id: 1,
    question_type: 'multiple_choice', question_text: 'Labelled question items', points: 5,
    difficulty: 'medium', topic: '', explanation: '', correct_answer: 'Old answer',
    options: [{ key: 'A', text: 'Old answer', is_correct: true }, { key: 'B', text: 'Other', is_correct: false }] }] }));
  await render([course]);
  const selector = host.querySelector<HTMLSelectElement>('select[aria-label="نوع السؤال 1"]')!;
  expect([...selector.options].map(option => option.value)).toContain('ordering');
  expect([...selector.options].map(option => option.value)).not.toContain('matching');
  await act(async () => { selector.value = 'ordering'; selector.dispatchEvent(new Event('change', { bubbles: true })); });
  let saved = JSON.parse(localStorage.getItem(key)!);
  expect(saved.questions[0]).toMatchObject({ question_type: 'ordering', needs_answer_review: false });
  expect(saved.questions[0].options.map((option: {text: string}) => option.text)).toEqual(['Old answer', 'Other']);
  expect(saved.questions[0].options[0].key).not.toBe('A');
  const publication = { title: 'Exam', lessonId: 'lesson', isQuiz: true, duration: 30,
    startDate: '2099-01-01', startTime: '03:00 م', endDate: '2099-01-02', endTime: '03:00 م', questions: saved.questions };
  expect(validateAssessmentPublication(publication, 'review')).toBeNull();
  expect(host.querySelector('textarea[aria-label="الإجابة الصحيحة"]')).toBeNull();
  await act(async () => host.querySelector<HTMLButtonElement>('button[aria-label="تحريك الاختيار 1 لأسفل"]')!.click());
  saved = JSON.parse(localStorage.getItem(key)!);
  expect(saved.questions[0].options.map((option: {text: string}) => option.text)).toEqual(['Other', 'Old answer']);
  expect(saved.questions[0].correct_answer.split(',')).toEqual(saved.questions[0].options.map((option: {key: string}) => option.key));
  expect(validateAssessmentPublication({ ...publication, questions: saved.questions }, 'review')).toBeNull();
  const row = [...host.querySelectorAll('.question-points-panel tbody tr')].find(row => row.querySelector('th')?.textContent === 'ترتيب')!;
  expect(row.querySelector('td')?.textContent).toBe('1');
  const score = row.querySelector('input')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(score, '7');
    score.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await act(async () => root.unmount()); root = createRoot(host); await render([course]);
  expect(host.querySelector<HTMLSelectElement>('select[aria-label="نوع السؤال 1"]')?.value).toBe('ordering');
  expect(host.textContent).toContain('الترتيب الصحيح للاختيارات');
  expect(JSON.parse(localStorage.getItem(key)!).questions[0].options.map((option: {text: string}) => option.text)).toEqual(['Other', 'Old answer']);
  expect(JSON.parse(localStorage.getItem(key)!).questions[0].points).toBe(7);
  expect(host.querySelector<HTMLInputElement>('input[aria-label="نص اختيار الترتيب 1"]')?.value).toBe('Other');
  expect(JSON.parse(localStorage.getItem(key)!).editingQuestionId).toBe(1);
  await click('حفظ التعديل');
  expect(host.querySelector('input[aria-label="نص اختيار الترتيب 1"]')).toBeNull();
  await act(async () => root.unmount()); root = createRoot(host); await render([course]);
  expect(host.querySelector('input[aria-label="نص اختيار الترتيب 1"]')).toBeNull();
  expect(host.querySelector('button[aria-label="تحريك الاختيار 1 لأسفل"]')).not.toBeNull();
  await act(async () => host.querySelector<HTMLButtonElement>('button[aria-label="تحريك الاختيار 1 لأسفل"]')!.click());
  expect(JSON.parse(localStorage.getItem(key)!).questions[0].options.map((option: {text: string}) => option.text)).toEqual(['Old answer', 'Other']);
  expect(JSON.parse(localStorage.getItem(key)!).questions[0].points).toBe(7);
});

it('keeps ordering controls on older drafts that have no saved edit mode', async () => {
  localStorage.setItem(key, JSON.stringify({ title: 'Older draft', questions: [{ id: 1, question_type: 'ordering',
    question_text: 'Arrange these choices', points: 5, correct_answer: 'second,first',
    options: [{ key: 'first', text: 'First', is_correct: false }, { key: 'second', text: 'Second', is_correct: false }] }] }));
  await render([course]);
  const list = host.querySelector('ol[aria-label="اختيارات سؤال الترتيب"]')!;
  expect(list.querySelectorAll('[data-order-key]')).toHaveLength(2);
  expect(list.querySelector('li')?.textContent).toContain('Second');
  expect(host.querySelector('button[aria-label="تحريك الاختيار 1 لأسفل"]')).not.toBeNull();
  expect(host.textContent).not.toContain('اعتماد الترتيب الحالي');
});
