import type { Page } from "@playwright/test";
import { expect, test } from "./qaTest";

const base = process.env.QA_BASE_URL || "http://127.0.0.1:18080";
async function login(page: Page, email: string, password: string) {
  await page.goto(`${base}/#auth`);
  const form = page.locator("form").first();
  await form.locator('input[type="text"]').fill(email);
  await form.locator('input[type="password"]').fill(password);
  await form.locator('button[type="submit"]').click();
  await expect(page.locator(".profile-button")).toHaveCount(1);
}
async function post(page: Page, path: string, data: unknown, status = 201) {
  const csrf = (await page.context().cookies()).find(c => c.name === "matgar_csrf")?.value || "";
  const response = await page.request.post(`${base}/api/v1/${path}`, { data, headers: { "X-CSRF-Token": csrf } });
  expect(response.status(), await response.text()).toBe(status);
  return response.json();
}

for (const delayedIdentity of [false, true]) {
test(`essay and uploaded homework are submitted and graded through the real UI${delayedIdentity ? ' after delayed identity hydration' : ''}`, async ({ page, browser }) => {
  test.setTimeout(180_000);
  page.setDefaultTimeout(15_000);
  await login(page, "teacher@demo.com", "qa-teacher-pass");
  const stamp = Date.now();
  const course = await post(page, "courses", { code: `QAMAN${stamp}`, title: `QA Manual ${stamp}` });
  const module = await post(page, `courses/${course.id}/modules`, { title: "Manual Unit", position: 1 });
  const lesson = await post(page, `modules/${module.id}/lessons`, { title: `Manual Lesson ${stamp}`, kind: "article", position: 1, price_egp: 0 });
  const question = await post(page, "questions", { course_id: course.id, question_type: "essay", prompt: "Explain conservation of mass and units", points: 5 });
  const quiz = await post(page, "quizzes", { course_id: course.id, lesson_id: lesson.id, title: `Essay ${stamp}`, question_ids: [question.id] });
  const assignment = await post(page, "assignments", { course_id: course.id, lesson_id: lesson.id, title: `Homework ${stamp}`, prompt: "Upload your worked solution", max_score: 5 });
  await post(page, `courses/${course.id}/publish`, {}, 200);
  await post(page, `quizzes/${quiz.id}/publish`, {}, 200);
  await post(page, `assignments/${assignment.id}/publish`, {}, 200);
  // The course switcher intentionally appears only with multiple enrollments.
  const secondCourse = await post(page, "courses", { code: `QAMANB${stamp}`, title: `Other Manual ${stamp}` });
  await post(page, `courses/${secondCourse.id}/publish`, {}, 200);
  const studentContext = await browser.newContext({ ignoreHTTPSErrors: false });
  const student = await studentContext.newPage();
  student.setDefaultTimeout(15_000);
  const studentEmail = `qa-manual-${crypto.randomUUID()}@demo.com`;
  const registered = await student.request.post(`${base}/api/v1/auth/register`, { data: {
    display_name: 'QA Manual Student', email: studentEmail, password: 'qa-student-pass',
    grade_level: 'SECONDARY_1', governorate: 'CAIRO', school_name: 'Local QA school', gender: 'MALE',
  } });
  expect(registered.status(), await registered.text()).toBe(201);
  const registrationCsrf = (await studentContext.cookies()).find(c => c.name === 'matgar_csrf')!.value;
  expect((await student.request.post(`${base}/api/v1/auth/logout`, { headers: { 'X-CSRF-Token': registrationCsrf } })).status()).toBe(204);
  try {
    await login(student, studentEmail, "qa-student-pass");
    await post(student, `courses/${course.id}/enroll`, {}, 200);
    await post(student, `courses/${secondCourse.id}/enroll`, {}, 200);
    const me = await (await student.request.get(`${base}/api/v1/auth/me`)).json();
    await student.reload();
    await student.getByLabel("اختر المقرر").selectOption(course.id);
    await student.getByRole("button", { name: "الاختبارات والكويزات" }).click();
    await student.getByRole("button", { name: "بدء حل الاختبار" }).click();
    await student.getByPlaceholder("اكتب إجابتك هنا…").fill("Mass is conserved; state the units in grams.");
    await student.getByRole("button", { name: "تسليم الاختبار" }).last().click();
    await student.getByRole("button", { name: "نعم، تأكيد وتسليم الآن" }).click();
    await expect(student.getByText("تم تسليم الاختبار، والنتيجة في انتظار اعتماد المدرس")).toBeVisible();
    const pending = await (await student.request.get(`${base}/api/v1/quizzes/${quiz.id}/result`)).json();
    expect(pending.grading_status).toBe("pending");
    expect(pending.score).toBeNull();
    expect(pending.summary).toBeNull();
    expect(pending.approval_status).toBe('pending');
    expect(pending.questions.every((question: Record<string, unknown>) =>
      Object.keys(question).sort().join(',') === 'id,student_answer')).toBe(true);
    await student.getByRole("button", { name: "العودة إلى المقرر", exact: true }).click();
    await student.getByRole("button", { name: "الواجبات والتكليفات" }).click();
    await student.getByRole("button", { name: "فتح الواجب وتسليم الحل" }).click();
    await expect(student.locator('input[type="file"]')).toHaveCount(1);
    await student.locator('input[type="file"]').setInputFiles({ name: "solution.png", mimeType: "image/png",
      buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==", "base64") });
    const other = await studentContext.newPage();
    const hydrated = other.waitForResponse(response => response.url().endsWith('/bootstrap') && response.status() === 200);
    await other.goto(`${base}/#profile`);
    await hydrated;
    await expect(other.locator('.profile-button')).toHaveCount(1);
    // Reproduce the expired-access + temporary refresh outage on the actual
    // homework UI. Never send/replay the non-idempotent file while identity
    // is unavailable; retain the selected file and current account for retry.
    const transfers: string[] = [];
    student.on('request', request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname === `/api/v1/assignments/${assignment.id}/submissions/file`) transfers.push(request.url());
    });
    await studentContext.clearCookies({ name: 'matgar_session' });
    let failedRefreshes = 0;
    let otherRefreshes = 0;
    let failedSheets = 0;
    student.on('response', response => {
      if (response.url().includes(`/assignments/${assignment.id}/sheet`) && response.status() === 401) failedSheets++;
    });
    await studentContext.route('**/api/v1/auth/refresh', route => {
      if (route.request().frame().page() === student) failedRefreshes++;
      else otherRefreshes++;
      return route.fulfill({ status: 503, json: { detail: 'Synthetic temporary refresh outage' } });
    });
    // Exercise the real blob helper, multipart preflight, JSON hydration and
    // SSE renewal in two tabs sharing cookies; no direct scripted API helper.
    await student.getByRole('button', { name: 'تحميل PDF', exact: true }).click();
    // The provider deliberately announces the same message in a screen-reader
    // live region. Check the visible contextual notice AND that announcement,
    // not an ambiguous page-wide text locator or an arbitrary first match.
    const homeworkFeedback = student.getByRole('region', { name: 'رسائل الواجب', exact: true });
    const sheetError = homeworkFeedback.getByText('تعذر تحميل ورقة الواجب', { exact: true });
    await expect(sheetError).toBeVisible();
    await expect(sheetError).toBeInViewport();
    expect(await sheetError.evaluate(node => {
      const rect = node.getBoundingClientRect();
      const top = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
      return !!top && (node.contains(top) || top.contains(node));
    }), 'Visible feedback must not be behind the full-page homework overlay').toBe(true);
    await expect(student.locator('.sr-only[role="status"]')).toHaveText('تعذر تحميل ورقة الواجب');
    await other.reload();
    await student.getByRole('button', { name: 'إرسال الحل للمعلم' }).click();
    await expect(homeworkFeedback.getByText('تعذر تجديد الجلسة مؤقتًا.', { exact: false })).toBeVisible();
    await expect(student.locator('.profile-button')).toHaveCount(1);
    expect(await student.locator('input[type="file"]').evaluate(input => (input as HTMLInputElement).files?.length)).toBe(1);
    expect(transfers).toHaveLength(0);
    await student.waitForTimeout(11_000); // Observe beyond real frontend cooldown, no retry loop.
    expect(failedRefreshes).toBe(1);
    expect(otherRefreshes).toBeGreaterThanOrEqual(1);
    expect(otherRefreshes).toBeLessThanOrEqual(2);
    expect(failedSheets).toBe(1);
    expect(await other.evaluate(() => localStorage.getItem('lms_cached_user'))).not.toBeNull();
    expect(transfers).toHaveLength(0);
    await studentContext.unroute('**/api/v1/auth/refresh');
    const downloaded = student.waitForEvent('download');
    await student.getByRole('button', { name: 'تحميل PDF', exact: true }).click();
    expect((await downloaded).suggestedFilename()).toBe(`${assignment.title}.pdf`);
    const rehydrated = other.waitForResponse(response => response.url().endsWith('/bootstrap') && response.status() === 200);
    await other.reload();
    await rehydrated;
    await expect(other.locator('.profile-button')).toHaveCount(1);
    await student.getByRole("button", { name: "إرسال الحل للمعلم" }).click();
    await expect(student.getByText("تم إرسال حل الواجب للمعلم بنجاح")).toBeVisible();
    expect(transfers).toHaveLength(1);
    // One untouched lesson plus two actual submissions:2/3, not a started
    // attempt counted as complete or a homework always stuck at0.
    await expect(student.getByRole('button', { name: `نسبة إنجاز المقرر: ${course.title}`, exact: true })).toHaveText('67%');

    await page.goto(`${base}/#submissions`);
    if (delayedIdentity) {
      let release: () => void = () => {};
      const held = new Promise<void>(resolve => { release = resolve; });
      await page.route('**/api/v1/bootstrap', async route => { await held; await route.continue(); });
      const hydrated = page.waitForResponse(response => response.url().endsWith('/bootstrap') && response.status() === 200);
      await page.reload();
      try {
        await expect(page.getByRole('status')).toContainText('جارٍ التحقق من الحساب');
        await expect(page.getByRole('button', { name: 'معاينة وتعديل درجة الامتحان' }),
          'Cached identity must not expose grading before server hydration').toHaveCount(0);
      } finally { release(); }
      await hydrated;
      await page.unroute('**/api/v1/bootstrap');
    } else await page.reload();
    await page.getByPlaceholder("بحث باسم الطالب، رقم ولي الأمر، أو البريد الإلكتروني...").fill(studentEmail);
    await page.getByRole('button', { name: 'Toggle Theme' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.getByRole("button", { name: "معاينة وتعديل درجة الامتحان" }).click();
    await expect(page.getByText("Mass is conserved; state the units in grams.", { exact: true })).toBeVisible();
    await page.getByLabel("درجة السؤال 1").fill("3.5");
    await page.getByLabel("تعليق السؤال 1").fill("Good reasoning; explain the measurement units.");
    await expect(page.getByLabel('تعليق السؤال 1')).toHaveCSS('background-color', 'rgb(30, 41, 59)');
    await expect(page.getByLabel('درجة السؤال 1')).toHaveCSS('background-color', 'rgb(30, 41, 59)');
    await page.getByRole("button", { name: "اعتماد وإظهار النتيجة", exact: true }).click();
    await expect(page.getByLabel("درجة السؤال 1")).toHaveCount(0);
    const result = await (await student.request.get(`${base}/api/v1/quizzes/${quiz.id}/result`)).json();
    expect(result.grading_status).toBe("complete");
    expect(result.approval_status).toBe('approved');
    expect(result.results_approved_at).toBeTruthy();
    expect(result.score).toBe(3.5);
    expect(result.questions[0].feedback).toBe("Good reasoning; explain the measurement units.");
    const summary = await (await page.request.get(`${base}/api/v1/users?role=student`)).json();
    expect(summary.find((item: { id: string }) => item.id === me.id).has_completed_exam).toBe(true);
    await page.getByRole("button", { name: "معاينة وتعديل درجة", exact: true }).click();
    await page.getByLabel("درجة الواجب").fill("4.5");
    await page.getByLabel("تعليق الواجب").fill("Clear working and units.");
    await page.getByRole("button", { name: "اعتماد وحفظ الدرجة" }).click();
    await expect(page.getByLabel("درجة الواجب")).toHaveCount(0);
    const submissions = await (await student.request.get(`${base}/api/v1/submissions/me`)).json();
    const submitted = submissions.find((item: { assignment_id: string }) => item.assignment_id === assignment.id);
    expect(submitted.final_score).toBe(4.5);
    expect(submitted.teacher_feedback).toBe("Clear working and units.");
  } finally {
    const csrf = (await studentContext.cookies()).find(c => c.name === "matgar_csrf")?.value;
    if (csrf) expect.soft((await student.request.post(`${base}/api/v1/auth/logout`, { headers: { "X-CSRF-Token": csrf } })).status()).toBe(204);
    await studentContext.close();
  }
});
}
