/** Additional reading evidence; does not replace the complete functional suite.
 * Chromium page/pinch scale is checked through visualViewport, NOT simulated
 * with CSS zoom/deviceScaleFactor and NOT claimed as desktop toolbar zoom.
 * All writes are new synthetic content in the allowlisted local QA project.
 */
import type { Locator, Page } from '@playwright/test';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFileSync } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import { expect, test } from './qaTest';

const base = process.env.QA_BASE_URL || 'https://localhost:18543';
const runDocker = promisify(execFile);
const layouts = [{ width: 320, height: 720 }, { width: 640, height: 360 }];

async function theme(page: Page, value: string, guest = false) {
  if (await page.locator('html').getAttribute('data-theme') !== value) {
    await page.getByRole('button', { name: guest ? 'تغيير المظهر' : 'Toggle Theme', exact: true }).click();
  }
  await expect(page.locator('html')).toHaveAttribute('data-theme', value);
}

async function reading(page: Page, name: string, controls: Locator[], study?: Locator) {
  const cdp = await page.context().newCDPSession(page);
  const original = page.viewportSize();
  const evidence: unknown[] = [];
  try {
    for (const viewport of layouts) {
      await cdp.send('Emulation.setPageScaleFactor', { pageScaleFactor: 1 });
      await page.setViewportSize(viewport);
      await page.evaluate(() => document.fonts.ready);
      const normal = await page.evaluate(() => ({
        width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
        scale: visualViewport?.scale, font: getComputedStyle(document.body).fontFamily,
        direction: getComputedStyle(document.body).direction,
        zoomPolicy: document.querySelector('meta[name="viewport"]')?.getAttribute('content'),
      }));
      expect(normal.scrollWidth, `${name}: no page overflow at ${viewport.width}px`).toBeLessThanOrEqual(normal.width + 1);
      expect(normal.font).toContain('Cairo');
      expect(normal.direction).toBe('rtl');
      expect(normal.zoomPolicy).not.toMatch(/user-scalable\s*=\s*no|maximum-scale\s*=\s*1(?:\D|$)/i);
      for (const control of controls) {
        await expect(control).toBeVisible();
        await control.scrollIntoViewIfNeeded();
        const bounds = await control.boundingBox();
        expect(bounds).not.toBeNull();
        expect(bounds!.x, `${name}: control left edge`).toBeGreaterThanOrEqual(-1);
        expect(bounds!.x + bounds!.width, `${name}: control right edge`).toBeLessThanOrEqual(viewport.width + 1);
      }
      if (study) {
        await expect(study).toBeVisible();
        expect(await study.evaluate(node => parseFloat(getComputedStyle(node).fontSize)), `${name}: study text`).toBeGreaterThanOrEqual(16);
      }
      await controls[0].scrollIntoViewIfNeeded();
      await page.screenshot({ path: test.info().outputPath(`${name}-${viewport.width}-100.png`) });
      await cdp.send('Emulation.setPageScaleFactor', { pageScaleFactor: 2 });
      await expect.poll(() => page.evaluate(() => visualViewport?.scale)).toBeCloseTo(2, 2);
      const zoomed = await page.evaluate(() => ({ scale: visualViewport?.scale, visibleWidth: visualViewport?.width, layoutWidth: innerWidth }));
      expect(zoomed.visibleWidth!).toBeCloseTo(viewport.width / 2, 0);
      // Playwright's desktop click-coordinate scrolling does not reliably pan
      // a Chromium pinch viewport. Scroll the real page, then check its actual
      // DOM hit target in the visible viewport; do not change CSS or submit.
      await controls[0].evaluate(node => {
        node.scrollIntoView({ block: 'start', inline: 'start' });
        const rect = node.getBoundingClientRect();
        const viewport = window.visualViewport!;
        // A start-aligned target can be behind the real sticky header. Pan
        // the document into the visual viewport's centre, as a user can;
        // do not disable the header or modify application styles.
        const delta = rect.top - viewport.offsetTop - (viewport.height - Math.min(rect.height, viewport.height)) / 2;
        // Homework is a fixed, independently scrollable page. Scrolling the
        // underlying window cannot move its target away from its own header.
        let scroller = node.parentElement;
        while (scroller && !(scroller.scrollHeight > scroller.clientHeight && /auto|scroll/.test(getComputedStyle(scroller).overflowY))) {
          scroller = scroller.parentElement;
        }
        if (scroller) scroller.scrollBy(0, delta);
        else window.scrollBy(0, delta);
      });
      const primaryHitTestAt200 = await controls[0].evaluate(node => {
        const rect = node.getBoundingClientRect();
        const viewport = window.visualViewport!;
        const left = Math.max(rect.left, viewport.offsetLeft);
        const right = Math.min(rect.right, viewport.offsetLeft + viewport.width);
        const top = Math.max(rect.top, viewport.offsetTop);
        const bottom = Math.min(rect.bottom, viewport.offsetTop + viewport.height);
        const hit = right > left && bottom > top ? document.elementFromPoint((left + right) / 2, (top + bottom) / 2) : null;
        return {
          reachable: !!hit && (node.contains(hit) || hit.contains(node)),
          rect: { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom },
          viewport: { left: viewport.offsetLeft, top: viewport.offsetTop, width: viewport.width, height: viewport.height },
          hitTag: hit?.tagName || null,
        };
      });
      await page.screenshot({ path: test.info().outputPath(`${name}-${viewport.width}-200.png`) });
      evidence.push({ viewport, normal, zoomed, primaryHitTestAt200 });
      expect(primaryHitTestAt200.reachable, `${name}: primary control hit target at actual200%: ${JSON.stringify(primaryHitTestAt200)}`).toBe(true);
    }
  } finally {
    await cdp.send('Emulation.setPageScaleFactor', { pageScaleFactor: 1 });
    await cdp.detach();
    if (original) await page.setViewportSize(original);
    // No tokens, identities, server URLs or storage state in this attachment.
    await test.info().attach(`${name}-reading-metrics`, { body: JSON.stringify(evidence), contentType: 'application/json' });
  }
}

async function post(page: Page, path: string, data: unknown = {}, status = 201) {
  const csrf = (await page.context().cookies()).find(c => c.name === 'matgar_csrf')?.value || '';
  const response = await page.request.post(`${base}/api/v1/${path}`, { data, headers: { 'X-CSRF-Token': csrf } });
  expect(response.status(), `QA API ${path.split('/')[0]} status`).toBe(status);
  return response.status() === 204 ? null : response.json();
}

async function teacher(page: Page) {
  if (process.env.QA_PROJECT !== 'chemistryaudit2') throw new Error('Reading matrix requires isolated chemistryaudit2');
  const { stdout } = await runDocker(process.env.QA_DOCKER || 'docker', ['exec', '-e', 'QA_ISOLATED=true', '-e', 'QA_PROJECT=chemistryaudit2',
    'chemistryaudit2-api-1', 'sh', '/srv/entrypoint-prod.sh', 'python', '-m', 'scripts.seed_qa_teacher'], { encoding: 'utf8', timeout: 20_000 });
  const identity = JSON.parse(stdout.trim());
  await page.goto(`${base}/#auth`);
  const form = page.locator('form').first();
  await form.locator('input[type="text"]').fill(identity.email);
  await form.locator('input[type="password"]').fill(identity.password);
  const loggedIn = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/v1/auth/login');
  await form.locator('button[type="submit"]').click();
  expect((await loggedIn).status()).toBe(200);
  await expect(page.locator('.profile-button')).toHaveCount(1);
}

async function courseWithLesson(page: Page, kind = 'article') {
  const course = await post(page, 'courses', { code: `QAR-${randomUUID().slice(0, 8)}`, title: 'مقرر اختبار القراءة في الكيمياء', grade_level: 'SECONDARY_1' });
  const module = await post(page, `courses/${course.id}/modules`, { title: 'وحدة حفظ الكتلة', position: 1 });
  const lesson = await post(page, `modules/${module.id}/lessons`, { title: 'درس اختبار القراءة', kind, position: 1, price_egp: 0 });
  return { course, lesson };
}

for (const mode of ['light', 'dark']) {
  test(`guest registration and reset reading in ${mode}, small phone/landscape and actual200%`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto(`${base}/#auth?tab=register`);
    await theme(page, mode, true);
    await expect(page.locator('.registration-steps li')).toHaveCount(2);
    await reading(page, 'registration-personal', [page.getByLabel('الاسم الأول'), page.getByRole('button', { name: 'التالي', exact: true })]);
    await page.getByLabel('الاسم الأول').fill('أحمد');
    await page.getByLabel('الاسم الأوسط').fill('محمد');
    await page.getByLabel('الاسم الأخير').fill('حسن');
    await page.getByRole('radio', { name: 'ذكر', exact: true }).check();
    await page.getByLabel('السنة الدراسية').selectOption('1st_secondary');
    await page.getByRole('button', { name: 'التالي', exact: true }).click();
    await reading(page, 'registration-contact', [page.getByLabel('رقم تليفونك الشخصي'), page.getByRole('button', { name: 'إنشاء حسابي', exact: true })]);
    await page.goto(`${base}/#auth?tab=signin`);
    await page.getByRole('button', { name: 'نسيت كلمة المرور؟', exact: true }).click();
    await reading(page, 'reset-request', [page.getByLabel('بريد الاسترجاع'), page.getByRole('button', { name: 'إرسال رابط الاسترجاع', exact: true })]);
  });

  test(`teacher editor reading in ${mode}, small phone/landscape and actual200%`, async ({ page }) => {
    test.setTimeout(150_000);
    await teacher(page);
    const { lesson } = await courseWithLesson(page);
    await theme(page, mode);
    const me = await (await page.request.get(`${base}/api/v1/auth/me`)).json();
    await page.evaluate(({ id, draft }) => localStorage.setItem(`lms_quiz_maker_unuploaded_draft_v2:${id}`, JSON.stringify(draft)), {
      id: me.id, draft: { title: 'اختبار القراءة وحفظ الكتلة', assessmentType: 'quiz', selectedAcademicYear: '1st_secondary', selectedLessonIds: [lesson.id],
        quizDurationMinutes: 45, publishStartDate: new Date().toISOString().slice(0, 10), publishStartTime: '00:00',
        closeDeadlineDate: new Date(Date.now() + 86400_000).toISOString().slice(0, 10), closeDeadlineTime: '23:59',
        showOnStudentCalendar: false, sendScheduledNotification: false,
        questions: [{ id: 'reading-q1', question_text: 'اشرح قانون حفظ الكتلة مع ذكر وحدات القياس.', question_type: 'essay', points: 5 }] },
    });
    await page.setViewportSize(layouts[0]);
    await page.goto(`${base}/#quizgen`);
    await page.reload();
    const next = page.getByRole('button', { name: 'التالي: مراجعة الأسئلة', exact: true });
    await reading(page, 'editor-setup', [next]);
    await next.click();
    const publishStage = page.getByRole('button', { name: 'التالي: تحديد الموعد والنشر', exact: true });
    await reading(page, 'editor-review', [publishStage]);
    await publishStage.click();
    await reading(page, 'editor-publication', [page.getByRole('button', { name: 'حفظ ونشر الاختبار للطلاب', exact: true }).first()]);
  });

  test(`student study/video/quiz/homework reading in ${mode}, small phone/landscape and actual200%`, async ({ page, browser, playwright }) => {
    test.setTimeout(240_000);
    await teacher(page);
    const { course, lesson } = await courseWithLesson(page, 'video');
    const media = readFileSync(process.env.QA_VIDEO_FILE || '/qa-media/video.webm');
    const upload = await post(page, `lessons/${lesson.id}/video-uploads`, {
      filename: 'reading.webm', content_type: 'video/webm', size_bytes: media.length,
      fingerprint: createHash('sha256').update(media).digest('hex'), request_key: randomUUID(),
    });
    const uploader = await playwright.request.newContext({ ignoreHTTPSErrors: false });
    try {
      for (let number = 1; number <= Math.ceil(media.length / upload.part_bytes); number++) {
        const signed = await post(page, `video-uploads/${upload.id}/parts/${number}`, {}, 200);
        expect((await uploader.put(signed.url, { data: media.subarray((number - 1) * upload.part_bytes, (number - 1) * upload.part_bytes + signed.size_bytes) })).status()).toBe(200);
      }
    } finally { await uploader.dispose(); }
    await post(page, `video-uploads/${upload.id}/complete`, {}, 202);
    await expect.poll(async () => (await (await page.request.get(`${base}/api/v1/video-uploads/${upload.id}`)).json()).status,
      { timeout: 120_000, intervals: [1000, 3000] }).toBe('ready');
    const question = await post(page, 'questions', { course_id: course.id, question_type: 'essay', prompt: 'اشرح قانون حفظ الكتلة مع ذكر وحدات القياس.', points: 5 });
    const quiz = await post(page, 'quizzes', { course_id: course.id, lesson_id: lesson.id, title: 'اختبار حفظ الكتلة', question_ids: [question.id] });
    const homework = await post(page, 'assignments', { course_id: course.id, lesson_id: lesson.id, title: 'واجب حفظ الكتلة', prompt: 'ارفع الحل موضحًا خطوات الحساب ووحدات القياس.', max_score: 5 });
    await post(page, `courses/${course.id}/publish`, {}, 200);
    await post(page, `quizzes/${quiz.id}/publish`, {}, 200);
    await post(page, `assignments/${homework.id}/publish`, {}, 200);
    const context = await browser.newContext({ baseURL: base, ignoreHTTPSErrors: false, viewport: layouts[0], hasTouch: true });
    const student = await context.newPage();
    const telemetryStatuses: number[] = [];
    student.on('response', response => {
      if (new URL(response.url()).pathname === '/api/v1/telemetry/video-events') telemetryStatuses.push(response.status());
    });
    try {
      await post(student, 'auth/register', { display_name: 'طالب اختبار القراءة', email: `qa-reading-${randomUUID()}@example.com`, password: 'Qa-reading-2026!',
        grade_level: 'SECONDARY_1', governorate: 'CAIRO', school_name: 'مدرسة اختبار محلية', gender: 'MALE' });
      await post(student, `courses/${course.id}/enroll`, {}, 200);
      await student.goto(`${base}/#mycourses`);
      await expect(student.locator('.profile-button')).toHaveCount(1);
      await theme(student, mode);
      await reading(student, 'student-course', [student.getByRole('button', { name: 'مشاهدة الدرس', exact: true })]);
      await student.getByRole('button', { name: 'مشاهدة الدرس', exact: true }).tap();
      const play = student.getByRole('button', { name: 'تشغيل', exact: true });
      await expect(play).toBeVisible({ timeout: 30_000 });
      await play.tap();
      await expect.poll(() => student.locator('video:not(#qa-video)').evaluate((node: HTMLVideoElement) => node.currentTime), { timeout: 30_000 }).toBeGreaterThan(0);
      await student.getByRole('button', { name: 'إيقاف مؤقت', exact: true }).tap();
      const settings = student.getByRole('button', { name: 'الإعدادات والجودة', exact: true });
      await reading(student, 'student-video', [settings, play]);
      expect((await settings.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      await student.getByRole('navigation', { name: 'Breadcrumb' }).getByRole('button', { name: course.title, exact: true }).click();
      await expect.poll(() => telemetryStatuses.length).toBeGreaterThan(0);
      expect(telemetryStatuses, 'Actual batched browser video response statuses').toEqual(telemetryStatuses.map(() => 202));
      await student.getByRole('button', { name: 'الاختبارات والكويزات', exact: true }).click();
      await student.getByRole('button', { name: 'بدء حل الاختبار', exact: true }).click();
      const answer = student.getByPlaceholder('اكتب إجابتك هنا…');
      await reading(student, 'student-quiz', [answer, student.getByRole('button', { name: 'تسليم الاختبار', exact: true }).last()], answer);
      await answer.fill('الكتلة محفوظة عند تساوي مجموع كتل المتفاعلات والنواتج.');
      await student.getByRole('button', { name: 'تسليم الاختبار', exact: true }).last().click();
      await student.getByRole('button', { name: 'نعم، تأكيد وتسليم الآن', exact: true }).click();
      await expect(student.getByText('تم تسليم الاختبار، والنتيجة في انتظار اعتماد المدرس')).toBeVisible();
      await student.getByRole('button', { name: 'العودة إلى المقرر', exact: true }).click();
      await student.getByRole('button', { name: 'الواجبات والتكليفات', exact: true }).click();
      await student.getByRole('button', { name: 'فتح الواجب وتسليم الحل', exact: true }).click();
      await reading(student, 'student-homework', [student.getByRole('button', { name: 'تحميل PDF', exact: true }), student.getByRole('button', { name: 'إرسال الحل للمعلم', exact: true })]);
    } finally {
      await post(student, 'auth/logout', {}, 204);
      await context.close();
    }
  });
}
