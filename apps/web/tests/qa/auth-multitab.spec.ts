import { execFileSync } from 'node:child_process';
import { expect, test } from './qaTest';

for (const fault of [503, 429, 'network'] as const) {
test(`two real tabs recover shared-cookie rotation and retain drafts during ${fault} refresh outage`, async ({ page, context }) => {
  test.setTimeout(90_000);
  const project = process.env.QA_REDIS_CONTAINER?.replace(/-redis-1$/, '');
  if (project !== 'chemistryaudit2') throw new Error('Requires the isolated QA project');
  const identity = JSON.parse(execFileSync(process.env.QA_DOCKER || 'docker', ['exec', '-e', 'QA_ISOLATED=true',
    '-e', `QA_PROJECT=${project}`, `${project}-api-1`, 'sh', '/srv/entrypoint-prod.sh', 'python', '-m',
    'scripts.seed_qa_teacher'], { encoding: 'utf8', timeout: 20_000 }).trim());
  await page.goto('/#auth');
  const form = page.locator('form').first();
  await form.locator('input[type="text"]').fill(identity.email);
  await form.locator('input[type="password"]').fill(identity.password);
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('.profile-button')).toHaveCount(1);
  const other = await context.newPage();
  const reloadAndWaitForIdentity = async () => {
    await Promise.all([page, other].map(async tab => {
      // A cached profile is visible before identity hydration finishes. Wait
      // for the app's own successful bootstrap, not that cached UI alone.
      const hydrated = tab.waitForResponse(response =>
        new URL(response.url()).pathname.endsWith('/bootstrap') && response.status() === 200,
      { timeout: 15_000 });
      await tab.reload();
      await hydrated;
    }));
  };
  try {
    await other.goto('/#quizgen');
    await page.goto('/#quizgen');
    const titleInput = (tab: typeof page) => tab.getByPlaceholder('أدخل اسم الاختبار هنا...');
    // A cached profile/bootstrap response does not mean React's lazy editor
    // has mounted. Create the draft through the real editor, not a storage
    // fixture which a still-mounting empty tab can immediately remove.
    for (const tab of [page, other]) await expect(titleInput(tab)).toBeVisible();
    const me = await (await page.request.get('/api/v1/auth/me')).json();
    const key = `lms_quiz_maker_unuploaded_draft_v2:${me.id}`;
    const draft = { title: 'QA two-tab retained draft' };
    await titleInput(page).fill(draft.title);
    await expect.poll(() => page.evaluate(key => JSON.parse(localStorage.getItem(key) || 'null')?.title, key)).toBe(draft.title);
    // Exercise the real stale editor's autosave (not a synthetic storage
    // event): changing its grade must neither delete nor overwrite this draft.
    await other.getByRole('button', { name: 'الثاني الثانوي', exact: true }).click();
    await expect(other.getByRole('alert').filter({ hasText: 'توجد مسودة أحدث' })).toBeVisible();
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key) || 'null')?.title, key)).toBe(draft.title);
    await titleInput(other).fill('QA stale tab must not overwrite the newer draft');
    await expect(titleInput(other)).toHaveValue('QA stale tab must not overwrite the newer draft');
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key) || 'null')?.title, key)).toBe(draft.title);
    const statuses: number[] = [];
    for (const tab of [page, other]) tab.on('response', response => {
      if (new URL(response.url()).pathname.endsWith('/auth/refresh')) statuses.push(response.status());
    });
    await context.clearCookies({ name: 'matgar_session' });
    await reloadAndWaitForIdentity();
    await expect.poll(() => statuses.length).toBeGreaterThan(0);
    expect(statuses.every(status => status === 200)).toBe(true);
    for (const tab of [page, other]) {
      await expect(titleInput(tab)).toHaveValue(draft.title);
      await expect(tab.locator('.profile-button')).toHaveCount(1);
      expect((await tab.request.get('/api/v1/auth/me')).status()).toBe(200);
      expect(await tab.evaluate(() => localStorage.getItem('lms_session_token'))).toBeNull();
    }
    let unavailable = 0;
    await context.route('**/api/v1/auth/refresh', route => {
      unavailable++;
      if (fault === 'network') return route.abort('connectionrefused');
      return route.fulfill({ status: fault, headers: { 'Retry-After': '2' }, json: { detail: 'QA temporary identity outage' } });
    });
    await context.clearCookies({ name: 'matgar_session' });
    await Promise.all([page.reload(), other.reload()]);
    await expect.poll(() => unavailable).toBeGreaterThan(0);
    // Observe longer than one cooldown; the app must not start an endless
    // automatic refresh loop or erase the teacher's draft/account on failure.
    await page.waitForTimeout(11_000);
    expect(unavailable).toBeLessThanOrEqual(4);
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key) || 'null')?.title, key)).toBe(draft.title);
    expect(await page.evaluate(() => localStorage.getItem('lms_cached_user'))).not.toBeNull();
    await context.unroute('**/api/v1/auth/refresh');
    await reloadAndWaitForIdentity();
    for (const tab of [page, other]) {
      await expect(titleInput(tab)).toHaveValue(draft.title);
      await expect(tab.locator('.profile-button')).toHaveCount(1);
      expect((await tab.request.get('/api/v1/auth/me')).status()).toBe(200);
    }
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key) || 'null')?.title, key)).toBe(draft.title);
  } finally { await other.close(); }
});
}
