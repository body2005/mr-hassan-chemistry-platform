import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "./qaTest";

const baseURL = `${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/api/v1/`;

test("protected WebM supports browser playback, seeking and byte ranges", async ({ page, playwright }) => {
  const api = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true", baseURL });
  const teacherLogin = await api.post("auth/login", {
    data: { email: "teacher@demo.com", password: "qa-teacher-pass", institution_slug: "demo" },
  });
  expect(teacherLogin.status()).toBe(200);
  const teacherToken = (await teacherLogin.json()).token as string;
  const teacher = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true",
    baseURL,
    extraHTTPHeaders: { Authorization: `Bearer ${teacherToken}` },
  });
  const student = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true", baseURL });
  try {
    const code = `QAV${Date.now()}`;
    const courseResponse = await teacher.post("courses", { data: { code, title: "QA Video Course" } });
    expect(courseResponse.status()).toBe(201);
    const course = await courseResponse.json();
    const moduleResponse = await teacher.post(`courses/${course.id}/modules`, { data: { title: "QA Video Unit", position: 1 } });
    expect(moduleResponse.status()).toBe(201);
    const module = await moduleResponse.json();
    const unsafeExternal = await teacher.post(`modules/${module.id}/lessons`, {
      data: { title: "Unprotected cloud video", kind: "video", position: 2, external_video_url: "https://example.com/video.mp4" },
    });
    expect(unsafeExternal.status()).toBe(422);
    const lessonResponse = await teacher.post(`modules/${module.id}/lessons`, {
      data: { title: "QA Protected Video", kind: "video", position: 1, price_egp: 0 },
    });
    expect(lessonResponse.status()).toBe(201);
    const lesson = await lessonResponse.json();
    const media = readFileSync(resolve(process.cwd(), (process.env.QA_VIDEO_FILE || "../../.qa/production/media/video.webm")));
    const upload = await teacher.post(`lessons/${lesson.id}/video`, {
      multipart: { file: { name: "qa-video.webm", mimeType: "video/webm", buffer: media } },
    });
    expect(upload.status(), await upload.text()).toBe(200);
    expect((await teacher.post(`courses/${course.id}/publish`)).status()).toBe(200);
    const login = await student.post("auth/login", {
      data: { email: "student03@demo.com", password: "qa-student-pass", institution_slug: "demo" },
    });
    expect(login.status()).toBe(200);
    const csrf = (await student.storageState()).cookies.find((cookie) => cookie.name === "matgar_csrf")?.value;
    expect(csrf).toBeTruthy();
    expect((await student.post(`courses/${course.id}/enroll`, {
      headers: { "X-CSRF-Token": csrf! },
    })).status()).toBe(200);
    const unauthorized = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true", baseURL });
    expect((await unauthorized.get(`lessons/${lesson.id}/stream`)).status()).toBe(403);
    expect((await unauthorized.post(`lessons/${lesson.id}/video-token`)).status()).toBe(401);
    await unauthorized.dispose();

    const tokenResponse = await student.post(`lessons/${lesson.id}/video-token`, {
      headers: { "X-CSRF-Token": csrf! },
    });
    expect(tokenResponse.status(), await tokenResponse.text()).toBe(200);
    expect(tokenResponse.headers()["cache-control"]).toContain("no-store");
    const token = await tokenResponse.json();
    const studentBearer = (await login.json()).token as string;
    const copiedLink = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true",
      baseURL,
      extraHTTPHeaders: {
        Authorization: `Bearer ${studentBearer}`,
        Origin: (process.env.QA_BASE_URL || "http://127.0.0.1:18080"),
        Referer: `${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/`,
      },
    });
    try {
      expect((await copiedLink.get(token.stream_url, { headers: { Range: "bytes=0-99" } })).status()).toBe(403);
    } finally {
      await copiedLink.dispose();
    }
    const ranged = await student.get(token.stream_url, { headers: { Range: "bytes=0-99" } });
    expect(ranged.status()).toBe(206);
    expect(ranged.headers()["cross-origin-resource-policy"]).toBe("same-origin");
    expect(ranged.headers()["referrer-policy"]).toBe("no-referrer");
    expect(ranged.headers()["content-range"]).toMatch(/^bytes 0-99\/\d+$/);
    expect((await ranged.body()).length).toBe(100);

    await page.goto("/#auth");
    const form = page.locator("form").first();
    await form.locator('input[type="text"]').fill("student03@demo.com");
    await form.locator('input[type="password"]').fill("qa-student-pass");
    await form.locator('button[type="submit"]').click();
    await expect(page.locator(".profile-button")).toHaveCount(1);
    await page.getByLabel("اختر المقرر").selectOption(course.id);
    await page.getByRole("button", { name: "مشاهدة الدرس" }).first().click();
    const lessonPlayer = page.locator("video").first();
    await expect(lessonPlayer).toBeVisible();
    await expect.poll(() => lessonPlayer.evaluate((video: HTMLVideoElement) => video.readyState)).toBeGreaterThanOrEqual(2);
    const renewed = page.waitForResponse((response) => response.url().endsWith(`/lessons/${lesson.id}/video-token`) && response.status() === 200);
    await lessonPlayer.evaluate((video: HTMLVideoElement) => {
      video.src = "/api/v1/lessons/not-a-valid-id/stream?token=expired";
      video.load();
    });
    await renewed;
    await expect.poll(() => lessonPlayer.evaluate((video: HTMLVideoElement) => video.currentSrc)).not.toContain("token=expired");
    await page.evaluate(async (lessonId) => {
      const csrfToken = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("matgar_csrf="))?.split("=")[1];
      const response = await fetch(`/api/v1/lessons/${lessonId}/video-token`, {
        method: "POST", credentials: "include", headers: { "X-CSRF-Token": csrfToken || "" },
      });
      if (!response.ok) throw new Error(`Video token ${response.status}`);
      const { stream_url } = await response.json();
      const video = document.createElement("video");
      video.id = "qa-video";
      video.muted = true;
      video.src = stream_url;
      document.body.appendChild(video);
      await video.play();
    }, lesson.id);
    await expect.poll(() => page.locator("#qa-video").evaluate((video: HTMLVideoElement) => video.readyState)).toBeGreaterThanOrEqual(2);
    await page.locator("#qa-video").evaluate((video: HTMLVideoElement) => { video.currentTime = 3; });
    await expect.poll(() => page.locator("#qa-video").evaluate((video: HTMLVideoElement) => video.currentTime)).toBeGreaterThanOrEqual(2.9);

    // Logout must kill the old URL, but a fresh login must be able to watch.
    expect((await student.post("auth/logout", { headers: { "X-CSRF-Token": csrf! } })).status()).toBe(204);
    const loginAgain = await student.post("auth/login", {
      data: { email: "student03@demo.com", password: "qa-student-pass", institution_slug: "demo" },
    });
    expect(loginAgain.status()).toBe(200);
    const newCsrf = (await student.storageState()).cookies.find((cookie) => cookie.name === "matgar_csrf")?.value;
    const freshToken = await student.post(`lessons/${lesson.id}/video-token`, {
      headers: { "X-CSRF-Token": newCsrf! },
    });
    expect(freshToken.status(), await freshToken.text()).toBe(200);
    expect((await student.get(token.stream_url)).status()).toBe(403);
    const freshUrl = (await freshToken.json()).stream_url as string;
    expect((await student.get(freshUrl, { headers: { Range: "bytes=0-99" } })).status()).toBe(206);
    for (let repeat = 0; repeat < 3; repeat += 1) {
      const repeated = await student.post(`lessons/${lesson.id}/video-token`, {
        headers: { "X-CSRF-Token": newCsrf! },
      });
      expect(repeated.status(), await repeated.text()).toBe(200);
    }
    expect((await student.post("auth/revoke-all", { headers: { "X-CSRF-Token": newCsrf! } })).status()).toBe(204);
    expect((await student.get(freshUrl, { headers: { Range: "bytes=0-99" } })).status()).toBe(403);
  } finally {
    await Promise.all([api.dispose(), teacher.dispose(), student.dispose()]);
  }
});
