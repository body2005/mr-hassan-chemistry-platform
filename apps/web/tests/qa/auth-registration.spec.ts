import { expect, test } from "./qaTest";

test("student registers from the browser and can sign in again", async ({ page, browser }) => {
  const email = `qa-register-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const password = "Qa-Registration-2026!";

  await page.addInitScript(() => localStorage.setItem('lms_session_token', 'legacy-test-credential'));
  const authorizationHeaders: string[] = [];
  page.on('request', request => {
    const header = request.headers()['authorization'];
    if (header) authorizationHeaders.push(header);
  });

  await page.goto("/#auth");
  await page.getByRole("button", { name: "تسجيل جديد" }).click();
  await expect(page.locator('.registration-steps li')).toHaveCount(2);
  const form = page.locator("form").first();
  await page.getByLabel('الاسم الأول').fill('أحمد');
  await page.getByLabel('الاسم الأوسط').fill('محمد');
  await page.getByLabel('الاسم الأخير').fill('حسن');
  await page.getByRole('radio', { name: 'ذكر', exact: true }).check();
  await page.getByLabel('السنة الدراسية').selectOption('2nd_secondary');
  await page.getByRole('button', { name: 'التالي', exact: true }).click();
  await page.getByLabel('رقم تليفونك الشخصي').fill('01012345678');
  await page.getByLabel('رقم ولي الأمر').fill('01112345678');
  await page.getByLabel('المحافظة').selectOption('CAIRO');
  await page.getByLabel('المدينة أو المنطقة').fill('البساتين');
  await page.getByLabel('اسم المدرسة').fill('مدرسة QA المحلية');
  await page.getByLabel('البريد الإلكتروني').fill(email);
  await form.locator('input[name="password"]').fill(password);
  await page.getByLabel('تأكيد كلمة المرور').fill(password);
  await expect(page.getByRole('heading', { name: 'التواصل وإنشاء الحساب' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'التالي', exact: true })).toHaveCount(0);
  const registered = page.waitForResponse(r => r.url().endsWith('/auth/register'));
  await page.getByRole('button', { name: 'إنشاء حسابي', exact: true }).click();
  expect(await (await registered).json()).not.toHaveProperty('token');

  await expect(page).toHaveURL(/#mycourses$/);
  expect(await page.evaluate(() => localStorage.getItem('lms_session_token'))).toBeNull();
  expect(await page.evaluate(() => document.cookie.includes('matgar_session='))).toBe(false);
  const access = (await page.context().cookies()).find(c => c.name === 'matgar_session');
  expect(access?.httpOnly).toBe(true);
  expect(access?.secure).toBe(true);
  await page.reload();
  await expect(page.locator('.profile-button')).toHaveCount(1);
  expect(await page.evaluate(() => localStorage.getItem('lms_session_token'))).toBeNull();
  expect(authorizationHeaders).toEqual([]);

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
