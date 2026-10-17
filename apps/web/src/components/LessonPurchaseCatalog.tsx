import type { ReactNode } from 'react';
import { Lock, ShoppingCart } from 'lucide-react';
import type { Course } from '../types/lms';
import type { Language } from '../utils/i18n';
import type { PaymentTarget } from '../services/paymentService';
import { newestLessonsFirst } from '../services/lessonOrder';

/** Sales cards only: never hydrate protected content or assessment endpoints. */
export function LessonPurchaseCatalog({ courses, year, enrolledIds, lang, onCheckout, fallback = null }: {
  courses: Course[];
  year: Course['academicYear'] | null;
  enrolledIds: string[];
  lang: Language;
  onCheckout: (target: PaymentTarget) => void;
  fallback?: ReactNode;
}) {
  const lessons = courses
    .filter(course => course.status === 'published' && course.academicYear === year && !enrolledIds.includes(course.id))
    .flatMap(course => newestLessonsFirst(course.lessons)
      .filter(lesson => Number(lesson.price) > 0)
      .map(lesson => ({ lesson, courseTitle: course.title })));
  if (!lessons.length) return fallback;
  const ar = lang === 'ar';
  return <section aria-label={ar ? 'دروس متاحة للشراء' : 'Lessons available to purchase'} style={{ marginBottom: 24 }}>
    <h2 style={{ color: 'var(--text-main)', fontSize: 20 }}>{ar ? 'دروس صفك المتاحة للشراء' : 'Lessons available for your grade'}</h2>
    <p style={{ color: 'var(--text-muted)', lineHeight: 1.7 }}>
      {ar ? 'اختر الدرس للاشتراك. بعد اعتماد الشراء يظهر في دروسك، ويُتاح محتواه حسب مواعيد النشر.'
        : 'Choose a lesson to purchase. After approval it appears in your lessons, with content available according to its release schedule.'}
    </p>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))', gap: 18 }}>
      {lessons.map(({ lesson, courseTitle }) => <article key={lesson.id} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 16, overflow: 'hidden', minWidth: 0 }}>
        <div style={{ background: 'var(--bg-accent)', color: 'var(--text-main)', padding: 20, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Lock size={22} aria-hidden="true" />
          <span>{ar ? 'يلزم شراء الدرس' : 'Lesson purchase required'}</span>
        </div>
        <div style={{ padding: 20 }}>
          <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 0 }}>{courseTitle}</p>
          <h3 style={{ color: 'var(--text-main)', fontSize: 17, lineHeight: 1.7, overflowWrap: 'anywhere' }}>{lesson.title}</h3>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <strong style={{ color: 'var(--text-main)' }}>{Number(lesson.price).toLocaleString(ar ? 'ar-EG' : 'en-GB')} {ar ? 'ج.م' : 'EGP'}</strong>
            <button type="button" className="btn-primary" onClick={() => onCheckout({ productType: 'lesson', productId: lesson.id })}>
              <ShoppingCart size={16} aria-hidden="true" /> {ar ? 'شراء الدرس' : 'Purchase lesson'}
            </button>
          </div>
        </div>
      </article>)}
    </div>
  </section>;
}
