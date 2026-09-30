import { expect, test } from "./qaTest";

type MailpitMessage = { ID: string; To: { Address: string }[] };

test("password reset email completes the browser journey and invalidates the old password", async ({ page, browser, request }) => {
  const email = `qa-reset-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const oldPassword = "Qa-reset-original-2026!";
  const newPassword = "Qa-reset-new-2026!";

  await page.goto("/#auth");
  await page.getByRole("button", { name: "تسجيل جديد" }).click();
  const registration = page.locator("form").first();
  await registration.locator('input[type="text"]').first().fill("طالب اختبار الاسترجاع");
  await registration.locator('input[type="email"]').fill(email);
  await registration.locator('input[type="password"]').nth(0).fill(oldPassword);
  await registration.locator('input[type="password"]').nth(1).fill(oldPassword);
  await registration.locator("select").nth(0).selectOption("2nd_secondary");
  await registration.locator("select").nth(1).selectOption("CAIRO");
  await registration.locator('input[placeholder="اسم المدرسة"]').fill("مدرسة QA المحلية");
  await registration.locator("select").nth(2).selectOption("MALE");
  await registration.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/#mycourses$/);

  const freshContext = await browser.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true" });
  try {
    const resetPage = await freshContext.newPage();
    await resetPage.goto("/#auth");
    await resetPage.getByRole("button", { name: "نسيت كلمة المرور؟" }).click();
    await resetPage.getByRole("textbox", { name: "بريد الاسترجاع" }).fill(email);
    await resetPage.getByRole("button", { name: "إرسال رابط الاسترجاع" }).click();
    await expect(resetPage.getByText("إذا كان الحساب موجودًا، ستصلك رسالة الاسترجاع.")).toBeVisible();

    let messageId = "";
    await expect.poll(async () => {
      const response = await request.get(`${process.env.QA_MAILPIT_URL || "http://127.0.0.1:18025"}/api/v1/messages`);
      expect(response.ok()).toBeTruthy();
      const inbox = await response.json() as { messages: MailpitMessage[] };
      messageId = inbox.messages.find((message) => message.To.some((recipient) => recipient.Address === email))?.ID || "";
      return messageId;
    }).not.toBe("");
    const message = await request.get(`${process.env.QA_MAILPIT_URL || "http://127.0.0.1:18025"}/api/v1/message/${messageId}`);
    expect(message.ok()).toBeTruthy();
    const body = (await message.json() as { Text: string }).Text;
    const token = body.match(/reset_token=([A-Za-z0-9_-]+)/)?.[1];
    expect(token).toBeTruthy();

    await resetPage.goto(`/#auth?reset_token=${token}`);
    await resetPage.getByLabel("كلمة المرور الجديدة", { exact: true }).fill(newPassword);
    await resetPage.getByLabel("تأكيد كلمة المرور الجديدة").fill(newPassword);
    await resetPage.getByRole("button", { name: "تغيير كلمة المرور" }).click();
    await expect(resetPage).toHaveURL(/#auth$/);
    await expect(resetPage.getByText("تم تغيير كلمة المرور. سجّل الدخول بالكلمة الجديدة.")).toBeVisible();

    const oldLogin = await request.post(`${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/api/v1/auth/login`, {
      data: { email, password: oldPassword, institution_slug: "demo" },
    });
    expect(oldLogin.status()).toBe(401);
    const usedToken = await request.post(`${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/api/v1/auth/password-reset/confirm`, {
      data: { token, new_password: "Qa-reuse-must-fail-2026!" },
    });
    expect(usedToken.status()).toBe(400);

    const signIn = resetPage.locator("form").first();
    await signIn.locator('input[type="text"]').fill(email);
    await signIn.locator('input[type="password"]').fill(newPassword);
    await signIn.locator('button[type="submit"]').click();
    await expect(resetPage).toHaveURL(/#mycourses$/);
  } finally {
    await freshContext.close();
  }
});
