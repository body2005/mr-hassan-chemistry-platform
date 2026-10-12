import { test, expect, type Page } from '@playwright/test';

// Layout fixtures: backend authorization/storage are covered separately in API tests.
const timestamp = '2026-10-12T00:00:00Z';
const lesson = { id: 'lesson', title: 'شرح الكيمياء والروابط التساهمية بعنوان طويل لاختبار التفاف النص',
  kind: 'video', position: 1, content: 'وصف الدرس', publication_status: 'published',
  has_uploaded_video: true, video_duration_seconds: 600, materials: [], video_url: '/api/v1/lessons/lesson/stream', price_egp: 0 };
const course = { id: 'course', institution_id: 'school', teacher_id: 'teacher', code: 'CHEM',
  title: 'الكيمياء للصف الأول الثانوي', description: 'الشرح والمراجعة', status: 'published',
  grade_level: 'SECONDARY_1', created_at: timestamp, updated_at: timestamp, price_egp: 0,
  modules: [{ id: 'unit', title: 'الوحدة الأولى', position: 1, lessons: [lesson] }] };

async function fixture(page: Page, role: 'teacher' | 'student') {
  const user = { id: role, username: role, institution_id: 'school', role, display_name: 'مستخدم اختبار',
    email: `${role}@example.com`, grade_level: 'SECONDARY_1', created_at: timestamp, is_active: true };
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
    let body: unknown = [];
    if (path === '/bootstrap') body = { authenticated: true, user, courses: [course],
      enrolled_course_ids: ['course'], entitlements: [], notifications: [], settings: {}, unread_notifications_count: 0 };
    else if (path === '/auth/me') body = user;
    else if (path === '/courses') body = { items: [course], pagination: { total: 1, page: 1, page_size: 100, pages: 1 } };
    else if (path === '/courses/course') body = course;
    else if (path === '/courses/me/enrollments') body = [{ course_id: 'course', status: 'active' }];
    else if (path.endsWith('/content')) body = { ...course, modules: course.modules };
    else if (path.endsWith('/assessments')) body = { quizzes: [], assignments: [] };
    else if (path === '/auth/profile-summary') body = {};
    else if (path === '/payments/config') body = { methods: [], currency: 'EGP' };
    else if (path === '/users') body = [{ ...user, id: 'student', role: 'student', display_name: 'طالب بعنوان طويل',
      total_overall_grade: 50, quiz_success_rate: 100, homework_success_rate: 0, custom_field_values: {} }];
    else if (path === '/settings/public') body = {};
    else if (path === '/lessons/lesson/video-token') body = { stream_url: '/api/v1/missing-video' };
    if (path === '/realtime/stream') return route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': layout fixture\n\n' });
    return route.fulfill({ status: path === '/missing-video' ? 404 : 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

async function fits(page: Page) {
  // Inspect visible descendant bounds too: overflow:hidden must not mask a bad layout.
  const overflow = await page.locator('main').evaluate(main => Array.from(main.querySelectorAll<HTMLElement>('*'))
    .filter(node => {
      const style = getComputedStyle(node), box = node.getBoundingClientRect();
      if (!box.width || !box.height || style.position === 'absolute' || style.position === 'fixed'
          || style.visibility === 'hidden' || style.display === 'none' || node.closest('thead')) return false;
      return box.left < -2 || box.right > innerWidth + 2;
    }).map(node => `${node.tagName}.${node.className}`).slice(0, 10));
  expect(overflow).toEqual([]);
}

for (const role of ['teacher', 'student'] as const) {
  for (const width of [320, 360, 375, 390, 412, 430, 768, 1023, 1024]) {
    test(`${role} layouts fit ${width}px portrait and landscape`, async ({ page }) => {
      await fixture(page, role);
      const pageErrors: string[] = [];
      page.on('pageerror', error => pageErrors.push(error.message));
      const tabs = role === 'teacher' ? ['lessonmanagement', 'quizgen', 'submissions', 'notifications', 'profile']
        : ['mycourses', 'mysubmissions', 'notifications', 'payments', 'profile'];
      const headings: Record<string, string> = { lessonmanagement: 'إدارة الدروس',
        quizgen: 'صانع الاختبارات والتقييمات', submissions: 'متابعة الطالب',
        mycourses: course.title, mysubmissions: 'واجباتي واختباراتي المصححة', profile: 'الملف التعريفي للحساب',
        notifications: role === 'teacher' ? 'جدول مواعيد الإشعارات والتنبيهات المجدولة' : 'الإشعارات ومواعيد الدروس والواجبات' };
      await page.setViewportSize({ width, height: 850 });
      for (const tab of tabs) {
        await page.goto(`/#${tab}`);
        const ready = tab === 'payments' ? page.getByText('تأكيد الاشتراك والسداد', { exact: true })
          : page.getByRole('heading', { name: headings[tab], exact: true });
        await expect(ready).toBeVisible().catch(error => {
          throw new Error(`${tab}: ${pageErrors.join('; ')}\n${error}`);
        });
        await page.waitForTimeout(150);
        await fits(page);
        expect(pageErrors).toEqual([]);
        if (width === 360 && ['lessonmanagement', 'submissions', 'payments'].includes(tab)) {
          await page.screenshot({ path: test.info().outputPath(`${tab}-360.png`), fullPage: true });
        }
      }
      await page.setViewportSize({ width: 850, height: width });
      await fits(page);
    });
  }
}

test('teacher player browser Back returns to its list and Forward restores it', async ({ page }) => {
  await fixture(page, 'teacher');
  await page.goto('/#lessonmanagement');
  await page.getByRole('button', { name: 'مشاهدة الدرس', exact: true }).click();
  await expect(page.locator('.lesson-video-player')).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('button', { name: 'مشاهدة الدرس', exact: true })).toBeVisible();
  await page.goForward();
  await expect(page.locator('.lesson-video-player')).toBeVisible();
});

test('student player browser Back preserves the lesson list and Forward restores the player', async ({ page }) => {
  await fixture(page, 'student');
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/#mycourses');
  const watch = page.getByRole('button', { name: 'مشاهدة الدرس', exact: true });
  await watch.click();
  await expect(page.locator('.lesson-video-player')).toBeVisible();
  await fits(page);
  await page.goBack();
  await expect(watch).toBeVisible();
  await page.goForward();
  await expect(page.locator('.lesson-video-player')).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('player-375.png'), fullPage: true });
});
