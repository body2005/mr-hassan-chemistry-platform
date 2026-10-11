import { expect, test } from "./qaTest";

const baseURL = `${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/api/v1/`;

test("cookie mutations require CSRF and reject an untrusted Origin", async ({ playwright }) => {
  const context = await playwright.request.newContext({ ignoreHTTPSErrors: false, baseURL });
  try {
    const login = await context.post("auth/login", {
      data: { email: "teacher@demo.com", password: "qa-teacher-pass", institution_slug: "demo" },
    });
    expect(login.status()).toBe(200);
    const cookies = (await context.storageState()).cookies;
    const csrf = cookies.find((cookie) => cookie.name === "matgar_csrf")?.value;
    expect(csrf).toBeTruthy();
    const courseData = { code: `QASEC${Date.now()}`, title: "QA Security Boundary" };

    const noCsrf = await context.post("courses", { data: courseData });
    expect(noCsrf.status()).toBe(403);
    expect((await noCsrf.json()).detail).toBe("CSRF validation failed");

    const badOrigin = await context.post("courses", {
      headers: { Origin: "https://untrusted.example", "X-CSRF-Token": csrf! },
      data: courseData,
    });
    expect(badOrigin.status()).toBe(403);
    expect((await badOrigin.json()).detail).toBe("Origin is not allowed");

    const allowed = await context.post("courses", {
      headers: { Origin: (process.env.QA_BASE_URL || "http://127.0.0.1:18080"), "X-CSRF-Token": csrf! },
      data: courseData,
    });
    expect(allowed.status(), await allowed.text()).toBe(201);
  } finally {
    await context.dispose();
  }
});

test("CORS preflight only authorizes the configured QA origin", async ({ playwright }) => {
  const context = await playwright.request.newContext({ ignoreHTTPSErrors: false, baseURL });
  try {
    const headers = { "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,x-csrf-token" };
    const allowed = await context.fetch("courses", { method: "OPTIONS", headers: { ...headers, Origin: (process.env.QA_BASE_URL || "http://127.0.0.1:18080") } });
    expect(allowed.status()).toBe(200);
    expect(allowed.headers()["access-control-allow-origin"]).toBe((process.env.QA_BASE_URL || "http://127.0.0.1:18080"));
    const denied = await context.fetch("courses", { method: "OPTIONS", headers: { ...headers, Origin: "https://untrusted.example" } });
    expect(denied.status()).toBe(400);
    expect(denied.headers()["access-control-allow-origin"]).toBeUndefined();
  } finally {
    await context.dispose();
  }
});
