import AxeBuilder from '@axe-core/playwright';
import { expect, test } from './qaTest';

test('registration wizard is keyboard-accessible, responsive, preserves edits and exposes no SMS', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/#auth');
  await page.getByRole('button', { name: 'تسجيل جديد', exact: true }).click();
  await expect(page.locator('.registration-steps li')).toHaveCount(2);
  const signin = page.getByRole('button', { name: 'تسجيل الدخول', exact: true });
  const register = page.getByRole('button', { name: 'تسجيل جديد', exact: true });
  await expect(register).toHaveAttribute('aria-pressed', 'true');
  await expect(signin).toBeInViewport();
  await expect(register).toBeInViewport();
  expect((await signin.boundingBox())!.x).toBeGreaterThan((await register.boundingBox())!.x);
  await expect.poll(async () => (await page.locator('.auth-form-panel').boundingBox())!.x).toBeLessThan(10);
  expect(await page.locator('.registration-primary').evaluate(element => getComputedStyle(element).backgroundColor)).toBe('rgb(15, 57, 43)');
  await page.screenshot({ path: test.info().outputPath('registration-site-colors-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await page.getByRole('button', { name: 'التالي', exact: true }).click();
  await expect(page.getByLabel('الاسم الأول')).toBeFocused();
  await expect(page.getByText('أدخل اسمًا صحيحًا من حرفين إلى 50 حرفًا')).toHaveCount(3);
  await page.getByLabel('الاسم الأول').fill('أحمد');
  await page.getByLabel('الاسم الأوسط').fill('محمد');
  await page.getByLabel('الاسم الأخير').fill('حسن');
  await page.getByRole('radio', { name: 'ذكر', exact: true }).focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('radio', { name: 'ذكر', exact: true })).toBeChecked();
  await page.getByLabel('السنة الدراسية').selectOption('3rd_secondary');
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark') await page.getByRole('button', { name: 'تغيير المظهر' }).click();
    const result = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    await test.info().attach('registration-'+theme+'-axe.json', { body: JSON.stringify(result), contentType: 'application/json' });
    expect(result.violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: test.info().outputPath('registration-'+theme+'.png'), fullPage: true });
  }
  await page.getByRole('button', { name: 'التالي', exact: true }).click();
  await page.getByLabel('رقم تليفونك الشخصي').fill('٠١٠١٢٣٤٥٦٧٨');
  await page.getByLabel('رقم ولي الأمر').fill('01112345678');
  await page.getByLabel('المحافظة').selectOption('CAIRO');
  await page.getByLabel('المدينة أو المنطقة').fill('البساتين');
  await page.getByLabel('اسم المدرسة').fill('مدرسة QA');
  await page.getByLabel('البريد الإلكتروني').fill('synthetic-wizard@example.com');
  await page.locator('input[name="password"]').fill('Wizard-Synthetic-2026!');
  await page.getByLabel('تأكيد كلمة المرور').fill('Wizard-Synthetic-2026!');
  await page.getByRole('button', { name: 'السابق', exact: true }).click();
  await expect(page.getByLabel('الاسم الأول')).toHaveValue('أحمد');
  await page.getByRole('button', { name: 'التالي', exact: true }).click();
  await expect(page.getByLabel('رقم تليفونك الشخصي')).toHaveValue('٠١٠١٢٣٤٥٦٧٨');
  const contact = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  await test.info().attach('registration-contact-axe.json', { body: JSON.stringify(contact), contentType:'application/json' });
  expect(contact.violations).toEqual([]);
  await expect(page.getByText('رقم الهاتف وسيلة تواصل', { exact: false })).toBeVisible();
  let requests = 0;
  await page.route('**/api/v1/auth/register', route => {
    requests++;
    return route.fulfill({ status:503, json:{detail:'Synthetic registration outage'} });
  });
  await page.getByRole('button', { name:'إنشاء حسابي', exact:true }).click();
  await expect(page.getByRole('alert')).toContainText('Synthetic registration outage');
  expect(requests).toBe(1);
  await expect(page.getByRole('heading', { name:'التواصل وإنشاء الحساب', exact:true })).toBeVisible();
  await expect(page.getByLabel('البريد الإلكتروني')).toHaveValue('synthetic-wizard@example.com');
  await expect(page.locator('input[name="password"]')).toHaveValue('Wizard-Synthetic-2026!');
  for (const theme of ['dark', 'light']) {
    if (theme === 'light') await page.getByRole('button', { name: 'تغيير المظهر' }).click();
    const errors = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    await test.info().attach('registration-error-'+theme+'-axe.json', { body: JSON.stringify(errors), contentType:'application/json' });
    expect(errors.violations).toEqual([]);
  }
  await page.unroute('**/api/v1/auth/register');
  let release = () => {};
  await page.route('**/api/v1/auth/register', async route => {
    requests++;
    await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({ status:503, json:{detail:'Synthetic registration outage'} });
  });
  try {
    await page.getByRole('button', { name:'إنشاء حسابي', exact:true }).click();
    await expect(page.locator('.registration-card form')).toHaveAttribute('aria-busy', 'true');
    await expect(page.getByRole('button', { name:'جاري إنشاء الحساب…', exact:true })).toBeDisabled();
    await expect(page.getByRole('button', { name:'السابق', exact:true })).toBeDisabled();
    const loading = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    await test.info().attach('registration-loading-axe.json', { body: JSON.stringify(loading), contentType:'application/json' });
    expect(loading.violations).toEqual([]);
    expect(requests).toBe(2); // One user retry, never an automatic request loop.
  } finally { release(); }
  await expect(page.getByRole('alert')).toContainText('Synthetic registration outage');
});
