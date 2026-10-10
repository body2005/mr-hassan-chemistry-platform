import type { Course } from '../types/lms';

export function AssessmentScopePicker({ courses, courseId, lessonIds, moduleIds, onChange }: {
  courses: Course[]; courseId?: string; lessonIds: string[]; moduleIds: string[];
  onChange: (courseId: string, lessonIds: string[], moduleIds: string[]) => void;
}) {
  const selected = lessonIds.length + moduleIds.length > 0;
  const toggle = (values: string[], id: string) => values.includes(id) ? values.filter(value => value !== id) : [...values, id];
  return <fieldset className="assessment-scope-picker">
    <legend>الدروس والوحدات المرتبطة بالتقييم</legend>
    <p>اختَر درسًا أو أكثر، أو وحدات كاملة. يلزم إتاحة المحتوى المحدد للطالب قبل الحل.</p>
    {courses.every(course => !course.lessons.length) && <p>أضف درسًا لهذا الصف أولًا.</p>}
    {courses.map(course => {
      const groups = new Map<string, typeof course.lessons>();
      course.lessons.forEach(lesson => {
        const id = lesson.moduleId || '';
        groups.set(id, [...(groups.get(id) || []), lesson]);
      });
      const disabled = selected && courseId !== course.id;
      return <div key={course.id}>
        {courses.length > 1 && <strong>{course.title}</strong>}
        {[...groups].map(([moduleId, lessons]) => <div className="assessment-scope-unit" key={moduleId}>
          {moduleId && <label><input type="checkbox" checked={moduleIds.includes(moduleId)} disabled={disabled}
            onChange={() => onChange(course.id, lessonIds, toggle(moduleIds, moduleId))} />
            {lessons[0].unitTitle || 'الوحدة'} — الوحدة كاملة</label>}
          {lessons.map(lesson => <label key={lesson.id}><input type="checkbox" checked={lessonIds.includes(lesson.id)} disabled={disabled}
            onChange={() => onChange(course.id, toggle(lessonIds, lesson.id), moduleIds)} />{lesson.title}</label>)}
        </div>)}
      </div>;
    })}
    {selected && courses.length > 1 && <p>لاختيار محتوى مجموعة أخرى، ألغِ الاختيارات الحالية أولًا.</p>}
  </fieldset>;
}
