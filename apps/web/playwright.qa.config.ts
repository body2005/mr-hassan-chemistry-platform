import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.ts",
  outputDir: process.env.QA_PLAYWRIGHT_OUTPUT || "../../.qa/playwright/results",
  reporter: [["list"]],
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: process.env.QA_BASE_URL || "http://127.0.0.1:18080",
    ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
