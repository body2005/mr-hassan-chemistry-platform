import { useEffect, useState } from 'react';
import { apiRequest, getApiAuthGeneration } from '../services/apiClient';
import { courseService } from '../services/lmsService';
import { assessmentWindow } from '../services/assessmentSchedule';
import { cairoLocalValue, requireUpcomingTime } from '../utils/cairoTime';
import { useToast } from './ToastProvider';

type Assessment = { id: string; title: string; status: string; starts_at: string | null; ends_at?: string | null; due_at?: string | null; kind: 'quiz' | 'assignment' };

/** Server records, including scheduled/draft assessments, across this manager's scope. */
export function AssessmentScheduleManager() {
  const toast = useToast();
  const [items, setItems] = useState<Assessment[]>([]);
  const [selection, setSelection] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const item = items.find(row => `${row.kind}:${row.id}` === selection);

  useEffect(() => {
    let active = true;
    const generation = getApiAuthGeneration();
    setLoading(true);
    void Promise.all([
      apiRequest<Omit<Assessment, 'kind'>[]>('/quizzes', { skipCache: true }),
      apiRequest<Omit<Assessment, 'kind'>[]>('/assignments', { skipCache: true }),
    ]).then(([quizzes, assignments]) => {
      if (active && generation === getApiAuthGeneration()) {
        setItems([...quizzes.map(row => ({ ...row, kind: 'quiz' as const })), ...assignments.map(row => ({ ...row, kind: 'assignment' as const }))]);
        setError('');
      }
    }).catch(() => { if (active) setError('تعذر تحميل التقييمات من الخادم.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);

  useEffect(() => {
    setStart(item?.starts_at ? cairoLocalValue(item.starts_at) : '');
    const value = item?.kind === 'quiz' ? item.ends_at : item?.due_at;
    setEnd(value ? cairoLocalValue(value) : '');
  }, [item]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const changed = () => { clearTimeout(timer); timer = setTimeout(() => setRevision(value => value + 1), 300); };
    window.addEventListener('lms_assessments_updated', changed);
    return () => { clearTimeout(timer); window.removeEventListener('lms_assessments_updated', changed); };
  }, []);

  async function save(status?: 'draft' | 'published', cancelSchedule = false) {
    if (!item || busy) return;
    setError('');
    try {
      const schedule = assessmentWindow(cancelSchedule ? null : start, cancelSchedule ? null : end);
      requireUpcomingTime(schedule.startsAt, item.starts_at);
      requireUpcomingTime(schedule.endsAt, item.kind === 'quiz' ? item.ends_at : item.due_at);
      setBusy(true);
      await courseService.updateAssessmentPublication(item.kind, item.id, cancelSchedule ? null : start, cancelSchedule ? null : end, status);
      toast({ message: 'تم حفظ إعدادات الإتاحة.', tone: 'success' });
      setRevision(value => value + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'تعذر حفظ إعدادات الإتاحة.');
    } finally { setBusy(false); }
  }

  return <section className="card" style={{ padding: 20 }} aria-labelledby="assessment-schedule-title">
    <h3 id="assessment-schedule-title">إدارة نشر الاختبارات والواجبات</h3>
    <p>المواعيد بتوقيت القاهرة. ترك البداية فارغة يسمح بالإتاحة فور النشر، وترك النهاية فارغة يلغي موعد الإغلاق.</p>
    <label htmlFor="managed-assessment">التقييم</label>
    <select id="managed-assessment" value={selection} disabled={busy || loading} onChange={event => setSelection(event.target.value)}>
      <option value="">{loading ? 'جارٍ التحميل…' : 'اختر اختبارًا أو واجبًا'}</option>
      {items.map(row => <option key={`${row.kind}:${row.id}`} value={`${row.kind}:${row.id}`}>
        {row.kind === 'quiz' ? 'اختبار' : 'واجب'} · {row.title} · {row.status === 'draft' ? 'مسودة' : row.status === 'closed' ? 'مغلق' : 'منشور'}
      </option>)}
    </select>
    {item && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 16 }}>
      <label>بداية الإتاحة<input type="datetime-local" value={start} disabled={busy} onChange={event => setStart(event.target.value)} /></label>
      <label>نهاية الإتاحة<input type="datetime-local" value={end} disabled={busy} onChange={event => setEnd(event.target.value)} /></label>
      <button type="button" className="btn-primary" disabled={busy} onClick={() => void save()}>حفظ المواعيد</button>
      <button type="button" className="btn-secondary" disabled={busy} onClick={() => void save(undefined, true)}>إلغاء الجدولة</button>
      <button type="button" className="btn-secondary" disabled={busy} onClick={() => void save(item.status === 'published' ? 'draft' : 'published')}>
        {item.status === 'published' ? 'سحب النشر' : 'نشر التقييم'}
      </button>
    </div>}
    {error && <div role="alert"><p>{error}</p><button type="button" disabled={busy} onClick={() => setRevision(value => value + 1)}>إعادة تحميل التقييمات</button></div>}
  </section>;
}
