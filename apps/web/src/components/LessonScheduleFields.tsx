interface Props {
  start: string;
  end: string;
  announce: boolean;
  draft: boolean;
  onStart: (value: string) => void;
  onEnd: (value: string) => void;
  onAnnounce: (value: boolean) => void;
  onDraft: (value: boolean) => void;
}

export function LessonScheduleFields(props: Props) {
  return <fieldset className="lesson-schedule-fields">
    <legend>مواعيد إتاحة الدرس</legend>
    <p>بتوقيت مصر. اترك البداية فارغة للإتاحة بعد اكتمال الرفع، والنهاية فارغة للإتاحة المستمرة.</p>
    {(['start', 'end'] as const).map(kind => {
      const value = props[kind];
      const [date = '', time = ''] = value.split('T');
      const change = kind === 'start' ? props.onStart : props.onEnd;
      const label = kind === 'start' ? 'بداية' : 'انتهاء';
      return <div className="lesson-schedule-boundary" key={kind}>
        <strong>{kind === 'start' ? 'موعد النشر وبدء الإتاحة' : 'موعد انتهاء الإتاحة وإغلاق الدرس'}</strong>
        <label>تاريخ {label} الإتاحة
          <input type="date" value={date} required={Boolean(time)} onChange={e => change(e.target.value || time ? `${e.target.value}T${time}` : '')} />
        </label>
        <label>وقت {label} الإتاحة
          <input type="time" value={time} required={Boolean(date)} onChange={e => change(date || e.target.value ? `${date}T${e.target.value}` : '')} />
        </label>
        {value && <button type="button" className="btn-secondary" onClick={() => change('')}>إلغاء موعد {label} الإتاحة</button>}
      </div>;
    })}
    <label className="lesson-schedule-notice">
      <input type="checkbox" checked={props.announce} onChange={e => props.onAnnounce(e.target.checked)} />
      <span><strong>إظهار في تقويم وجدول الطلاب وإرسال إشعار</strong><small>يصل التنبيه عند إتاحة الدرس فعليًا واكتمال الرفع.</small></span>
    </label>
    <label className="lesson-schedule-draft"><input type="checkbox" checked={props.draft} onChange={e => props.onDraft(e.target.checked)} />حفظ كمسودة دون إتاحته للطلاب</label>
  </fieldset>;
}
