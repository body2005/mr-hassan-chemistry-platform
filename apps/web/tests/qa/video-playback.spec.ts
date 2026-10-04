import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { expect, test } from "./qaTest";

const baseURL = `${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/api/v1/`;

test("protected WebM supports browser playback, seeking and byte ranges", async ({ page, playwright }) => {
  test.setTimeout(180_000);
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
    const capabilities = await (await teacher.get("video-upload-capabilities")).json();
    if (capabilities.direct_upload) {
      const identity = await teacher.post(`lessons/${lesson.id}/video-uploads`, { data: {
        filename: "qa-video.webm", content_type: "video/webm", size_bytes: media.length,
        fingerprint: createHash("sha256").update(media).digest("hex"), request_key: randomUUID(),
      } });
      expect(identity.status(), await identity.text()).toBe(201);
      const upload = await identity.json();
      const uploader = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true" });
      try {
        for (let number = 1; number <= Math.ceil(media.length / upload.part_bytes); number++) {
          const signed = await (await teacher.post(`video-uploads/${upload.id}/parts/${number}`)).json();
          const part = media.subarray((number - 1) * upload.part_bytes, (number - 1) * upload.part_bytes + signed.size_bytes);
          const result = await uploader.put(signed.url, { data: part });
          expect(result.status()).toBe(200);
        }
      } finally { await uploader.dispose(); }
      // Real concurrent completion on PostgreSQL; both retry outcomes must be
      // explicit, and the stored job ID cannot be duplicated.
      const completions = await Promise.all([1, 2].map(() => teacher.post(`video-uploads/${upload.id}/complete`)));
      expect(completions.map(result => result.status()).every(status => status === 202 || status === 409)).toBe(true);
      await expect.poll(async () => (await (await teacher.get(`video-uploads/${upload.id}`)).json()).status,
        { timeout: 120_000, intervals: [1000, 3000] }).toBe("ready");
      expect((await teacher.post(`video-uploads/${upload.id}/complete`)).status()).toBe(202);
      // Real decoder validation, not just an extension/MIME unit test. A bad
      // replacement must fail without superseding the previously ready asset.
      const invalid = Buffer.from("This is not an MP4 video, even with a video filename.");
      const rejected = await teacher.post(`lessons/${lesson.id}/video-uploads`, { data: {
        filename: "fake.mp4", content_type: "video/mp4", size_bytes: invalid.length,
        fingerprint: createHash("sha256").update(invalid).digest("hex"), request_key: randomUUID(),
      } });
      expect(rejected.status()).toBe(201);
      const badUpload = await rejected.json();
      const signer = await teacher.post(`video-uploads/${badUpload.id}/parts/1`);
      expect(signer.status()).toBe(200);
      const direct = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true" });
      try { expect((await direct.put((await signer.json()).url, { data: invalid })).status()).toBe(200); }
      finally { await direct.dispose(); }
      expect((await teacher.post(`video-uploads/${badUpload.id}/complete`)).status()).toBe(202);
      await expect.poll(async () => (await (await teacher.get(`video-uploads/${badUpload.id}`)).json()).status,
        { timeout: 30_000, intervals: [1000, 3000] }).toBe("failed");
      const badState = await (await teacher.get(`video-uploads/${badUpload.id}`)).json();
      expect(badState.error_code).toBe("VIDEO_DECODE_FAILED");
      expect((await (await teacher.get(`video-uploads/${upload.id}`)).json()).status).toBe("ready");
    } else {
      const upload = await teacher.post(`lessons/${lesson.id}/video`, {
        multipart: { file: { name: "qa-video.webm", mimeType: "video/webm", buffer: media } },
      });
      expect(upload.status(), await upload.text()).toBe(200);
    }
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
    let rangeUrl = token.stream_url;
    if (token.format === "hls") {
      const master = await student.get(token.stream_url);
      expect(master.status()).toBe(200);
      expect(master.headers()["content-type"]).toContain("mpegurl");
      const playlistUrl = (await master.text()).split("\n").find(line => line && !line.startsWith("#"))!;
      const playlist = await student.get(playlistUrl);
      expect(playlist.status()).toBe(200);
      rangeUrl = (await playlist.text()).split("\n").find(line => line && !line.startsWith("#"))!;
      const anonymous = await playwright.request.newContext({ ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === "true", baseURL });
      expect((await anonymous.get(rangeUrl)).status()).toBe(403);
      await anonymous.dispose();
    }
    const ranged = await student.get(rangeUrl, { headers: { Range: "bytes=0-99" } });
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
    let deniedSegments = 0;
    const segmentRoute = "**/api/v1/lessons/*/hls/**/*.ts?*";
    if (token.format === "hls") {
      // Interrupt the actual HLS transport, not video.src: Chrome's MSE
      // player does not use the native source URL while hls.js is attached.
      await page.route(segmentRoute, route => {
        deniedSegments += 1;
        return route.fulfill({ status: 403, body: "QA expired playback token" });
      });
    }
    await page.getByRole("button", { name: "مشاهدة الدرس" }).first().click();
    const lessonPlayer = page.locator("video").first();
    await expect(lessonPlayer).toBeVisible();
    const renewed = page.waitForResponse((response) => response.url().endsWith(`/lessons/${lesson.id}/video-token`) && response.status() === 200);
    if (token.format === "hls") {
      await expect(page.getByRole("button", { name: "إعادة المحاولة", exact: true })).toBeVisible();
      expect(deniedSegments).toBeGreaterThan(0);
      expect(deniedSegments).toBeLessThanOrEqual(2); // No unbounded retries.
      await page.unroute(segmentRoute);
      await page.getByRole("button", { name: "إعادة المحاولة", exact: true }).click();
    } else {
      await expect.poll(() => lessonPlayer.evaluate((video: HTMLVideoElement) => video.readyState)).toBeGreaterThanOrEqual(2);
      await lessonPlayer.evaluate((video: HTMLVideoElement) => {
        video.src = "/api/v1/lessons/not-a-valid-id/stream?token=expired";
        video.load();
      });
    }
    await renewed;
    await expect.poll(() => lessonPlayer.evaluate((video: HTMLVideoElement) => video.readyState), { timeout: 30_000 }).toBeGreaterThanOrEqual(2);
    await expect.poll(() => lessonPlayer.evaluate((video: HTMLVideoElement) => video.currentSrc)).not.toContain("token=expired");
    if (token.format === "hls") {
      await lessonPlayer.evaluate(async (video: HTMLVideoElement) => { video.muted = true; await video.play(); });
      await expect.poll(() => lessonPlayer.evaluate((video: HTMLVideoElement) => video.currentTime), { timeout: 20_000 }).toBeGreaterThanOrEqual(4);
      await lessonPlayer.evaluate((video: HTMLVideoElement) => { video.currentTime = 3; });
      await expect.poll(() => lessonPlayer.evaluate((video: HTMLVideoElement) => video.currentTime)).toBeGreaterThanOrEqual(2.9);
    } else {
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
    }

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
    expect((await student.get(freshUrl, { headers: { Range: "bytes=0-99" } })).status()).toBe(token.format === "hls" ? 200 : 206);
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
