import { readFile } from "node:fs/promises";
import { unzipSync } from "fflate";
import { expect, test } from "./qaTest";

test("teacher downloads a valid RTL Excel report", async ({ page }) => {
  await page.goto("/#auth");
  const form = page.locator("form").first();
  await form.locator('input[type="text"]').first().fill("teacher@demo.com");
  await form.locator('input[type="password"]').first().fill("qa-teacher-pass");
  await form.locator('button[type="submit"]').click();
  await expect(page.locator(".sidebar-bottom .profile-button")).toBeVisible();
  await page.getByRole("button", { name: "Open Menu" }).click();
  await page.locator(".nav-item").nth(2).click();
  await expect(page).toHaveURL(/#submissions$/);
  await page.getByRole("button", { name: "تصدير التقرير" }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /تصدير Excel/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
  const bytes = await readFile(await download.path());
  expect(bytes.subarray(0, 2).toString()).toBe("PK");
  const files = unzipSync(bytes);
  const worksheet = new TextDecoder().decode(files["xl/worksheets/sheet1.xml"]);
  expect(worksheet).toMatch(/rightToLeft="(?:1|true)"/);
  expect(worksheet).toContain("<sheetData>");
});
