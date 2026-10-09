import { expect, test } from "./qaTest";

test("profile changes password and revokes all browser sessions", async ({ page, browser }) => {
  const email = `qa-security-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const oldPassword = "Qa-Old-Password-2026!";
  const newPassword = "Qa-New-Password-2026!";

  await page.goto("/#auth");
  await page.getByRole("button", { name: "تسجيل جديد" }).click();
  await expect(page.locator('.registration-steps li')).toHaveCount(2);
  const registration = page.locator("form").first();
  await page.getByLabel('الاسم الأول').fill('طالب');
  await page.getByLabel('الاسم الأوسط').fill('اختبار');
  await page.getByLabel('الاسم الأخير').fill('الأمان');
  await page.getByRole('radio', { name: 'ذكر', exact: true }).check();
  await page.getByLabel('السنة الدراسية').selectOption('2nd_secondary');
  await page.getByRole('button', { name: 'التالي', exact: true }).click();
  await page.getByLabel('رقم تليفونك الشخصي').fill('01012345678');
  await page.getByLabel('رقم ولي الأمر').fill('01112345678');
  await page.getByLabel('المحافظة').selectOption('CAIRO');
  await page.getByLabel('المدينة أو المنطقة').fill('البساتين');
  await page.getByLabel('اسم المدرسة').fill('مدرسة QA المحلية');
  await page.getByLabel('البريد الإلكتروني').fill(email);
  await registration.locator('input[name="password"]').fill(oldPassword);
  await page.getByLabel('تأكيد كلمة المرور').fill(oldPassword);
  await expect(page.getByRole('heading', { name: 'التواصل وإنشاء الحساب', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'إنشاء حسابي', exact: true }).click();
  await expect(page).toHaveURL(/#mycourses$/);

  const secondContext = await browser.newContext({ ignoreHTTPSErrors: false });
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
    await page.getByRole('button', { name: 'Toggle Theme' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(security.locator('input')).toHaveCount(0);
    await security.getByRole("button", { name: "تغيير كلمة المرور" }).click();
    const wizard = page.getByRole('dialog', { name: 'تغيير كلمة المرور' });
    await wizard.getByRole('button', { name: 'نسيت كلمة المرور الحالية؟' }).click();
    await expect(wizard.getByLabel('البريد الإلكتروني')).toHaveValue(email);
    const reset = page.waitForResponse(r => r.url().endsWith('/auth/password-reset/request'));
    await wizard.getByRole('button', { name: 'إرسال رابط الاسترجاع' }).click();
    expect((await reset).status()).toBe(200);
    await expect(wizard.getByRole('status')).toContainText('إذا كان البريد مرتبطًا بحساب');
    const mailUrl = process.env.QA_MAILPIT_URL || 'http://127.0.0.1:18525';
    await expect.poll(async () => {
      const inbox = await (await page.request.get(`${mailUrl}/api/v1/messages`)).json();
      return inbox.messages.some((message: { To: { Address: string }[] }) => message.To.some(recipient => recipient.Address === email));
    }, { timeout: 30_000 }).toBe(true);
    await wizard.getByRole('button', { name: 'تم', exact: true }).click();
    await expect(security.getByRole('button', { name: 'تغيير كلمة المرور' })).toBeFocused();
    await security.getByRole('button', { name: 'تغيير كلمة المرور' }).click();
    await wizard.getByLabel("كلمة المرور الحالية").fill('Wrong-current-password-2026!');
    await wizard.getByRole('button', { name: 'متابعة', exact: true }).click();
    await wizard.getByLabel("كلمة المرور الجديدة", { exact: true }).fill(newPassword);
    await wizard.getByLabel("تأكيد كلمة المرور الجديدة").fill(newPassword);
    await expect(wizard.getByLabel('كلمة المرور الجديدة', { exact: true })).toHaveCSS('background-color', 'rgb(30, 41, 59)');
    await page.screenshot({ path: test.info().outputPath('password-wizard-dark.png') });
    const rejected = page.waitForResponse(r => r.url().endsWith('/auth/change-password'));
    await wizard.getByRole("button", { name: "حفظ كلمة المرور الجديدة" }).click();
    expect((await rejected).status()).toBe(400);
    await expect(wizard.getByRole('alert')).toBeVisible();
    await wizard.getByRole('button', { name: 'رجوع', exact: true }).click();
    await wizard.getByLabel('كلمة المرور الحالية').fill(oldPassword);
    await wizard.getByRole('button', { name: 'متابعة', exact: true }).click();
    await wizard.getByRole("button", { name: "حفظ كلمة المرور الجديدة" }).click();
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
    await expect(page.getByRole("button", { name: "تسجيل الخروج من جميع الأجهزة" })).toHaveCount(0);
    // The requested UI removal must not remove the server's revocation control.
    const csrf = (await page.context().cookies()).find(c => c.name === 'matgar_csrf')?.value || '';
    const revoked = await page.request.post('/api/v1/auth/revoke-all', { headers: { 'X-CSRF-Token': csrf } });
    expect(revoked.ok()).toBe(true);
    await page.reload();
    await expect(page.locator(".sidebar-bottom .profile-button")).toHaveCount(0);
  } finally {
    await secondContext.close();
  }
});
