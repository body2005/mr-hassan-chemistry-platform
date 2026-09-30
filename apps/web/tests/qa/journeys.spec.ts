import { expect, test } from "./qaTest";

type BrowserIssue = { kind: string; detail: string };

async function login(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/#auth");
  const form = page.locator("form").first();
  await form.locator('input[type="text"]').first().fill(email);
  await form.locator('input[type="password"]').first().fill(password);
  await form.locator('button[type="submit"]').click();
  await expect(page.locator(".sidebar-bottom .profile-button")).toBeVisible();
}

function observe(page: import("@playwright/test").Page) {
  const issues: BrowserIssue[] = [];
  const requests: string[] = [];
  page.on("pageerror", (error) => issues.push({ kind: "pageerror", detail: error.message }));
  page.on("console", (message) => {
    if (message.type() === "error") issues.push({ kind: "console", detail: message.text() });
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/v1/")) {
      requests.push(`${response.request().method()} ${new URL(response.url()).pathname} ${response.status()}`);
      if (response.status() >= 400) {
        issues.push({ kind: "http", detail: requests[requests.length - 1] });
      }
    }
  });
  page.on("requestfailed", (request) => {
    const failure = request.failure()?.errorText || "";
    if (!failure.includes("ERR_ABORTED") && !failure.includes("NS_BINDING_ABORTED")) {
      issues.push({ kind: "network", detail: `${request.url()} ${failure}` });
    }
  });
  return { issues, requests };
}

test("student can log in, navigate dashboard and profile, then log out in Arabic RTL", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const observed = observe(page);
  await login(page, "student01@demo.com", "qa-student-pass");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page).toHaveURL(/#mycourses$/);
  await page.getByRole("button", { name: "Open Menu" }).click();
  await page.locator(".profile-button").click();
  await expect(page).toHaveURL(/#profile$/);
  await page.goBack();
  await expect(page).toHaveURL(/#mycourses$/);
  await page.getByRole("button", { name: "Open Menu" }).click();
  await page.locator(".profile-button").click();
  await page.getByRole("button", { name: "تسجيل الخروج" }).first().click();
  await page.getByRole("button", { name: "تسجيل الخروج" }).last().click();
  await expect(page.locator(".sidebar-bottom .profile-button")).toHaveCount(0);
  console.log(JSON.stringify({ role: "student", requests: observed.requests, issues: observed.issues }));
  expect(observed.issues).toEqual([]);
});

test("teacher can log in and navigate lessons, submissions and profile", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  const observed = observe(page);
  await login(page, "teacher@demo.com", "qa-teacher-pass");
  await expect(page).toHaveURL(/#lessonmanagement$/);
  await page.getByRole("button", { name: "Open Menu" }).click();
  await page.locator(".nav-item").nth(2).click();
  await expect(page).toHaveURL(/#submissions$/);
  await page.getByRole("button", { name: "Open Menu" }).click();
  await page.locator(".profile-button").click();
  await expect(page).toHaveURL(/#profile$/);
  console.log(JSON.stringify({ role: "teacher", requests: observed.requests, issues: observed.issues }));
  expect(observed.issues.filter((item) => item.kind === "pageerror")).toEqual([]);
});
