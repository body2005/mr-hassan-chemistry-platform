import { expect, test } from './qaTest';
import { cookieApi } from './cookieApi';

test('large real student enrollment catalog bounds hydration and leaves auth usable', async ({ page, playwright }) => {
  test.setTimeout(120_000);
  if (process.env.QA_REDIS_CONTAINER !== 'chemistryaudit2-redis-1') throw new Error('Hydration seeding requires isolated chemistryaudit2');
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
  let peak = 0, completed = 0, enrolled = 0;
  const failures: number[] = [];
  const isAssessment = (url: string) => /\/api\/v1\/courses\/[^/?]+\/assessments(?:\?|$)/.test(url);
  page.on('request', request => {
    if (isAssessment(request.url())) { pending.add(request); peak = Math.max(peak, pending.size); }
  });
  page.on('requestfinished', request => { if (pending.delete(request)) completed++; });
  page.on('requestfailed', request => { if (pending.delete(request)) failures.push(0); });
  page.on('response', async response => {
    if (isAssessment(response.url()) && response.status() >= 400) failures.push(response.status());
    if (response.url().endsWith('/bootstrap') && response.status() === 200) {
      const bootstrap = await response.json();
      if (bootstrap.authenticated) enrolled = bootstrap.enrolled_course_ids?.length || 0;
    }
  });
  // Real API/storage/DB responses, not fabricated assessments. A bounded
  // transport delay makes simultaneous requests observable on fast machines.
  await page.route('**/api/v1/courses/*/assessments', async route => {
    await new Promise(resolve => setTimeout(resolve, 150));
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
  await expect.poll(() => completed, { timeout: 30_000 }).toBeGreaterThanOrEqual(10);
  expect(peak).toBeLessThanOrEqual(4);
  await expect.poll(() => pending.size, { timeout: 60_000 }).toBe(0);
  expect(failures).toEqual([]);
  expect((await page.request.get('/api/v1/auth/me')).status()).toBe(200);
  console.log(JSON.stringify({ case: 'real-catalog-hydration', enrolled, peak, completed, failures }));
});
