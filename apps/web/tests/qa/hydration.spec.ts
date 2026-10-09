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
  // Reproducible on a clean checkout too: no dependence on old test debris.
  const seeded = await promisify(execFile)(process.env.QA_DOCKER || 'docker', [
    'exec', '-e', 'QA_ISOLATED=true', '-e', 'QA_PROJECT=chemistryaudit2', 'chemistryaudit2-api-1',
    'sh', '/srv/entrypoint-prod.sh', 'python', '-m', 'scripts.seed_qa_enrollments'],
    { encoding: 'utf8', timeout: 30_000 });
  expect(JSON.parse(seeded.stdout.trim()).published_active_enrollments).toBeGreaterThanOrEqual(152);
  const student = (await cookieApi(playwright.request, 'student03@demo.com', 'qa-student-pass')).context;
  try {
    const snapshot = await student.get('bootstrap');
    expect(snapshot.status()).toBe(200);
    const count = (await snapshot.json()).enrolled_course_ids.length;
    expect(count).toBeGreaterThanOrEqual(152);
  } finally {
    expect((await student.post('auth/logout')).status()).toBe(204);
    await student.dispose();
  }
  const pending = new Set<object>();
  let peak = 0, completed = 0, enrolled = 0, hydrationRequests = 0;
  const assessmentIds = new Set<string>();
  const failures: number[] = [];
  const isAssessment = (url: string) => /\/api\/v1\/courses\/[^/?]+\/assessments(?:\?|$)/.test(url);
  const isCourseRead = (url: string) => /\/api\/v1\/courses(?:\/[^/?]+(?:\/assessments)?)?(?:\?|$)/.test(url);
  page.on('request', request => {
    if (request.method() === 'GET' && isCourseRead(request.url())) hydrationRequests++;
    if (isAssessment(request.url())) {
      assessmentIds.add(new URL(request.url()).pathname.split('/')[4]);
      pending.add(request); peak = Math.max(peak, pending.size);
    }
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
    if (route.request().method() !== 'GET' || !isAssessment(route.request().url())) return route.continue();
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
  await expect.poll(() => enrolled, { timeout: 15_000 }).toBeGreaterThanOrEqual(152);
  await page.getByRole('button', { name: 'الاختبارات والكويزات', exact: true }).click();
  if (initialOutage) {
    await expect(page.getByRole('alert')).toContainText('تعذر تحميل تقييمات هذا المقرر');
    await expect.poll(() => pending.size).toBe(0);
    expect(assessmentIds.size).toBe(1);
    const initialRequests = hydrationRequests;
    await page.waitForTimeout(2500); // Beyond Retry-After: no automatic replay.
    expect(hydrationRequests).toBe(initialRequests);
    expect((await page.request.get('/api/v1/auth/me')).status()).toBe(200);
    await page.getByRole('button', { name: 'إعادة تحميل التقييمات' }).click();
  }
  // The selected course must finish promptly, WITHOUT152 assessment reads.
  await expect.poll(() => completed, { timeout: 5_000 }).toBeGreaterThanOrEqual(1);
  expect(peak).toBeLessThanOrEqual(1);
  await expect.poll(() => pending.size, { timeout: 60_000 }).toBe(0);
  expect(failures).toEqual(initialOutage ? [initialOutage] : []);
  expect(assessmentIds.size).toBe(1);
  expect(hydrationRequests).toBeLessThanOrEqual(Math.ceil(enrolled / 100) + 2);
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect((await page.request.get('/api/v1/auth/me')).status()).toBe(200);
  console.log(JSON.stringify({ case: 'real-catalog-hydration', initialOutage, enrolled, peak, completed, failures, hydrationRequests }));
});
}
