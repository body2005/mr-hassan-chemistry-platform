import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: false,
    // Bound jsdom forks on developer/CI hosts alongside the Docker QA stack.
    // Keep per-file isolation and all tests; only execution concurrency changes.
    maxWorkers: 2,
    include: ["src/**/*.test.{ts,tsx}"],
    reporters: "default",
  },
});
