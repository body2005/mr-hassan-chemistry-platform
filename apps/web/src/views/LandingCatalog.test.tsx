import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LandingPageView } from './LandingPageView';
import { FloatingProgressFab } from '../components/FloatingProgressFab';
import { translations } from '../utils/i18n';
import type { Course, CurrentUser } from '../types/lms';
import { courseService } from '../services/lmsService';

vi.mock('../components/ToastProvider', () => ({ useToast: () => vi.fn() }));
vi.mock('../services/lmsService', () => ({ courseService: { getPublicCatalogPage: vi.fn() } }));
const courses = [
  { id: 'alpha', title: 'مقرر الذرة', academicYear: '1st_secondary', academicYearLabel: 'الأول الثانوي' },
  { id: 'beta', title: 'مقرر التفاعل', academicYear: '3rd_secondary', academicYearLabel: 'الثالث الثانوي' },
].map(c => ({ ...c, subject: 'Chemistry', teacherName: 'Synthetic', teacherTitle: 'Teacher',
  description: 'شرح مقرر الكيمياء', thumbnailColor: '#0f392b', lessonsCount: 0,
  totalDurationFormatted: '0', lessons: [{ id: `${c.id}-lesson`, courseId: c.id, academicYear: c.academicYear,
    title: c.title, description: '', durationMinutes: 10, durationFormatted: '10 دقائق', videoUrl: '',
    materials: [], uploadedByTeacherName: 'Synthetic', uploadedAt: '', order: 1,
    price: 125, hasUploadedVideo: true }], assessments: [], enrolledStudentsCount: 0 })) as Course[];
let root: Root, host: HTMLDivElement;
const navigate = vi.fn();
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  window.history.replaceState({}, '', '/');
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  navigate.mockReset();
  vi.mocked(courseService.getPublicCatalogPage).mockReset();
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function landing() {
  await act(async () => root.render(<LandingPageView courses={courses} lang="ar" theme="light"
    onNavigateToAuth={navigate} onToggleLang={vi.fn()} onToggleTheme={vi.fn()} />));
}
function button(text: string) { return [...host.querySelectorAll('button')].find(b => b.textContent === text)!; }

async function publicLanding() {
  await act(async () => root.render(<LandingPageView lang="ar" theme="dark"
    onNavigateToAuth={navigate} onToggleLang={vi.fn()} onToggleTheme={vi.fn()} />));
}
async function finishDebounce() { await act(async () => { await new Promise(resolve => setTimeout(resolve, 350)); }); }

it('loads the public server catalog without private cached courses or a false empty state', async () => {
  let complete!: (value: { courses: Course[]; pages: number; total: number }) => void;
  vi.mocked(courseService.getPublicCatalogPage).mockImplementation(() => new Promise(resolve => { complete = resolve; }));
  localStorage.setItem('lms_courses', JSON.stringify([{ title: 'PRIVATE ACCOUNT DRAFT' }]));
  await publicLanding();
  expect(host.querySelector('.catalog-empty')).toBeNull();
  expect(host.textContent).not.toContain('PRIVATE ACCOUNT DRAFT');
  expect(host.querySelector('#courses [role="status"]')?.textContent).toContain('جارٍ تحميل');
  await finishDebounce();
  expect(courseService.getPublicCatalogPage).toHaveBeenCalledTimes(1);
  await act(async () => complete({ courses, pages: 2, total: 26 }));
  expect(host.querySelectorAll('#courses h3')).toHaveLength(2);
  expect(host.querySelector('#courses')?.textContent).not.toContain('26 مقرر');
  expect(button('الصفحة التالية')).toBeDefined();
});

it('stops after a catalog failure and retries only by user action', async () => {
  vi.mocked(courseService.getPublicCatalogPage).mockRejectedValueOnce({ status: 429 })
    .mockResolvedValue({ courses, pages: 1, total: 2 });
  await publicLanding(); await finishDebounce();
  expect(host.querySelector('#courses [role="alert"]')?.textContent).toContain('طلبات كثيرة');
  expect(host.querySelector('.catalog-empty')).toBeNull();
  await finishDebounce();
  expect(courseService.getPublicCatalogPage).toHaveBeenCalledTimes(1);
  await act(async () => button('إعادة تحميل الاشتراكات').click()); await finishDebounce();
  expect(courseService.getPublicCatalogPage).toHaveBeenCalledTimes(2);
  expect(host.querySelectorAll('#courses h3')).toHaveLength(2);
});

it('filters by grade and rejects a late response for the previous grade', async () => {
  let stale!: (value: { courses: Course[]; pages: number; total: number }) => void;
  vi.mocked(courseService.getPublicCatalogPage).mockImplementationOnce(() => new Promise(resolve => { stale = resolve; }))
    .mockResolvedValue({ courses: [courses[1]], pages: 1, total: 1 });
  await publicLanding(); await finishDebounce();
  await act(async () => button(translations.ar.thirdSecondary).click()); await finishDebounce();
  expect(courseService.getPublicCatalogPage).toHaveBeenLastCalledWith(1, '', '3rd_secondary', expect.any(AbortSignal));
  await act(async () => stale({ courses, pages: 1, total: 2 }));
  expect(host.querySelectorAll('#courses h3')).toHaveLength(1);
  expect(host.querySelector('#courses')!.textContent).not.toContain('مقرر الذرة');
});

it('loads only the requested page and resets pagination when the grade changes', async () => {
  vi.mocked(courseService.getPublicCatalogPage).mockResolvedValue({ courses, pages: 3, total: 50 });
  await publicLanding(); await finishDebounce();
  await act(async () => button('الصفحة التالية').click()); await finishDebounce();
  expect(courseService.getPublicCatalogPage).toHaveBeenLastCalledWith(2, '', '', expect.any(AbortSignal));
  await act(async () => button(translations.ar.firstSecondary).click()); await finishDebounce();
  expect(courseService.getPublicCatalogPage).toHaveBeenLastCalledWith(1, '', '1st_secondary', expect.any(AbortSignal));
});

it('shows only uploaded subscriptions with real prices, without a search or library', async () => {
  await landing();
  expect(host.querySelector('#catalog-search')).toBeNull();
  expect(host.querySelector('#library')).toBeNull();
  expect(host.querySelector('a[href="#library"]')).toBeNull();
  expect(host.querySelector('.subscription-actions strong')?.textContent).toContain('١٢٥');
  expect(host.querySelector('#courses h2')?.textContent).toBe('الاشتراكات');
  await act(async () => button(translations.ar.secondSecondary).click());
  expect(host.querySelector('.catalog-empty')?.textContent).toContain('لا توجد اشتراكات');
  await act(async () => button('كل الصفوف').click());
  expect(host.querySelectorAll('.subscription-card')).toHaveLength(2);
});

it('opens the grade menu by click without hover and applies its choice', async () => {
  await landing();
  const toggle = [...host.querySelectorAll('button')].find(b => b.textContent?.includes(translations.ar.landingNavYears))!;
  await act(async () => toggle.click());
  expect(toggle.getAttribute('aria-expanded')).toBe('true');
  const choice = [...host.querySelectorAll('#catalog-grade-menu a')].find(a => a.textContent?.includes(translations.ar.thirdSecondary))!;
  await act(async () => choice.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })));
  expect(host.querySelector('#courses')!.textContent).not.toContain('مقرر الذرة');
  expect(host.querySelector('#courses')!.textContent).toContain('مقرر التفاعل');
  expect(toggle.getAttribute('aria-expanded')).toBe('false');
});

it('restores grade while ignoring removed search and preserves unrelated routing state', async () => {
  window.history.replaceState({}, '', '/?catalog_grade=3rd_secondary&catalog_search=irrelevant&keep=yes#landing');
  await landing();
  expect(host.querySelectorAll('.subscription-card')).toHaveLength(1);
  await act(async () => button(translations.ar.firstSecondary).click());
  const params = new URLSearchParams(window.location.search);
  expect(params.get('keep')).toBe('yes');
  expect(params.get('catalog_grade')).toBe('1st_secondary');
  expect(params.has('catalog_search')).toBe(false);
  expect(window.location.hash).toBe('#landing');
});

it('shows the full static headline and passes the exact selected course to sign in', async () => {
  await landing();
  expect(host.querySelector('h1')!.textContent).toBe(translations.ar.landingHeroTitle);
  expect(host.querySelector('h1 span')).toBeNull();
  const actions = [...host.querySelectorAll('#courses button')].filter(b => b.textContent === 'اشترك الآن');
  await act(async () => (actions[1] as HTMLButtonElement).click());
  expect(navigate).toHaveBeenCalledWith('signin', courses[1]);
  expect(host.querySelector('#courses')!.textContent).not.toContain('أضف المقرر');
});

it('explains the paid course subscription instead of calling an included lesson free', async () => {
  const paid = { ...courses[0], price: 300, lessons: [{ ...courses[0].lessons[0], price: 0 }] };
  await act(async () => root.render(<LandingPageView courses={[paid]} lang="ar" theme="light"
    onNavigateToAuth={navigate} onToggleLang={vi.fn()} onToggleTheme={vi.fn()} />));
  expect(host.querySelector('.subscription-actions')?.textContent).toContain('٣٠٠');
  expect(host.querySelector('.subscription-price-note')?.textContent).toBe('ضمن اشتراك الصف');
  expect(host.querySelector('.subscription-actions')?.textContent).not.toContain('مجاني');
});

const student = { id: 'synthetic-student', role: 'student', academicYear: '1st_secondary' } as CurrentUser;
it('progress names only the supplied course, is inline, and responds to a normal tap once', async () => {
  await act(async () => root.render(<FloatingProgressFab course={courses[1]} completedLessonIds={[]}
    currentUser={student} theme="dark" />));
  const control = host.querySelector('button')!;
  expect(control.getAttribute('aria-label')).toContain(courses[1].title);
  expect(host.textContent).not.toContain(courses[0].title);
  expect((host.firstElementChild as HTMLElement).style.position).toBe('relative');
  await act(async () => control.click());
  expect(control.getAttribute('aria-expanded')).toBe('true');
  await act(async () => control.click());
  expect(control.getAttribute('aria-expanded')).toBe('false');
});

it('dragging does not accidentally open the progress panel; next tap works', async () => {
  await act(async () => root.render(<FloatingProgressFab course={courses[1]} completedLessonIds={[]}
    currentUser={student} theme="light" placement="floating" />));
  const control = host.querySelector('button')!;
  await act(async () => {
    control.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 10, clientY: 10 }));
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 60, clientY: 60 }));
    window.dispatchEvent(new MouseEvent('pointerup'));
    control.click();
  });
  expect(control.getAttribute('aria-expanded')).toBe('false');
  await act(async () => {
    control.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0 }));
    window.dispatchEvent(new MouseEvent('pointerup'));
    control.click();
  });
  expect(control.getAttribute('aria-expanded')).toBe('true');
});
