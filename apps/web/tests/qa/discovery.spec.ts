/** Exploratory regressions. Failures are deliberately not marked expected/skipped.
 * Uses disposable accounts/content in the allowlisted local QA project only.
 * Run after the standard journeys; do not overlap shared-IP auth tests.
 */
import type { Browser, Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { expect, test } from './qaTest';

const base = process.env.QA_BASE_URL || 'https://localhost:18543';
function pdfText(pdf: Buffer) {
  return execFileSync(process.env.QA_PYTHON || 'python', ['-c',
    'import io,sys; from pypdf import PdfReader; print("\\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(sys.stdin.buffer.read())).pages))'],
  { input: pdf, encoding: 'utf8', timeout: 10_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
}
async function signIn(page: Page, email: string, password: string) {
  // Use the actual guest sign-in control, including after a real logout.
  // A hash alone is not the modal's public navigation contract.
  await page.goto(base);
  await page.getByRole('button', {name: 'تسجيل الدخول', exact: true}).click();
  const form = page.locator('form').first();
  await form.locator('input[type="text"]').fill(email);
  await form.locator('input[type="password"]').fill(password);
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('.profile-button')).toHaveCount(1);
}
async function teacher(page: Page) {
  const project = process.env.QA_REDIS_CONTAINER?.replace(/-redis-1$/, '');
  if (project !== 'chemistryaudit2') throw new Error('Discovery requires chemistryaudit2');
  const output = execFileSync(process.env.QA_DOCKER || 'docker', ['exec', '-e', 'QA_ISOLATED=true', '-e', `QA_PROJECT=${project}`,
    `${project}-api-1`, 'sh', '/srv/entrypoint-prod.sh', 'python', '-m', 'scripts.seed_qa_teacher'], { encoding: 'utf8', timeout: 20_000 });
  const identity = JSON.parse(output.trim());
  await signIn(page, identity.email, identity.password);
  return identity;
}
async function post(page: Page, path: string, data: unknown, status = 201) {
  const csrf = (await page.context().cookies()).find(c => c.name === 'matgar_csrf')?.value || '';
  const response = await page.request.post(`${base}/api/v1/${path}`, { data, headers: { 'X-CSRF-Token': csrf } });
  expect(response.status(), await response.text()).toBe(status);
  return response.json();
}
async function student(browser: Browser, grade = 'SECONDARY_1') {
  const context = await browser.newContext({ baseURL: base, ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === 'true' });
  const page = await context.newPage();
  const email = `qa-discovery-${crypto.randomUUID()}@demo.com`;
  const password = 'qa-discovery-only-pass';
  const response = await page.request.post(`${base}/api/v1/auth/register`, { data: { display_name: 'QA Discovery Student', email,
    password, grade_level: grade, governorate: 'CAIRO', school_name: 'QA local school', gender: 'MALE' } });
  expect(response.status(), await response.text()).toBe(201);
  // Registration establishes the real session cookies; #auth correctly
  // redirects an authenticated student, so no second sign-in form exists.
  await page.goto(base);
  await expect(page.locator('.profile-button')).toHaveCount(1);
  return { page, close: async () => {
    const csrf = (await context.cookies()).find(c => c.name === 'matgar_csrf')?.value;
    if (csrf) expect((await page.request.post(`${base}/api/v1/auth/logout`, { headers: { 'X-CSRF-Token': csrf } })).status()).toBe(204);
    await context.close();
  } };
}
async function courseWithLesson(page: Page, suffix = '', grade = 'SECONDARY_1') {
  const course = await post(page, 'courses', { code: `QAD-${crypto.randomUUID().slice(0, 8)}`, title: `QA discovery course ${suffix}`, grade_level: grade });
  const module = await post(page, `courses/${course.id}/modules`, { title: 'QA Unit', position: 1 });
  const lesson = await post(page, `modules/${module.id}/lessons`, { title: `QA discovery lesson ${suffix}`, kind: 'article', position: 1, price_egp: 0 });
  await post(page, `courses/${course.id}/publish`, {}, 200);
  return { course, lesson };
}
type DraftQuestion = { id: string; question_text: string; question_type: string; points: number; options?: { key: string; text: string; is_correct: boolean }[] };
async function prepareDraft(page: Page, lessonId: string, kind: string, questions: DraftQuestion[], future = false) {
  const me = await (await page.request.get(`${base}/api/v1/auth/me`)).json();
  const title = `QA Discovery ${kind} ${Date.now()}`;
  await page.evaluate(({ id, draft }) => localStorage.setItem(`lms_quiz_maker_unuploaded_draft_v2:${id}`, JSON.stringify(draft)), {
    id: me.id, draft: { title, assessmentType: kind, selectedAcademicYear: '1st_secondary', selectedLessonIds: [lessonId],
      quizDurationMinutes: 45, publishStartDate: new Date(Date.now() + (future ? 86400_000 : 0)).toISOString().slice(0, 10),
      publishStartTime: '00:00', closeDeadlineDate: new Date(Date.now() + 3 * 86400_000).toISOString().slice(0, 10),
      closeDeadlineTime: '23:59', showOnStudentCalendar: false, sendScheduledNotification: false, questions },
  });
  await page.goto(`${base}/#quizgen`);
  await page.reload();
  return title;
}
async function publish(page: Page, kind: string) {
  await page.getByRole('button', { name: `حفظ ونشر ${kind === 'quiz' ? 'الاختبار' : 'الواجب'} للطلاب`, exact: true }).first().click();
  await page.getByRole('button', { name: 'تأكيد الرفع والنشر الآن' }).click();
}
const mcq: DraftQuestion = { id: 'q1', question_text: 'Choose the mass unit.', question_type: 'multiple_choice', points: 7,
  options: [{ key: 'A', text: 'kilogram QA option', is_correct: true }, { key: 'B', text: 'second QA option', is_correct: false }] };

for (const kind of ['quiz', 'assignment']) {
  test(`${kind} cannot publish OCR content until source review, including after edits and reload`, async ({ page }) => {
    test.setTimeout(120_000);
    await teacher(page);
    const { course, lesson } = await courseWithLesson(page, 'OCR review');
    const csrf = (await page.context().cookies()).find(c => c.name === 'matgar_csrf')?.value || '';
    // Real raster, real local OCR endpoint; no mocked extracted text.
    const extracted = await page.request.post(`${base}/api/v1/quiz/extract-from-file`, {
      headers: { 'X-CSRF-Token': csrf }, multipart: { course_id: course.id, lesson_id: lesson.id, target_type: kind,
        file: { name: '05_biology_first_page.png', mimeType: 'image/png',
          buffer: readFileSync('../api/tests/fixtures/blind_inputs/05_biology_first_page.png') } }, timeout: 60_000,
    });
    expect(extracted.status(), await extracted.text()).toBe(200);
    const source = await extracted.json();
    expect(source.questions).toHaveLength(5);
    expect(source.questions.every((q: { needs_content_review: boolean }) => q.needs_content_review)).toBe(true);
    const questions = source.questions.map((q: DraftQuestion) => ({ ...q, id: String(q.id), points: 2,
      needs_points_assignment: false, needs_answer_review: false,
      correct_answer: q.question_type === 'true_false' || q.question_type === 'TRUE_FALSE' ? 'صح' : null,
      options: q.options?.map((o, i) => ({ ...o, is_correct: i === 0 })) }));
    const title = await prepareDraft(page, lesson.id, kind, questions);
    const writes: string[] = [];
    page.on('request', r => { if (r.method() === 'POST' && /\/api\/v1\/(quizzes\/publish-draft|assignments)$/.test(new URL(r.url()).pathname)) writes.push(r.url()); });
    const publishButton = page.getByRole('button', { name: `حفظ ونشر ${kind === 'quiz' ? 'الاختبار' : 'الواجب'} للطلاب`, exact: true }).first();
    await publishButton.click();
    await expect(page.getByRole('button', { name: 'تأكيد الرفع والنشر الآن' })).toHaveCount(0);
    expect(writes).toHaveLength(0);
    const reviews = page.getByRole('checkbox', { name: /مراجعة نص السؤال .* مع المصدر/ });
    await expect(reviews).toHaveCount(5);
    for (let i = 0; i < 5; i++) await reviews.nth(i).check();
    await page.reload();
    for (let i = 0; i < 5; i++) await expect(reviews.nth(i)).toBeChecked();
    const card = page.getByTestId('question-card-1');
    await card.getByRole('button', { name: 'تعديل', exact: true }).click();
    await card.locator('[contenteditable="true"]').first().fill(`${questions[0].question_text} (مراجعة QA).`);
    await card.getByRole('button', { name: 'حفظ التعديل', exact: true }).click();
    await expect(reviews.first()).not.toBeChecked();
    await publishButton.click();
    await expect(page.getByRole('button', { name: 'تأكيد الرفع والنشر الآن' })).toHaveCount(0);
    expect(writes).toHaveLength(0);
    await reviews.first().check();
    await page.screenshot({ path: test.info().outputPath(`ocr-review-${kind}.png`), fullPage: true });
    await publish(page, kind);
    await expect.poll(() => writes.length).toBe(1);
    await expect.poll(async () => {
      const assessments = await (await page.request.get(`${base}/api/v1/courses/${course.id}/assessments`)).json();
      return (kind === 'quiz' ? assessments.quizzes : assessments.assignments).filter((a: { title: string }) => a.title === title).length;
    }).toBe(1);
  });
}

for (const check of ['options', 'score', 'future start'] as const) {
  test(`assignment preserves ${check} from teacher to student`, async ({ page, browser }) => {
    await teacher(page);
    const { course, lesson } = await courseWithLesson(page);
    const title = await prepareDraft(page, lesson.id, 'assignment', [mcq], check === 'future start');
    const created = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/v1/assignments');
    await publish(page, 'assignment');
    const response = await created;
    expect(response.status()).toBe(201);
    const record = await response.json();
    await expect.poll(async () => (await (await page.request.get(`${base}/api/v1/assignments?course_id=${course.id}`)).json())[0]?.status).toBe('published');
    const learner = await student(browser);
    try {
      await post(learner.page, `courses/${course.id}/enroll`, {}, 200);
      await learner.page.reload();
      if (await learner.page.getByLabel('اختر المقرر').count()) await learner.page.getByLabel('اختر المقرر').selectOption(course.id);
      await learner.page.getByRole('button', { name: 'الواجبات والتكليفات' }).click();
      await expect(learner.page.getByText(title, { exact: true }).first()).toBeVisible();
      await learner.page.getByRole('button', { name: 'فتح الواجب وتسليم الحل' }).click();
      await learner.page.screenshot({ path: test.info().outputPath(`assignment-${check.replaceAll(' ', '-')}.png`), fullPage: true });
      if (check === 'options') {
        // Homework intentionally renders its questions in a PDF, not inline
        // in the HTML. Inspect the actual student-visible paper as well as
        // the stored prompt; an absent HTML text alone is not evidence.
        const sheet = await learner.page.request.get(`${base}/api/v1/assignments/${record.id}/sheet.pdf`);
        expect(sheet.status()).toBe(200);
        const pdf = await sheet.body();
        await test.info().attach('student-assignment-sheet', { body: pdf, contentType: 'application/pdf' });
        const paperText = pdfText(pdf);
        console.log(JSON.stringify({ case: 'assignment-paper', sheet_status: sheet.status(), contains_choices: paperText.includes(mcq.options![0].text) }));
        expect.soft(record.prompt, 'Published prompt must retain MCQ choices').toContain(mcq.options![0].text);
        expect(paperText, 'Student PDF must retain the multiple-choice options').toContain(mcq.options![0].text);
      } else if (check === 'score') {
        expect(record.max_score, 'Teacher assigned seven points, not the default one hundred').toBe(7);
      } else {
        const csrf = (await learner.page.context().cookies()).find(c => c.name === 'matgar_csrf')?.value || '';
        const attempt = await learner.page.request.post(`${base}/api/v1/assignments/${record.id}/attempts`, { headers: { 'X-CSRF-Token': csrf } });
        console.log(JSON.stringify({ case: 'future-assignment', start_is_tomorrow: true, actual_attempt_status: attempt.status() }));
        expect.soft(attempt.status(), 'Future assignment must not be open before the teacher-selected start').toBe(403);
        const submitted = await learner.page.request.post(`${base}/api/v1/assignments/${record.id}/submissions`, {
          headers: { 'X-CSRF-Token': csrf }, data: { answer_text: 'QA submitted before future release', idempotency_key: crypto.randomUUID() },
        });
        console.log(JSON.stringify({ case: 'future-assignment-submit', actual_status: submitted.status() }));
        expect(submitted.status()).toBe(403);
      }
    } finally { await learner.close(); }
  });
}

test('failed quiz publishing is atomic and retry does not duplicate questions', async ({ page }) => {
  await teacher(page);
  const { course, lesson } = await courseWithLesson(page);
  await prepareDraft(page, lesson.id, 'quiz', [{ id: 'valid', question_text: 'Explain conservation of mass.', question_type: 'essay', points: 5 },
    { id: 'invalid', question_text: 'x', question_type: 'essay', points: 5 }]);
  const outcomes: number[] = [];
  // Publication is now one HTTP transaction; the same invariant remains:
  // rejected drafts and retries must create no question/quiz records.
  page.on('response', r => { if (r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/v1/quizzes/publish-draft') outcomes.push(r.status()); });
  await publish(page, 'quiz');
  await expect.poll(() => outcomes.includes(422)).toBe(true);
  const questions = await (await page.request.get(`${base}/api/v1/questions?course_id=${course.id}`)).json();
  console.log(JSON.stringify({ case: 'partial-quiz', statuses: outcomes, orphan_count: questions.length }));
  await page.screenshot({ path: test.info().outputPath('partial-quiz.png'), fullPage: true });
  expect.soft(questions).toHaveLength(0);
  // A failed publication leaves the confirmation modal open; retry the
  // visible confirmation instead of clicking the obscured page underneath.
  await page.getByRole('button', { name: 'تأكيد الرفع والنشر الآن' }).click();
  await expect.poll(() => outcomes.length).toBe(2);
  const afterRetry = await (await page.request.get(`${base}/api/v1/questions?course_id=${course.id}`)).json();
  console.log(JSON.stringify({ case: 'partial-quiz-retry', statuses: outcomes, orphan_count: afterRetry.length }));
  expect(afterRetry).toHaveLength(0);
});

test('student PDF retains Latin question text and title present in the server record', async ({ page, browser }) => {
  await teacher(page);
  const { course, lesson } = await courseWithLesson(page);
  const prompt = 'Choose the mass unit. 12 kg.';
  const title = 'QA Science Units';
  const assignment = await post(page, 'assignments', { course_id: course.id, lesson_id: lesson.id, title, prompt, max_score: 5 });
  expect(assignment.prompt).toBe(prompt);
  expect(assignment.title).toBe(title);
  await post(page, `assignments/${assignment.id}/publish`, {}, 200);
  const learner = await student(browser);
  try {
    await post(learner.page, `courses/${course.id}/enroll`, {}, 200);
    const response = await learner.page.request.get(`${base}/api/v1/assignments/${assignment.id}/sheet.pdf`);
    expect(response.status()).toBe(200);
    const pdf = await response.body();
    await test.info().attach('latin-student-paper', { body: pdf, contentType: 'application/pdf' });
    const text = pdfText(pdf);
    console.log(JSON.stringify({ case: 'latin-pdf', stored_text_correct: true, sheet_status: response.status(), contains_question: text.includes(prompt), contains_title: text.includes(title) }));
    expect.soft(text, 'Stored Latin title must be legible in the student PDF').toContain(title);
    expect(text, 'Stored Latin question and units must be legible in the student PDF').toContain(prompt);
  } finally { await learner.close(); }
});

test('closed assignment rejects direct submission even without an active attempt', async ({ page, browser }) => {
  await teacher(page);
  const { course, lesson } = await courseWithLesson(page);
  const assignment = await post(page, 'assignments', { course_id: course.id, lesson_id: lesson.id, title: 'QA closed assignment',
    prompt: 'Explain the unit of mass', due_at: new Date(Date.now() - 3600_000).toISOString(), max_score: 5 });
  await post(page, `assignments/${assignment.id}/publish`, {}, 200);
  const learner = await student(browser);
  try {
    await post(learner.page, `courses/${course.id}/enroll`, {}, 200);
    const csrf = (await learner.page.context().cookies()).find(c => c.name === 'matgar_csrf')?.value || '';
    const start = await learner.page.request.post(`${base}/api/v1/assignments/${assignment.id}/attempts`, { headers: { 'X-CSRF-Token': csrf } });
    expect(start.status(), 'Normal start must respect the deadline').toBe(403);
    const response = await learner.page.request.post(`${base}/api/v1/assignments/${assignment.id}/submissions`, {
      headers: { 'X-CSRF-Token': csrf }, data: { answer_text: 'QA submitted after deadline without starting', idempotency_key: crypto.randomUUID() },
    });
    console.log(JSON.stringify({ case: 'closed-assignment-bypass', start_status: start.status(), submit_status: response.status() }));
    expect(response.status()).toBe(403);
  } finally { await learner.close(); }
});

for (const failure of ['empty notification body', 'calendar outage'] as const) {
  test(`calendar wizard reports ${failure} honestly`, async ({ page }) => {
    await teacher(page);
    await page.goto(`${base}/#notifications`);
    await page.getByRole('button', { name: 'إضافة موعد جديد', exact: true }).click();
    await page.getByPlaceholder('مثال: الثلاثاء - المحاضرة الأسبوعية').fill(`QA Calendar ${Date.now()}`);
    await page.getByRole('button', { name: 'التالي: تحديد التوقيت', exact: true }).click();
    await page.getByRole('button', { name: /التالي:.*مراجعة/ }).click();
    if (failure === 'calendar outage') await page.route('**/api/v1/calendar', route => route.request().method() === 'POST'
      ? route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'QA calendar outage' }) }) : route.continue());
    const path = failure === 'calendar outage' ? '/calendar' : '/notifications/broadcast';
    const written = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(path));
    await page.getByRole('button', { name: 'تأكيد وحفظ الموعد في الجدول', exact: true }).click();
    const response = await written;
    console.log(JSON.stringify({ case: failure, actual_status: response.status() }));
    await page.screenshot({ path: test.info().outputPath(`calendar-${failure.replaceAll(' ', '-')}.png`), fullPage: true });
    if (failure === 'empty notification body') expect(response.status(), 'Default calendar lesson notification must be valid').toBe(201);
    else {
      const falseSuccess = await page.getByText('تم حفظ وتحديث الموعد في جدول الصف الدراسي بنجاح!', { exact: true }).isVisible();
      console.log(JSON.stringify({ case: failure, false_success_visible: falseSuccess }));
      expect(falseSuccess, 'Do not wait for the false-success toast to expire and miscount that as a pass').toBe(false);
    }
  });
}

for (const role of ['teacher', 'student']) {
  test(`${role} profile avatar survives its automatic reload`, async ({ page, browser }) => {
    const learner = role === 'student' ? await student(browser) : null;
    const author = !learner ? await teacher(page) : null;
    const target = learner?.page || page;
    try {
      await target.goto(`${base}/#profile`);
      const reloaded = target.waitForEvent('load');
      await target.locator('#avatar-upload').setInputFiles({ name: 'qa-avatar.png', mimeType: 'image/png',
        buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==', 'base64') });
      await reloaded;
      await expect(target.locator('.profile-button')).toHaveCount(1);
      await expect(target.getByRole('heading', { name: 'الملف التعريفي للحساب' })).toBeVisible();
      await target.screenshot({ path: test.info().outputPath(`avatar-${role}.png`), fullPage: true });
      const me = await (await target.request.get(`${base}/api/v1/auth/me`)).json();
      expect(me.avatar_url, 'Server must persist an authenticated avatar URL').toMatch(/^\/api\/v1\/auth\/avatar/);
      await expect(target.locator('main img[src^="/api/v1/auth/avatar"]')).toHaveCount(1);
      const image = await target.request.get(`${base}${me.avatar_url}`);
      expect(image.status()).toBe(200);
      expect(image.headers()['content-type']).toContain('image/png');
      await target.reload();
      await expect(target.locator('main img[src^="/api/v1/auth/avatar"]')).toHaveCount(1);
      const csrf = (await target.context().cookies()).find(c => c.name === 'matgar_csrf')!.value;
      expect((await target.request.post(`${base}/api/v1/auth/logout`, {headers: {'X-CSRF-Token': csrf}})).status()).toBe(204);
      await target.reload();
      await signIn(target, me.email, author?.password || 'qa-discovery-only-pass');
      await target.goto(`${base}/#profile`);
      await expect(target.locator('main img[src^="/api/v1/auth/avatar"]')).toHaveCount(1);
    } finally { if (learner) await learner.close(); }
  });
}

test('teacher can select both courses when they share the same grade', async ({ page }) => {
  await teacher(page);
  const a = await courseWithLesson(page, 'A', 'SECONDARY_2');
  const b = await courseWithLesson(page, 'B', 'SECONDARY_2');
  await page.goto(`${base}/#lessonmanagement`);
  await page.reload();
  await page.getByRole('button', { name: 'الصف الثاني الثانوي', exact: true }).click();
  await page.screenshot({ path: test.info().outputPath('same-grade-courses.png'), fullPage: true });
  // The product requires a course selector, not simultaneous concatenation.
  await page.getByLabel('اختر المقرر').selectOption(a.course.id);
  await expect(page.getByText(a.lesson.title, { exact: true })).toBeVisible();
  await page.getByLabel('اختر المقرر').selectOption(b.course.id);
  await expect(page.getByText(b.lesson.title, { exact: true })).toBeVisible();
});

for (const kind of ['quiz', 'assignment']) {
  test(`${kind} persists the explicitly selected second course and lesson after reload`, async ({page}) => {
    await teacher(page);
    const a = await courseWithLesson(page, 'A');
    const b = await courseWithLesson(page, 'B');
    await prepareDraft(page, a.lesson.id, kind, [{id: 'essay', question_text: 'Explain a source of energy.', question_type: 'essay', points: 7}]);
    await page.getByLabel('اختر المقرر').selectOption(b.course.id);
    const lessonSelect = page.locator(`select:has(option[value="${b.lesson.id}"])`);
    await lessonSelect.selectOption(b.lesson.id);
    await expect.poll(async () => page.evaluate(() => {
      const key = Object.keys(localStorage).find(key => key.startsWith('lms_quiz_maker_unuploaded_draft_v2:'));
      return key ? JSON.parse(localStorage.getItem(key)!).selectedCourseId : null;
    })).toBe(b.course.id);
    await page.reload();
    await expect(page.getByLabel('اختر المقرر')).toHaveValue(b.course.id);
    await expect(lessonSelect).toHaveValue(b.lesson.id);
    const endpoint = kind === 'quiz' ? '/quizzes/publish-draft' : '/assignments';
    const saved = page.waitForResponse(response => new URL(response.url()).pathname === `/api/v1${endpoint}` && response.request().method() === 'POST');
    await publish(page, kind);
    const response = await saved;
    expect(response.status(), await response.text()).toBe(201);
    const item = await response.json();
    // These resources expose collection/solve routes, not GET /{id}.
    // Read the saved record independently from the supported collection API.
    const collection = kind === 'quiz' ? 'quizzes' : 'assignments';
    const records = await page.request.get(`${base}/api/v1/${collection}?course_id=${b.course.id}`);
    expect(records.status(), await records.text()).toBe(200);
    const persisted = (await records.json()).find((record: {id: string}) => record.id === item.id);
    expect(persisted, 'Published assessment must exist in the stored course collection').toBeDefined();
    expect(persisted.course_id).toBe(b.course.id);
    expect(persisted.lesson_id).toBe(b.lesson.id);
    const wrongCourse = await (await page.request.get(`${base}/api/v1/${kind === 'quiz' ? 'quizzes' : 'assignments'}?course_id=${a.course.id}`)).json();
    expect(wrongCourse).toHaveLength(0);
  });
}

test('quiz publication retries after a lost response reuse the saved quiz and question records', async ({page}) => {
  await teacher(page);
  const {course, lesson} = await courseWithLesson(page);
  const title = await prepareDraft(page, lesson.id, 'quiz', [{id: 'essay', question_text: 'Explain the energy conversion.', question_type: 'essay', points: 5}]);
  let dropped = false;
  await page.route('**/api/v1/quizzes/publish-draft', async route => {
    if (!dropped) { dropped = true; await route.fetch(); await route.abort('failed'); }
    else await route.continue();
  });
  await publish(page, 'quiz');
  await expect(page.getByRole('button', {name: 'تأكيد الرفع والنشر الآن'})).toBeEnabled();
  await expect(page.getByRole('alert').last()).toBeVisible();
  await page.getByRole('button', {name: 'تأكيد الرفع والنشر الآن'}).click();
  await expect.poll(async () => (await (await page.request.get(`${base}/api/v1/quizzes?course_id=${course.id}`)).json()).filter((quiz: {title: string}) => quiz.title === title).length).toBe(1);
  await expect(page.getByRole('button', {name: 'تأكيد الرفع والنشر الآن'})).toHaveCount(0);
  expect(await (await page.request.get(`${base}/api/v1/questions?course_id=${course.id}`)).json()).toHaveLength(1);
});

test('saved calendar plus failed notification keeps a truthful draft and retry creates one of each', async ({page}) => {
  await teacher(page);
  await page.goto(`${base}/#notifications`);
  await page.getByRole('button', {name: 'إضافة موعد جديد', exact: true}).click();
  const title = `QA Partial Calendar ${Date.now()}`;
  await page.getByPlaceholder('مثال: الثلاثاء - المحاضرة الأسبوعية').fill(title);
  await page.getByRole('button', {name: 'التالي: تحديد التوقيت', exact: true}).click();
  await page.getByRole('button', {name: /التالي:.*مراجعة/}).click();
  let fail = true;
  await page.route('**/api/v1/notifications/broadcast', route => fail ? route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'QA partial send outage'})}) : route.continue());
  await page.getByRole('button', {name: 'تأكيد وحفظ الموعد في الجدول', exact: true}).click();
  await expect(page.getByRole('alert')).toContainText('حُفظ الموعد');
  fail = false;
  await page.getByRole('button', {name: 'تأكيد وحفظ الموعد في الجدول', exact: true}).click();
  await expect(page.getByRole('button', {name: 'تأكيد وحفظ الموعد في الجدول', exact: true})).toHaveCount(0);
  const events = await (await page.request.get(`${base}/api/v1/calendar`)).json();
  expect(events.filter((event: {title: string}) => event.title === title)).toHaveLength(1);
  const notifications = await (await page.request.get(`${base}/api/v1/notifications`)).json();
  expect(notifications.filter((item: {title: string}) => item.title.includes(title))).toHaveLength(1);
});

test('new teacher does not show a fabricated verified identity', async ({ page }) => {
  await teacher(page);
  const me = await (await page.request.get(`${base}/api/v1/auth/me`)).json();
  expect(me.national_id).toBeFalsy();
  await page.goto(`${base}/#profile`);
  await expect(page.getByRole('heading', { name: 'الملف التعريفي للحساب' })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('teacher-verification.png'), fullPage: true });
  await expect(page.getByText('تم التحقق من بطاقة الرقم القومي واعتماد عقد التدريس والسياسات التربوية للمنصة بنجاح')).toHaveCount(0);
});

test('new student profile has no invented completed watch history', async ({ browser }) => {
  const learner = await student(browser);
  try {
    const progress = await (await learner.page.request.get(`${base}/api/v1/progress/me`)).json();
    expect(progress).toHaveLength(0);
    await learner.page.goto(`${base}/#profile`);
    await expect(learner.page.getByRole('heading', { name: 'الملف التعريفي للحساب' })).toBeVisible();
    await learner.page.screenshot({ path: test.info().outputPath('student-invented-history.png'), fullPage: true });
    await expect(learner.page.getByText('الدرس 1: مدخل إلى الكيمياء وأدوات القياس المعملي', { exact: true })).toHaveCount(0);
  } finally { await learner.close(); }
});

test('teacher retains notification draft and sees a failure when broadcast returns 503', async ({ page }) => {
  await teacher(page);
  await page.goto(`${base}/#notifications`);
  await page.getByRole('button', { name: 'إرسال إشعار فوري للطلاب', exact: true }).click();
  const title = page.getByPlaceholder('مثال: تنبيه هام حول موعد حل الاختبار القادم');
  await title.fill('QA outage draft');
  await page.getByPlaceholder('اكتب التوجيهات أو التعليمات التي تريد وصولها للطلاب فوراً...').fill('QA outage message');
  await page.route('**/api/v1/notifications/broadcast', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'QA injected outage' }) }));
  const failed = page.waitForResponse(r => r.url().endsWith('/notifications/broadcast') && r.status() === 503);
  await page.getByRole('button', { name: 'إرسال الإشعار الآن', exact: true }).click();
  await failed;
  await page.screenshot({ path: test.info().outputPath('false-notification-success.png'), fullPage: true });
  await expect(title, 'Failure must preserve the teacher draft rather than close it and report success').toBeVisible({ timeout: 2000 });
});

test('teacher profile enrollment count reflects a real enrolled QA student', async ({ page, browser }) => {
  await teacher(page);
  const { course } = await courseWithLesson(page);
  const learner = await student(browser);
  try {
    await post(learner.page, `courses/${course.id}/enroll`, {}, 200);
    await page.goto(`${base}/#profile`);
    const count = page.getByText('الطلاب المسجلون', { exact: true }).locator('..').locator('strong');
    await expect(count).toHaveText('1');
  } finally { await learner.close(); }
});

test('grade-targeted teacher notification is not delivered to another grade', async ({ page, browser }) => {
  await teacher(page);
  const learner = await student(browser, 'SECONDARY_2');
  try {
    await page.goto(`${base}/#notifications`);
    await page.getByRole('button', { name: /إرسال إشعار/ }).first().click();
    const form = page.locator('form').filter({ has: page.getByPlaceholder('مثال: تنبيه هام حول موعد حل الاختبار القادم') });
    await form.locator('select').first().selectOption('1st_secondary');
    const title = `QA restricted grade ${Date.now()}`;
    await form.getByPlaceholder('مثال: تنبيه هام حول موعد حل الاختبار القادم').fill(title);
    await form.getByPlaceholder('اكتب التوجيهات أو التعليمات التي تريد وصولها للطلاب فوراً...').fill('QA message for grade one only');
    const sent = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/notifications/broadcast'));
    await form.getByRole('button', { name: 'إرسال الإشعار الآن' }).click();
    expect((await sent).status()).toBe(201);
    const notifications = await (await learner.page.request.get(`${base}/api/v1/notifications`)).json();
    console.log(JSON.stringify({ case: 'grade-target', wrong_grade_received: notifications.filter((n: { title: string }) => n.title === title).length }));
    expect(notifications.filter((n: { title: string }) => n.title === title)).toHaveLength(0);
  } finally { await learner.close(); }
});
