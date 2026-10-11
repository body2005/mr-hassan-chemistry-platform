import type { APIRequest, APIRequestContext } from "@playwright/test";
import { expect, test } from "./qaTest";
import { cookieApi } from './cookieApi';

const validPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==",
  "base64",
);

async function login(request: APIRequest, email: string, password: string): Promise<APIRequestContext> {
  return (await cookieApi(request, email, password)).context;
}

test("receipt review grants only the paying student access and sends notifications", async ({ playwright, page, browser }) => {
  const teacher = await login(playwright.request, "teacher@demo.com", "qa-teacher-pass");
  const otherTeacher = await login(playwright.request, "teacher2@example.com", "qa-teacher2-pass");
  const student = await login(playwright.request, "student04@demo.com", "qa-student-pass");
  const otherStudent = await login(playwright.request, "student05@demo.com", "qa-student-pass");
  try {
    const stamp = Date.now();
    const courseResponse = await teacher.post("courses", { data: { code: `QAPAY${stamp}`, title: "QA Payment Course" } });
    expect(courseResponse.status(), await courseResponse.text()).toBe(201);
    const course = await courseResponse.json();
    const moduleResponse = await teacher.post(`courses/${course.id}/modules`, { data: { title: "QA Paid Unit", position: 1 } });
    expect(moduleResponse.status()).toBe(201);
    const module = await moduleResponse.json();
    const lessonResponse = await teacher.post(`modules/${module.id}/lessons`, {
      data: { title: `QA Paid Lesson ${stamp}`, kind: "article", position: 1, content: "Only after approval", price_egp: 25 },
    });
    expect(lessonResponse.status()).toBe(201);
    const lesson = await lessonResponse.json();
    const materialResponse = await teacher.post(`lessons/${lesson.id}/materials`, {
      multipart: { file: { name: "qa-paid.txt", mimeType: "text/plain", buffer: Buffer.from("Paid QA material") } },
    });
    expect(materialResponse.status()).toBe(201);
    const material = await materialResponse.json();
    expect((await teacher.post(`courses/${course.id}/publish`)).status()).toBe(200);
    expect((await student.post(`courses/${course.id}/enroll`)).status()).toBe(200);
    expect((await otherStudent.post(`courses/${course.id}/enroll`)).status()).toBe(200);
    const download = `lessons/${lesson.id}/materials/${material.id}/download`;
    expect((await student.get(download)).status()).toBe(403);

    const create = await student.post("payments/orders", {
      data: { product_type: "lesson", product_id: lesson.id, payment_method: "instapay", payer_reference: `QA-${stamp}` },
    });
    expect(create.status(), await create.text()).toBe(201);
    const order = await create.json();
    expect(order.status).toBe("pending");
    expect((await otherStudent.get(`payments/orders/${order.id}`)).status()).toBe(404);

    const fake = await student.post(`payments/orders/${order.id}/receipt`, {
      multipart: { receipt: { name: "fake.png", mimeType: "image/png", buffer: Buffer.from("not a PNG") } },
    });
    expect(fake.status(), await fake.text()).toBe(422);
    const studentBrowser = await browser.newContext({ ignoreHTTPSErrors: false });
    try {
      const studentPage = await studentBrowser.newPage();
      await studentPage.goto("/#auth");
      const studentSignIn = studentPage.locator("form").first();
      await studentSignIn.locator('input[type="text"]').fill("student04@demo.com");
      await studentSignIn.locator('input[type="password"]').fill("qa-student-pass");
      await studentSignIn.locator('button[type="submit"]').click();
      await expect(studentPage).toHaveURL(/#mycourses$/);
      await studentPage.goto("/#payments");
      await studentPage.getByLabel("الدرس المطلوب تفعيله").selectOption(lesson.id);
      await studentPage.locator('input[name="method"]').first().check();
      await studentPage.locator('input[type="file"]').setInputFiles({ name: "real.png", mimeType: "image/png", buffer: validPng });
      await studentPage.getByRole("button", { name: /إرسال الإيصال وتأكيد الدفع/ }).click();
      await expect(studentPage.locator('.toast-stack').getByText("تم إرسال الإيصال للمراجعة", { exact: false })).toBeVisible();
      await expect(studentPage.locator('.sr-only[role="status"]')).toContainText('تم إرسال الإيصال للمراجعة');
    } finally {
      await studentBrowser.close();
    }
    expect((await (await student.get(`payments/orders/${order.id}`)).json()).status).toBe("under_review");
    expect((await otherStudent.get(`payments/orders/${order.id}/receipt`)).status()).toBe(404);
    expect((await otherTeacher.post(`payments/orders/${order.id}/approve`, { data: {} })).status()).toBe(404);
    expect((await student.get(download)).status()).toBe(403);

    await page.goto("/#auth");
    const signIn = page.locator("form").first();
    await signIn.locator('input[type="text"]').fill("teacher@demo.com");
    await signIn.locator('input[type="password"]').fill("qa-teacher-pass");
    await signIn.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/#lessonmanagement$/);
    await page.goto("/#paymentmanagement");
    const row = page.locator(".review-row").filter({ hasText: lesson.title });
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "تفعيل" }).click();
    await page.getByRole("dialog", { name: "تأكيد استلام المبلغ" }).getByRole("button", { name: "تفعيل الآن" }).click();
    // Substring matching also matches "QA Paid Lesson" before approval commits.
    // Wait for the actual state, not the product title, before checking access.
    await expect(row.getByText("paid", { exact: true })).toBeVisible();
    expect((await (await teacher.get(`payments/orders/${order.id}`)).json()).status).toBe("paid");
    expect((await student.get(download)).status()).toBe(200);
    expect((await otherStudent.get(download)).status()).toBe(403);
    const entitlements = await (await student.get("payments/me/entitlements")).json();
    expect(entitlements.some((item: { resource_id: string; active: boolean }) => item.resource_id === lesson.id && item.active)).toBe(true);
    const notifications = await (await student.get("notifications")).json();
    expect(notifications.some((item: { title: string }) => item.title.includes("تم تأكيد الدفع"))).toBe(true);
  } finally {
    await Promise.all([teacher.dispose(), otherTeacher.dispose(), student.dispose(), otherStudent.dispose()]);
  }
});
