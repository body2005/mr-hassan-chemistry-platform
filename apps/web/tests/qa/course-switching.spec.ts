import { expect, test } from "./qaTest";

const baseURL = `${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/api/v1/`;

test("student can switch between two enrolled courses", async ({ page, playwright }) => {
  const loginContext = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true", baseURL });
  const login = await loginContext.post("auth/login", {
    data: { email: "teacher@demo.com", password: "qa-teacher-pass", institution_slug: "demo" },
  });
  expect(login.status()).toBe(200);
  const token = (await login.json()).token as string;
  await loginContext.dispose();
  const teacher = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true", baseURL, extraHTTPHeaders: { Authorization: `Bearer ${token}` } });
  const studentLogin = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true", baseURL });
  const studentResponse = await studentLogin.post("auth/login", {
    data: { email: "student03@demo.com", password: "qa-student-pass", institution_slug: "demo" },
  });
  expect(studentResponse.status()).toBe(200);
  const studentToken = (await studentResponse.json()).token as string;
  await studentLogin.dispose();
  const student = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true", baseURL, extraHTTPHeaders: { Authorization: `Bearer ${studentToken}` } });
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
  } finally {
    await Promise.all([teacher.dispose(), student.dispose()]);
  }
});
