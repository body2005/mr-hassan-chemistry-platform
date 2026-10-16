import { cairoLocalValue } from '../utils/cairoTime';

interface Props {
  start: string;
  end: string;
  announce: boolean;
  onStart: (value: string) => void;
  onEnd: (value: string) => void;
  onAnnounce: (value: boolean) => void;
  originalStart?: string;
  originalEnd?: string;
}

export function LessonScheduleFields(props: Props) {
  const now = cairoLocalValue(new Date().toISOString());
  return <fieldset className="lesson-schedule-fields">
    <legend>مواعيد إتاحة الدرس</legend>
    <p>بتوقيت مصر. تاريخ ووقت البداية مطلوبان، والإتاحة بعد جاهزية الفيديو والمرفقات. النهاية اختيارية؛ اتركها فارغة للإتاحة المستمرة.</p>
    {(['start', 'end'] as const).map(kind => {
      const value = props[kind];
      const [date = '', time = ''] = value.split('T');
      const change = kind === 'start' ? props.onStart : props.onEnd;
      const label = kind === 'start' ? 'بداية' : 'انتهاء';
      const original = kind === 'start' ? props.originalStart : props.originalEnd;
      const minimum = value === original ? '' : now;
      const [minDate, minTime] = minimum.split('T');
      return <div className="lesson-schedule-boundary" key={kind}>
        <strong>{kind === 'start' ? 'موعد النشر وبدء الإتاحة' : 'موعد انتهاء الإتاحة وإغلاق الدرس'}</strong>
        <label>تاريخ {label} الإتاحة {kind === 'start' ? '(مطلوب)' : '(اختياري)'}
          <input type="date" min={minDate || undefined} value={date} required={kind === 'start' || Boolean(time)} onChange={e => change(e.target.value || time ? `${e.target.value}T${time}` : '')} />
        </label>
        <label>وقت {label} الإتاحة {kind === 'start' ? '(مطلوب)' : '(اختياري)'}
          <input type="time" min={date === minDate ? minTime : undefined} value={time} required={kind === 'start' || Boolean(date)} onChange={e => change(date || e.target.value ? `${date}T${e.target.value}` : '')} />
        </label>
        {kind === 'end' && value && <button type="button" className="btn-secondary" onClick={() => change('')}>إلغاء موعد {label} الإتاحة</button>}
      </div>;
    })}
    <label className="lesson-schedule-notice">
      <input type="checkbox" checked={props.announce} onChange={e => props.onAnnounce(e.target.checked)} />
      <span><strong>إرسال إشعار للطلاب الآن</strong><small>عند إيقافه، يُرسل الإشعار عند موعد الإتاحة وبعد جاهزية الفيديو. يظهر الموعد في التقويم في الحالتين.</small></span>
    </label>
  </fieldset>;
}
