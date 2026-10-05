import type { Page } from "@playwright/test";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { expect, test } from "./qaTest";

const base = process.env.QA_BASE_URL || "https://localhost:18543";
async function login(page: Page) {
  const project = process.env.QA_REDIS_CONTAINER?.replace(/-redis-1$/, "");
  if (!project || !["chemistryaudit2", "chemistryprodlocal"].includes(project)) throw new Error("Publication tests require the isolated Docker project");
  const output = execFileSync(process.env.QA_DOCKER || "docker", ["exec", "-e", "QA_ISOLATED=true", "-e", `QA_PROJECT=${project}`,
    `${project}-api-1`, "sh", "/srv/entrypoint-prod.sh", "python", "-m", "scripts.seed_qa_teacher"], { encoding: "utf8", timeout: 20_000 });
  const identity = JSON.parse(output.trim());
  await page.goto(`${base}/#auth`);
  const form = page.locator("form").first();
  await form.locator('input[type="text"]').fill(identity.email);
  await form.locator('input[type="password"]').fill(identity.password);
  await form.locator('button[type="submit"]').click();
  await expect(page.locator(".profile-button")).toHaveCount(1);
}
async function post(page: Page, path: string, data: unknown, status = 201) {
  const csrf = (await page.context().cookies()).find(c => c.name === "matgar_csrf")?.value || "";
  const response = await page.request.post(`${base}/api/v1/${path}`, { data, headers: { "X-CSRF-Token": csrf } });
  expect(response.status(), await response.text()).toBe(status);
  return response.json();
}

for (const scenario of [
  { kind: "quiz", label: "quiz" },
  { kind: "quiz", label: "quiz with delayed bootstrap", slowBootstrap: true },
  { kind: "assignment", label: "assignment" },
  { kind: "quiz", label: "quiz with Arabic afternoon time", arabicTime: true },
  { kind: "assignment", label: "assignment with Arabic afternoon time", arabicTime: true },
  { kind: "quiz", label: "quiz with invalid time", invalidTime: true },
  { kind: "assignment", label: "assignment with invalid time", invalidTime: true },
  { kind: "quiz", label: "quiz with a stale linked lesson", staleLesson: true },
  { kind: "assignment", label: "assignment with a stale linked lesson", staleLesson: true },
  { kind: "quiz", label: "quiz with a maximum-length title", longTitle: true },
  { kind: "assignment", label: "assignment while notifications are unavailable", notificationFailure: true },
] as const) {
  const { kind } = scenario;
  test(`teacher publishes a restored ${scenario.label} through UI`, async ({ page }) => {
    test.setTimeout(90_000);
    await login(page);
    const stamp = Date.now();
    const title = "longTitle" in scenario ? `QA ${stamp} `.padEnd(200, "ع") : `QA Publish ${kind} ${stamp}`;
    const course = await post(page, "courses", { code: `QAPUB${stamp}`, title });
    const module = await post(page, `courses/${course.id}/modules`, { title: "Publication Unit", position: 1 });
    const lesson = await post(page, `modules/${module.id}/lessons`, { title: "Publication Lesson", kind: "article", position: 1 });
    await post(page, `courses/${course.id}/publish`, {}, 200);
    const me = await (await page.request.get(`${base}/api/v1/auth/me`)).json();
    const today = new Date().toISOString().slice(0, 10);
    const tomorrow = new Date(Date.now() + 86400_000).toISOString().slice(0, 10);
    await page.evaluate(({ id, draft }) => localStorage.setItem(`lms_quiz_maker_unuploaded_draft_v2:${id}`, JSON.stringify(draft)), {
      id: me.id, draft: { title, assessmentType: kind, selectedAcademicYear: "1st_secondary", selectedLessonIds: ['staleLesson' in scenario ? crypto.randomUUID() : lesson.id],
        quizDurationMinutes: 45, publishStartDate: today, publishStartTime: "arabicTime" in scenario ? "3:00م" : "00:00", closeDeadlineDate: tomorrow,
        closeDeadlineTime: "invalidTime" in scenario ? "وقت غير صالح" : "arabicTime" in scenario ? "6:00م" : "23:59", showOnStudentCalendar: true, sendScheduledNotification: true,
        questions: [{ id: "manual-1", question_text: "Explain conservation of mass.", question_type: "essay", points: 5 }] },
    });
    const broadcasts: number[] = [];
    const calendars: number[] = [];
    const assessmentWrites: string[] = [];
    page.on('request', request => {
      if (request.method() === 'POST' && /\/api\/v1\/(questions|quizzes(?:\/publish-draft)?|assignments)$/.test(new URL(request.url()).pathname)) assessmentWrites.push(new URL(request.url()).pathname);
    });
    page.on("response", response => {
      if (new URL(response.url()).pathname.endsWith("/notifications/broadcast")) broadcasts.push(response.status());
      if (response.request().method() === "POST" && new URL(response.url()).pathname.endsWith("/calendar")) calendars.push(response.status());
    });
    const notificationFailure = "notificationFailure" in scenario;
    if (notificationFailure) {
      await page.route("**/api/v1/notifications/broadcast", route => route.fulfill({
        status: 503, contentType: "application/json", body: JSON.stringify({ detail: "QA notification outage" }),
      }));
    }
    await page.goto(`${base}/#quizgen`);
    if ('slowBootstrap' in scenario) {
      await page.route('**/api/v1/bootstrap', async route => {
        const response = await route.fetch();
        await new Promise(resolve => setTimeout(resolve, 1500));
        await route.fulfill({ response });
      });
    }
    await page.reload();
    if ('slowBootstrap' in scenario) {
      await expect(page.getByRole('status')).toContainText('جارٍ تحميل المقررات');
      await expect(page.getByRole('button', { name: 'تأكيد الرفع والنشر الآن' })).toHaveCount(0);
    }
    await page.getByRole("button", { name: `حفظ ونشر ${kind === "quiz" ? "الاختبار" : "الواجب"} للطلاب`, exact: true }).first().click();
    await page.getByRole("button", { name: "تأكيد الرفع والنشر الآن" }).click();
    if ('invalidTime' in scenario) {
      await expect(page.getByText('وقت التسليم غير صالح.', { exact: false })).toBeVisible();
      expect(assessmentWrites).toEqual([]);
      expect(broadcasts).toEqual([]);
      expect(calendars).toEqual([]);
      return;
    }
    if ('staleLesson' in scenario) {
      await expect(page.getByText('الدرس المرتبط بالمسودة لم يعد موجودًا', { exact: false })).toBeVisible();
      expect(assessmentWrites).toEqual([]);
      expect(broadcasts).toEqual([]);
      expect(calendars).toEqual([]);
      return;
    }
    await expect.poll(() => broadcasts, { timeout: 25_000 }).toEqual([notificationFailure ? 503 : 201]);
    await expect.poll(() => calendars, { timeout: 25_000 }).toEqual([201]);
    const assessments = await (await page.request.get(`${base}/api/v1/courses/${course.id}/assessments`)).json();
    const items = kind === "quiz" ? assessments.quizzes : assessments.assignments;
    // This route returns published assessments only; inspect the matching
    // server record as well instead of assuming a status field exists here.
    const published = items.filter((item: { title: string }) => item.title === title);
    expect(published).toHaveLength(1);
    const records = await (await page.request.get(`${base}/api/v1/${kind === "quiz" ? "quizzes" : "assignments"}?course_id=${course.id}`)).json();
    expect(records.find((item: { id: string }) => item.id === published[0].id).status).toBe("published");
    if ('arabicTime' in scenario) {
      const record = records.find((item: { id: string }) => item.id === published[0].id);
      expect(new Date(kind === 'quiz' ? record.ends_at : record.due_at).getTime()).toBe(new Date(`${tomorrow}T18:00:00`).getTime());
    }
    if (notificationFailure) {
      await expect(page.getByText("تم نشر المحتوى، لكن تعذر إكمال التقويم أو الإشعار. لا تعِد نشره؛ راجع صفحة الإشعارات.").first()).toBeVisible();
    } else {
      const notifications = await (await page.request.get(`${base}/api/v1/notifications`)).json();
      expect(notifications.some((item: { title: string; message: string }) => item.title.length <= 200 && item.message.includes(title))).toBe(true);
    }
  });
}

test('long notification text stays inside its card on desktop and mobile', async ({ page }) => {
  await login(page);
  const title = `QA Layout ${Date.now()} `.padEnd(200, 'ع');
  const message = 'ع'.repeat(3000);
  await post(page, 'notifications/broadcast', { kind: 'system', title, message });
  await page.goto(`${base}/#notifications`);
  const card = page.locator('.notification-card').filter({ hasText: title });
  await expect(card).toHaveCount(1);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => card.evaluate(el => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(1);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
    const text = card.locator('.notification-message');
    await expect(text).toHaveClass(/notification-message-preview/);
    await card.getByRole('button', { name: 'عرض الرسالة كاملة' }).click();
    await expect(text).toHaveText(message);
    await expect(text).not.toHaveClass(/notification-message-preview/);
    await card.getByRole('button', { name: 'عرض أقل' }).click();
    await page.screenshot({ path: test.info().outputPath(`notification-${width}.png`), fullPage: true });
  }
});

test('a video lesson without an uploaded source explains its state instead of waiting forever', async ({ page }) => {
  await login(page);
  const stamp = Date.now();
  const course = await post(page, 'courses', { code: `QANOVID${stamp}`, title: 'QA missing video', grade_level: 'SECONDARY_2' });
  const module = await post(page, `courses/${course.id}/modules`, { title: 'QA Unit', position: 1 });
  await post(page, `modules/${module.id}/lessons`, { title: 'QA no uploaded source', kind: 'video', position: 1 });
  await page.goto(`${base}/#lessonmanagement`);
  await page.reload();
  await page.getByRole('button', { name: 'الصف الثاني الثانوي', exact: true }).click();
  await page.getByRole('button', { name: 'مشاهدة الدرس', exact: true }).click();
  await expect(page.getByText('لا يوجد فيديو جاهز لهذا الدرس بعد.', { exact: false })).toBeVisible();
  await expect(page.getByText('جاري إعداد مشغل الفيديو التفاعلي...', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'طلب إتاحة الدرس من المعلم' })).toHaveCount(0);
});

test("SSE renews an expired cookie even when the cached bearer is still valid", async ({ page }) => {
  test.setTimeout(60_000);
  const initialStream = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/realtime/stream") && response.status() === 200);
  await login(page);
  await initialStream;
  const cookies = await page.context().cookies();
  expect(await page.evaluate(() => document.cookie.includes("matgar_csrf="))).toBe(true);
  const access = cookies.find(c => c.name === "matgar_session");
  expect(access).toBeTruthy();
  await page.context().addCookies([{ ...access!, value: "expired-qa-access-cookie" }]);
  const streams: number[] = [];
  const refreshes: number[] = [];
  page.on("response", response => {
    const path = new URL(response.url()).pathname;
    if (path.endsWith("/realtime/stream")) streams.push(response.status());
    if (path.endsWith("/auth/refresh")) refreshes.push(response.status());
  });
  await page.reload();
  await expect.poll(() => streams.includes(200), { timeout: 25_000 }).toBe(true);
  expect(refreshes).toEqual([200]);
  expect(streams).not.toContain(401);
  await expect(page.locator(".profile-button")).toHaveCount(1);
});

for (const scenario of [{ kind: "video", resume: false }, { kind: "material", resume: false }, { kind: "video", resume: true }] as const) {
  const { kind } = scenario;
  test(`teacher uploads real ${kind}${scenario.resume ? " after network interruption and browser reload" : ""} from UI, preserves grade/price and publishes the course`, async ({ page }) => {
    test.setTimeout(180_000);
    await login(page);
    const stamp = Date.now();
    const course = await post(page, "courses", { code: `QAUP${stamp}`, title: `QA UI upload ${stamp}`, grade_level: "SECONDARY_2" });
    await page.reload();
    await page.getByRole("button", { name: "الصف الثاني الثانوي", exact: true }).click();
    const title = `QA UI ${kind} ${stamp}`;
    await page.getByPlaceholder("مثال: الدرس 5: كمية التحرك وقانون نيوتن الثاني").fill(title);
    await page.getByPlaceholder("50", { exact: true }).fill("50");
    const media = process.env.QA_MEDIA_DIR || path.resolve("../../.qa/audit2/media");
    const form = page.locator("form").first();
    const input = kind === "video" ? form.locator('input[type="file"][accept="video/*"]') : form.locator('input[type="file"][multiple]');
    await input.setInputFiles(path.join(media, kind === "video" ? "video.webm" : "large.pdf"));
    const capabilities = await (await page.request.get(`${base}/api/v1/video-upload-capabilities`)).json();
    const direct = kind === "video" && capabilities.direct_upload;
    const puts: number[] = [];
    let interrupted = false;
    if (scenario.resume) {
      expect(direct, "Resumption requires the direct-upload Docker overlay").toBe(true);
      await page.route("https://localhost:18544/**", route => {
        const number = Number(new URL(route.request().url()).searchParams.get("partNumber"));
        if (number) puts.push(number);
        if (number === 2 && !interrupted) { interrupted = true; return route.abort("internetdisconnected"); }
        return route.continue();
      });
    }
    const uploaded = page.waitForResponse(response => response.request().method() === "POST"
      && (direct ? /\/video-uploads\/[^/]+\/complete$/.test(new URL(response.url()).pathname)
        : new RegExp(`/lessons/[^/]+/${kind === "video" ? "video" : "materials"}$`).test(new URL(response.url()).pathname)), { timeout: 90_000 });
    await page.getByRole("button", { name: "رفع وحفظ الدرس في المنصة", exact: true }).click();
    if (kind === "video") await page.getByRole("button", { name: "نعم، ارفع في الخلفية", exact: true }).click();
    if (scenario.resume) {
      // The real 32 MiB first part must finish before the second part can be
      // interrupted. Five seconds is not a transport SLA on a local machine.
      await expect.poll(() => interrupted, { timeout: 90_000 }).toBe(true);
      // A real reload drops the File object. Re-select it; do not silently
      // restart multipart, or pretend that localStorage contains its bytes.
      await expect.poll(async () => page.evaluate(() => {
        const tasks = JSON.parse(localStorage.getItem("lms_global_upload_tasks_v3") || "[]");
        return tasks[0]?.status;
      })).toBe("error");
      await page.reload();
      // The management view defaults to the first grade after navigation;
      // return to this course, independently of the persisted upload queue.
      await page.getByRole("button", { name: "الصف الثاني الثانوي", exact: true }).click();
      await page.getByRole("button", { name: "الرفع", exact: true }).click();
      await page.getByLabel("اختيار الفيديو للاستئناف").setInputFiles(path.join(media, "video.webm"));
    }
    const response = await uploaded;
    expect(response.status(), await response.text()).toBe(direct ? 202 : kind === "video" ? 200 : 201);
    if (direct) {
      const session = await response.json();
      await expect.poll(async () => (await (await page.request.get(`${base}/api/v1/video-uploads/${session.id}`)).json()).status,
        { timeout: 120_000, intervals: [1000, 2000, 5000] }).toBe("ready");
      if (scenario.resume) expect(puts).toEqual([1, 2, 2]); // Part 1 is NOT retransmitted.
    }
    const content = await (await page.request.get(`${base}/api/v1/courses/${course.id}`)).json();
    const serverCourses = await (await page.request.get(`${base}/api/v1/courses?page=1&page_size=100`)).json();
    expect(serverCourses.items.filter((item: { grade_level: string }) => item.grade_level === "SECONDARY_2"),
      "A transient empty course list must not cause an extra course to be created").toHaveLength(1);
    expect(content.grade_level).toBe("SECONDARY_2");
    const lesson = content.modules.flatMap((m: { lessons: unknown[] }) => m.lessons).find((item: { title: string }) => item.title === title);
    expect(lesson).toBeTruthy();
    expect(lesson.price_egp).toBe(50);
    expect(lesson.kind).toBe(kind === "video" ? "video" : "article");
    if (kind === "video") expect(lesson.has_video).toBe(true);
    else expect(lesson.materials).toHaveLength(1);
    await page.getByRole("button", { name: "نشر المقرر للطلاب", exact: true }).click();
    await expect.poll(async () => (await (await page.request.get(`${base}/api/v1/courses/${course.id}`)).json()).status).toBe("published");
  });
}
