import { expect, test } from "@playwright/test";


const viewports = [
  { width: 320, height: 568 },
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
];

for (const language of ["ar", "en"] as const) {
  for (const viewport of viewports) {
    test(`${language} has no horizontal overflow at ${viewport.width}x${viewport.height}`, async ({ page }) => {
      await page.addInitScript((lang) => localStorage.setItem("lms_lang", lang), language);
      await page.setViewportSize(viewport);
      await page.goto("/", { waitUntil: "networkidle" });

      await expect(page.locator("html")).toHaveAttribute("lang", language);
      await expect(page.locator("html")).toHaveAttribute("dir", language === "ar" ? "rtl" : "ltr");
      const dimensions = await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        content: document.documentElement.scrollWidth,
      }));
      expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
    });
  }
}
