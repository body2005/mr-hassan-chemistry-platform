import { expect, test } from "./qaTest";

test("profile changes password and revokes all browser sessions", async ({ page, browser }) => {
  const email = `qa-security-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const oldPassword = "Qa-Old-Password-2026!";
  const newPassword = "Qa-New-Password-2026!";

  await page.goto("/#auth");
  await page.getByRole("button", { name: "تسجيل جديد" }).click();
  const registration = page.locator("form").first();
  await registration.locator('input[type="text"]').first().fill("طالب اختبار الأمان");
  await registration.locator('input[type="email"]').fill(email);
  await registration.locator('input[type="password"]').nth(0).fill(oldPassword);
  await registration.locator('input[type="password"]').nth(1).fill(oldPassword);
  await registration.locator("select").nth(0).selectOption("2nd_secondary");
  await registration.locator("select").nth(1).selectOption("CAIRO");
  await registration.locator('input[placeholder="اسم المدرسة"]').fill("مدرسة QA المحلية");
  await registration.locator("select").nth(2).selectOption("MALE");
  await registration.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/#mycourses$/);

  const secondContext = await browser.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true" });
  try {
    const secondPage = await secondContext.newPage();
    await secondPage.goto("/#auth");
    const secondLogin = secondPage.locator("form").first();
    await secondLogin.locator('input[type="text"]').fill(email);
    await secondLogin.locator('input[type="password"]').fill(oldPassword);
    await secondLogin.locator('button[type="submit"]').click();
    await expect(secondPage).toHaveURL(/#mycourses$/);

    await page.getByRole("button", { name: "Open Menu" }).click();
    await page.locator(".profile-button").click();
    const security = page.getByRole("region", { name: "أمان الحساب" });
    await security.getByLabel("كلمة المرور الحالية").fill(oldPassword);
    await security.getByLabel("كلمة المرور الجديدة", { exact: true }).fill(newPassword);
    await security.getByLabel("تأكيد كلمة المرور الجديدة").fill(newPassword);
    await security.getByRole("button", { name: "تغيير كلمة المرور" }).click();
    await expect(page.locator(".sidebar-bottom .profile-button")).toHaveCount(0);

    await secondPage.reload();
    await expect(secondPage.locator(".sidebar-bottom .profile-button")).toHaveCount(0);

    await page.goto("/#auth");
    const login = page.locator("form").first();
    await login.locator('input[type="text"]').fill(email);
    await login.locator('input[type="password"]').fill(newPassword);
    await login.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/#mycourses$/);

    await page.getByRole("button", { name: "Open Menu" }).click();
    await page.locator(".profile-button").click();
    await page.getByRole("button", { name: "تسجيل الخروج من جميع الأجهزة" }).click();
    await page.getByRole("button", { name: "إنهاء الجلسات" }).click();
    await expect(page.locator(".sidebar-bottom .profile-button")).toHaveCount(0);
  } finally {
    await secondContext.close();
  }
});
