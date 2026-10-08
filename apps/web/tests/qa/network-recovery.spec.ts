import { expect, test } from "./qaTest";

for (const status of [429, 503]) {
test(`persistent bootstrap ${status} stops automatic requests and permits explicit recovery`, async ({ page }) => {
  await page.goto('/#auth');
  const form = page.locator('form').first();
  await form.locator('input[type="text"]').fill('student06@demo.com');
  await form.locator('input[type="password"]').fill('qa-student-pass');
  await form.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/#mycourses$/);
  await expect(page.locator('.student-course-list, .my-courses-view, .profile-button').first()).toBeVisible();
  let requests = 0;
  let recover = false;
  await page.route('**/api/v1/bootstrap', async route => {
    requests++;
    if (recover) return route.continue();
    return route.fulfill({ status, headers: { 'Retry-After': '2' }, json: { detail: 'Persistent synthetic bootstrap outage' } });
  });
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('الخدمة غير متاحة مؤقتًا');
  await page.waitForTimeout(12_000); // Beyond2+3+4.5s retries AND Retry-After.
  expect(requests).toBe(status === 429 ? 1 : 4);
  const stopped = requests;
  // Cross the former fourth auto-retry at16.25s too. A15s observation
  // falsely passed the old unbounded503 policy during its next backoff.
  await page.waitForTimeout(8000);
  expect(requests).toBe(stopped);
  expect((await page.request.get('/api/v1/auth/me')).status()).toBe(200);
  recover = true;
  await page.getByRole('button', { name: 'إعادة المحاولة الآن' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('.profile-button')).toBeVisible();
  expect(requests).toBe(stopped + 1);
});
}

test("authenticated dashboard recovers after a failed bootstrap without a request storm", async ({ page }) => {
  await page.goto("/#auth");
  const form = page.locator("form").first();
  await form.locator('input[type="text"]').fill("student06@demo.com");
  await form.locator('input[type="password"]').fill("qa-student-pass");
  await form.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/#mycourses$/);

  let bootstrapRequests = 0;
  await page.route("**/api/v1/bootstrap", async (route) => {
    bootstrapRequests += 1;
    if (bootstrapRequests === 1) await route.abort("failed");
    else await route.continue();
  });
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("الخدمة غير متاحة مؤقتًا");
  expect(bootstrapRequests).toBe(1);
  await page.getByRole("button", { name: "إعادة المحاولة الآن" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.locator(".sidebar-bottom .profile-button")).toBeVisible();
  expect(bootstrapRequests).toBe(2);
});

test("real login 429 does not trigger automatic retries", async ({ page, playwright }) => {
  const client = await playwright.request.newContext({
    baseURL: process.env.QA_BASE_URL || "http://127.0.0.1:18080",
    ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true",
  });
  try {
    let limited = false;
    for (let number = 0; number < 24; number += 1) {
      const response = await client.post("/api/v1/auth/login", {
        data: { email: `qa-abuse-${number}@example.invalid`, password: "incorrect", institution_slug: "demo" },
      });
      if (response.status() === 429) {
        expect(Number(response.headers()["retry-after"])).toBeGreaterThan(0);
        limited = true;
        break;
      }
      expect(response.status()).toBe(401);
    }
    expect(limited).toBe(true);
    await page.goto("/#auth");
    let loginRequests = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/auth/login")) loginRequests += 1;
    });
    const form = page.locator("form").first();
    await form.locator('input[type="text"]').fill("student06@demo.com");
    await form.locator('input[type="password"]').fill("qa-student-pass");
    const limitedResponse = page.waitForResponse((response) => response.url().endsWith("/auth/login") && response.status() === 429);
    await form.locator('button[type="submit"]').click();
    await limitedResponse;
    await expect(page.getByRole("alert")).toBeVisible();
    await page.waitForTimeout(2000);
    expect(loginRequests).toBe(1);
    expect(page.url()).toContain("#auth");
  } finally {
    await client.dispose();
  }
});
