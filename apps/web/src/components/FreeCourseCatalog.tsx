import { useEffect, useState } from 'react';
import { courseService } from '../services/lmsService';
import { Course } from '../types/lms';

export function FreeCourseCatalog({ year, enrolledIds, onEnroll }: {
  year: string | null; enrolledIds: string[]; onEnroll: (id: string) => Promise<void>;
}) {
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    void courseService.getCatalogPage(page).then(result => {
      if (active) { setCourses(result.courses); setPages(Math.max(1, result.pages)); }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : 'تعذر تحميل المقررات'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page]);
  const free = courses.filter(c => c.status === 'published' && !(c.price && c.price > 0)
    && (!year || c.academicYear === year) && !enrolledIds.includes(c.id));
  return <section aria-label="المقررات المجانية" style={{ padding: 24, borderRadius: 16, background: 'var(--bg-surface)', border: '1px solid var(--border-color)', marginBottom: 20 }}>
    <h2>المقررات المجانية المتاحة لصفك</h2>
    {loading && <p role="status">جارٍ تحميل المقررات…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && free.length === 0 && <p>لا توجد مقررات مجانية إضافية في هذه الصفحة.</p>}
    {!loading && free.map(course => <article key={course.id} style={{ padding: 16, borderBottom: '1px solid var(--border-color)' }}>
      <h3>{course.title}</h3><p>{course.description}</p>
      <button className="btn-primary" disabled={pending !== null} onClick={async () => {
        setPending(course.id); setError('');
        try { await onEnroll(course.id); }
        catch (e) { setError(e instanceof Error ? e.message : 'تعذر التسجيل'); }
        finally { setPending(null); }
      }}>{pending === course.id ? 'جارٍ التسجيل…' : 'التسجيل مجانًا'}</button>
    </article>)}
    {pages > 1 && <nav aria-label="صفحات المقررات">
      <button className="btn-secondary" disabled={page === 1 || loading} onClick={() => setPage(p => p - 1)}>الصفحة السابقة</button>
      <span>{page} / {pages}</span>
      <button className="btn-secondary" disabled={page >= pages || loading} onClick={() => setPage(p => p + 1)}>الصفحة التالية</button>
    </nav>}
  </section>;
}
