import type { EditorStage } from '../services/assessmentPublication';

const stages: { id: EditorStage; label: string; next: string }[] = [
  { id: 'setup', label: 'الإعداد', next: 'اختر المقرر والدرس واسم النشاط، ثم راجع الأسئلة.' },
  { id: 'review', label: 'مراجعة الأسئلة', next: 'راجع النص والإجابات والدرجات، ثم حدّد موعد النشر.' },
  { id: 'publish', label: 'النشر', next: 'حدّد المواعيد، ثم راجع ملخص النشر قبل التأكيد.' },
];
export function QuizEditorJourney({ stage, questionCount, points, onStageChange }: {
  stage: EditorStage; questionCount: number; points: number; onStageChange: (stage: EditorStage) => void;
}) {
  return <section className="quiz-editor-journey" aria-label="مراحل إعداد النشاط">
    <nav aria-label="مراحل إعداد الامتحان">{stages.map((item, index) => <button key={item.id} type="button"
      aria-current={stage === item.id ? 'step' : undefined} onClick={() => onStageChange(item.id)}>
      <span aria-hidden="true">{index + 1}</span>{item.label}
    </button>)}</nav>
    <p><strong>{questionCount} أسئلة · {points} درجات</strong><span>{stages.find(item => item.id === stage)?.next}</span></p>
  </section>;
}
