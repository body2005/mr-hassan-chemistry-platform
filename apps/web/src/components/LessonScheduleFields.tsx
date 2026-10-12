interface Props {
  start: string;
  end: string;
  announce: boolean;
  onStart: (value: string) => void;
  onEnd: (value: string) => void;
  onAnnounce: (value: boolean) => void;
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
      <span><strong>إرسال إشعار للطلاب الآن</strong><small>عند إيقافه، يُرسل الإشعار عند موعد الإتاحة وبعد جاهزية الفيديو. يظهر الموعد في التقويم في الحالتين.</small></span>
    </label>
  </fieldset>;
}
