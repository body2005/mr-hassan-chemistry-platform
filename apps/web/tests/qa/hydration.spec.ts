import { expect, test } from './qaTest';
import { cookieApi } from './cookieApi';

for (const initialOutage of [null, 429, 503] as const) {
test(`large real student enrollment catalog bounds hydration and leaves auth usable${initialOutage ? ` after ${initialOutage}` : ''}`, async ({ page, playwright }) => {
  test.setTimeout(120_000);
  if (process.env.QA_REDIS_CONTAINER !== 'chemistryaudit2-redis-1') throw new Error('Hydration seeding requires isolated chemistryaudit2');
  // Three catalog scenarios deliberately reuse a large real152-course
  // account. Wait its real READ window before each case as well as auth.
  // No counters are deleted; a run begins with its full600-read allowance.
  const { execFile } = await import('node:child_process');
  const { promisify } = await import('node:util');
  const probe = await promisify(execFile)(process.env.QA_DOCKER || 'docker', [
    'exec', process.env.QA_REDIS_CONTAINER, 'redis-cli', 'EVAL',
    "local ms=0; for _,k in ipairs(redis.call('KEYS','rate-limit:read:*')) do if redis.call('ZCARD',k)>0 then ms=math.max(ms,redis.call('PTTL',k)) end end; return ms", '0'],
    { encoding: 'utf8', timeout: 15_000 });
  if (!/^\d+$/.test(probe.stdout.trim())) throw new Error('Unexpected read-window response');
  const readWindow = Number(probe.stdout.trim());
  if (readWindow > 61_000) throw new Error('Unexpected production read window');
  if (readWindow) await new Promise(resolve => setTimeout(resolve, readWindow + 100));
  const student = (await cookieApi(playwright.request, 'student03@demo.com', 'qa-student-pass')).context;
  try {
    const snapshot = await student.get('bootstrap');
    expect(snapshot.status()).toBe(200);
    const count = (await snapshot.json()).enrolled_course_ids.length;
    if (count < 20) {
      const teacher = (await cookieApi(playwright.request, 'teacher@demo.com', 'qa-teacher-pass')).context;
      try {
        for (let index = count; index < 20; index++) {
          const created = await teacher.post('courses', { data: { code: `QAH-${crypto.randomUUID().slice(0, 8)}`,
            title: `QA hydration ${index}`, grade_level: 'SECONDARY_1' } });
          expect(created.status()).toBe(201);
          const id = (await created.json()).id;
          expect((await teacher.post(`courses/${id}/publish`)).status()).toBe(200);
          expect((await student.post(`courses/${id}/enroll`)).status()).toBe(201);
        }
      } finally {
        expect((await teacher.post('auth/logout')).status()).toBe(204);
        await teacher.dispose();
      }
    }
  } finally {
    expect((await student.post('auth/logout')).status()).toBe(204);
    await student.dispose();
  }
  const pending = new Set<object>();
  let peak = 0, completed = 0, enrolled = 0, hydrationRequests = 0;
  const failures: number[] = [];
  const isAssessment = (url: string) => /\/api\/v1\/courses\/[^/?]+\/assessments(?:\?|$)/.test(url);
  const isCourseRead = (url: string) => /\/api\/v1\/courses\/[^/?]+(?:\/assessments)?(?:\?|$)/.test(url);
  page.on('request', request => {
    if (request.method() === 'GET' && isCourseRead(request.url())) hydrationRequests++;
    if (isAssessment(request.url())) { pending.add(request); peak = Math.max(peak, pending.size); }
  });
  page.on('requestfinished', request => { if (pending.delete(request)) completed++; });
  page.on('requestfailed', request => { if (pending.delete(request)) failures.push(0); });
  page.on('response', async response => {
    if (isCourseRead(response.url()) && response.status() >= 400) failures.push(response.status());
    if (response.url().endsWith('/bootstrap') && response.status() === 200) {
      const bootstrap = await response.json();
      if (bootstrap.authenticated) enrolled = bootstrap.enrolled_course_ids?.length || 0;
    }
  });
  // Real API/storage/DB responses, not fabricated assessments. A bounded
  // transport delay makes simultaneous requests observable on fast machines.
  let injectOutage = initialOutage !== null;
  await page.route('**/api/v1/courses/**', async route => {
    if (route.request().method() !== 'GET' || !isCourseRead(route.request().url())) return route.continue();
    const failThisRequest = injectOutage;
    injectOutage = false;
    await new Promise(resolve => setTimeout(resolve, 150));
    if (failThisRequest) return route.fulfill({ status: initialOutage!, headers: { 'Retry-After': '2' },
      json: { detail: 'Synthetic transient course-hydration outage' } });
    await route.continue();
  });
  await page.goto('/#auth');
  const form = page.locator('form').first();
  await form.locator('input[type="text"]').fill('student03@demo.com');
  await form.locator('input[type="password"]').fill('qa-student-pass');
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('.profile-button')).toHaveCount(1);
  // Seeded above when necessary; existing large QA catalogs stay intact.
  await expect.poll(() => enrolled, { timeout: 15_000 }).toBeGreaterThanOrEqual(20);
  if (initialOutage) {
    await expect(page.getByRole('alert')).toContainText('تعذر تحميل بعض بيانات المقررات');
    await expect.poll(() => pending.size).toBe(0);
    expect(hydrationRequests).toBeLessThanOrEqual(4);
    const initialRequests = hydrationRequests;
    await page.waitForTimeout(2500); // Beyond Retry-After: no automatic replay.
    expect(hydrationRequests).toBe(initialRequests);
    expect((await page.request.get('/api/v1/auth/me')).status()).toBe(200);
    await page.getByRole('button', { name: 'إعادة تحميل المقررات' }).click();
  }
  await expect.poll(() => completed, { timeout: 30_000 }).toBeGreaterThanOrEqual(10);
  expect(peak).toBeLessThanOrEqual(4);
  await expect.poll(() => pending.size, { timeout: 60_000 }).toBe(0);
  expect(failures).toEqual(initialOutage ? [initialOutage] : []);
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect((await page.request.get('/api/v1/auth/me')).status()).toBe(200);
  console.log(JSON.stringify({ case: 'real-catalog-hydration', initialOutage, enrolled, peak, completed, failures, hydrationRequests }));
});
}
