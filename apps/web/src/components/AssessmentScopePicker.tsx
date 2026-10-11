import { useEffect, useId, useRef } from 'react';
import { ChevronDown, X } from 'lucide-react';
import type { Course } from '../types/lms';

type ScopeOption = { id: string; courseId: string; title: string; group: string; disabled: boolean };

function ScopeSelect({ label, placeholder, emptyText, options, values, onToggle, onClear }: {
  label: string; placeholder: string; emptyText: string; options: ScopeOption[]; values: string[];
  onToggle: (option: ScopeOption) => void;
  onClear: () => void;
}) {
  const id = useId();
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const selected = options.filter(option => values.includes(option.id));

  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !detailsRef.current?.contains(event.target)) {
        detailsRef.current?.removeAttribute('open');
      }
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, []);

  return <div className="assessment-scope-field">
    <span className="assessment-scope-label" id={`${id}-label`}>{label}</span>
    <details className="assessment-scope-select" ref={detailsRef} onKeyDown={event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        detailsRef.current?.removeAttribute('open');
        detailsRef.current?.querySelector('summary')?.focus();
      }
    }}>
      <summary aria-labelledby={`${id}-label ${id}-value`}>
        <span id={`${id}-value`}>{selected.length ? `تم اختيار ${selected.length}` : placeholder}</span>
        <ChevronDown size={18} aria-hidden="true" />
      </summary>
      <div className="assessment-scope-options" role="group" aria-labelledby={`${id}-label`}>
        {!options.length && <p>{emptyText}</p>}
        {options.map(option => <label key={option.id}>
          <input type="checkbox" checked={values.includes(option.id)} disabled={option.disabled}
            onChange={() => onToggle(option)} />
          <span>{option.title}{option.group && <small>{option.group}</small>}</span>
        </label>)}
      </div>
    </details>
    {selected.length > 0 && <ul className="assessment-scope-selections" aria-label={`${label} المختارة`}>
      {selected.map(option => <li key={option.id}>
        <span>{option.title}</span>
        <button type="button" aria-label={`إلغاء اختيار ${option.title}`} onClick={() => onToggle(option)}>
          <X size={14} aria-hidden="true" />
        </button>
      </li>)}
    </ul>}
    {selected.length > 0 && <button type="button" className="assessment-scope-clear" onClick={onClear}>مسح {label}</button>}
  </div>;
}

export function AssessmentScopePicker({ courses, courseId, lessonIds, moduleIds, onChange }: {
  courses: Course[]; courseId?: string; lessonIds: string[]; moduleIds: string[];
  onChange: (courseId: string, lessonIds: string[], moduleIds: string[]) => void;
}) {
  const selected = lessonIds.length + moduleIds.length > 0;
  const toggle = (values: string[], id: string) => values.includes(id) ? values.filter(value => value !== id) : [...values, id];
  const units: ScopeOption[] = [];
  const lessons: ScopeOption[] = [];
  courses.forEach(course => {
    const moduleSeen = new Set<string>();
    const disabled = selected && courseId !== course.id;
    course.lessons.forEach(lesson => {
      if (lesson.moduleId && !moduleSeen.has(lesson.moduleId)) {
        moduleSeen.add(lesson.moduleId);
        units.push({ id: lesson.moduleId, courseId: course.id, title: lesson.unitTitle || 'الوحدة',
          group: courses.length > 1 ? course.title : '', disabled });
      }
      lessons.push({ id: lesson.id, courseId: course.id, title: lesson.title,
        group: [lesson.unitTitle, courses.length > 1 ? course.title : ''].filter(Boolean).join(' — '), disabled });
    });
  });
  return <fieldset className="assessment-scope-picker">
    <legend>المحتوى المرتبط بالتقييم</legend>
    <p>اختَر أكثر من وحدة أو درس. يلزم إتاحة المحتوى المحدد للطالب قبل الحل.</p>
    <ScopeSelect label="الوحدات (اختياري)" placeholder="بدون وحدات — اختَر دروسًا مباشرة" emptyText="لا توجد وحدات بها دروس لهذا الصف."
      options={units} values={moduleIds} onToggle={option => onChange(option.courseId, lessonIds, toggle(moduleIds, option.id))}
      onClear={() => onChange(courseId || '', lessonIds, [])} />
    <ScopeSelect label="الدروس" placeholder="اختَر الدروس" emptyText="أضف درسًا لهذا الصف أولًا."
      options={lessons} values={lessonIds} onToggle={option => onChange(option.courseId, toggle(lessonIds, option.id), moduleIds)}
      onClear={() => onChange(courseId || '', [], moduleIds)} />
    {selected && courses.length > 1 && <p>لاختيار محتوى مجموعة أخرى، ألغِ الاختيارات الحالية أولًا.</p>}
  </fieldset>;
}
