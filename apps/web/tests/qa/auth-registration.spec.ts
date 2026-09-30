import { expect, test } from "./qaTest";

test("student registers from the browser and can sign in again", async ({ page, browser }) => {
  const email = `qa-register-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const password = "Qa-Registration-2026!";

  await page.goto("/#auth");
  await page.getByRole("button", { name: "تسجيل جديد" }).click();
  const form = page.locator("form").first();
  await form.locator('input[type="text"]').first().fill("طالب اختبار التسجيل");
  await form.locator('input[type="email"]').fill(email);
  await form.locator('input[type="password"]').nth(0).fill(password);
  await form.locator('input[type="password"]').nth(1).fill(password);
  await form.locator("select").nth(0).selectOption("2nd_secondary");
  await form.locator("select").nth(1).selectOption("CAIRO");
  await form.locator('input[placeholder="اسم المدرسة"]').fill("مدرسة QA المحلية");
  await form.locator("select").nth(2).selectOption("MALE");
  await form.locator('button[type="submit"]').click();

  await expect(page).toHaveURL(/#mycourses$/);

  const freshContext = await browser.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true" });
  try {
    const freshPage = await freshContext.newPage();
    await freshPage.goto("/#auth");
    const signIn = freshPage.locator("form").first();
    await signIn.locator('input[type="text"]').fill(email);
    await signIn.locator('input[type="password"]').fill(password);
    await signIn.locator('button[type="submit"]').click();
    await expect(freshPage).toHaveURL(/#mycourses$/);
  } finally {
    await freshContext.close();
  }
});
