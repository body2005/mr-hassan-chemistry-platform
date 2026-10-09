import { expect, test } from "./qaTest";
import { cookieApi } from './cookieApi';

test("student can switch between two enrolled courses", async ({ page, playwright }) => {
  const assessmentCourseIds: string[] = [];
  page.on('request', request => {
    const match = new URL(request.url()).pathname.match(/^\/api\/v1\/courses\/([^/]+)\/assessments$/);
    if (match) assessmentCourseIds.push(match[1]);
  });
  const teacher = (await cookieApi(playwright.request, 'teacher@demo.com', 'qa-teacher-pass')).context;
  const student = (await cookieApi(playwright.request, 'student03@demo.com', 'qa-student-pass')).context;
  try {
    const names = [`QA First Course ${Date.now()}`, `QA Second Course ${Date.now()}`];
    const ids: string[] = [];
    for (const [index, title] of names.entries()) {
      const created = await teacher.post("courses", { data: { code: `QASW${Date.now()}${index}`, title } });
      expect(created.status(), await created.text()).toBe(201);
      const course = await created.json();
      ids.push(course.id);
      const moduleResponse = await teacher.post(`courses/${course.id}/modules`, { data: { title: "QA Unit", position: 1 } });
      expect(moduleResponse.status()).toBe(201);
      const module = await moduleResponse.json();
      expect((await teacher.post(`modules/${module.id}/lessons`, { data: { title: "QA Lesson", kind: "article", position: 1, content: "QA only", price_egp: 0 } })).status()).toBe(201);
      expect((await teacher.post(`courses/${course.id}/publish`)).status()).toBe(200);
      expect((await student.post(`courses/${course.id}/enroll`)).status()).toBe(200);
    }
    const questionResponse = await teacher.post("questions", {
      data: { course_id: ids[0], question_type: "multiple_choice", prompt: "QA UI: What is H2O?", options: ["Water", "Salt"], correct_answer: "Water", points: 5 },
    });
    expect(questionResponse.status()).toBe(201);
    const question = await questionResponse.json();
    const quizTitle = `QA Browser Quiz ${Date.now()}`;
    const quizResponse = await teacher.post("quizzes", {
      data: { course_id: ids[0], title: quizTitle, question_ids: [question.id], duration_seconds: 120 },
    });
    expect(quizResponse.status()).toBe(201);
    const quiz = await quizResponse.json();
    expect((await teacher.post(`quizzes/${quiz.id}/publish`)).status()).toBe(200);

    await page.goto("/#auth");
    const form = page.locator("form").first();
    await form.locator('input[type="text"]').first().fill("student03@demo.com");
    await form.locator('input[type="password"]').first().fill("qa-student-pass");
    await form.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/#mycourses$/);
    const selector = page.getByLabel("اختر المقرر");
    await expect(selector).toBeVisible();
    await expect(selector.locator(`option[value="${ids[0]}"]`)).toHaveText(names[0]);
    await expect(selector.locator(`option[value="${ids[1]}"]`)).toHaveText(names[1]);
    await selector.selectOption(ids[1]);
    await expect(page.locator("h1").first()).toHaveText(names[1]);
    await selector.selectOption(ids[0]);
    await expect(page.locator("h1").first()).toHaveText(names[0]);
    await page.getByRole("button", { name: "الاختبارات والكويزات" }).click();
    await expect(page.getByText(quizTitle)).toBeVisible();
    await page.getByRole("button", { name: "بدء حل الاختبار" }).click();
    await expect(page.getByText("QA UI: What is H2O?")).toBeVisible();
    await page.getByText("Water", { exact: true }).click();
    await page.getByRole("button", { name: "تسليم الاختبار" }).last().click();
    await page.getByRole("button", { name: "نعم، تأكيد وتسليم الآن" }).click();
    await expect(page.getByText("تم تسليم الاختبار وتصحيحه فورياً")).toBeVisible();
    await page.getByRole('button', { name: 'العودة إلى المقرر', exact: true }).click();
    await expect(page.getByRole('button', { name: `نسبة إنجاز المقرر: ${names[0]}`, exact: true })).toHaveText('50%');
    // Many retained synthetic enrollments must not fan out assessment reads.
    expect(new Set(assessmentCourseIds)).toEqual(new Set(ids));
  } finally {
    await Promise.all([teacher.dispose(), student.dispose()]);
  }
});
