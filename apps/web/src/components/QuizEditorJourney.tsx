import type { EditorStage } from '../services/assessmentPublication';

const stages: { id: EditorStage; label: string; next: string }[] = [
  { id: 'setup', label: 'الإعداد', next: 'اختر المقرر والدرس واسم النشاط، ثم راجع الأسئلة.' },
  { id: 'review', label: 'مراجعة الأسئلة', next: 'راجع النص والإجابات والدرجات، ثم حدّد موعد النشر.' },
  { id: 'publish', label: 'النشر', next: 'حدّد المواعيد، ثم راجع ملخص النشر قبل التأكيد.' },
];
export function QuizEditorJourney({ stage, questionCount, points }: {
  stage: EditorStage; questionCount: number; points: number;
}) {
  return <section className="quiz-editor-journey" aria-label="مراحل إعداد النشاط">
    <p><strong>{questionCount} أسئلة · {points} درجات</strong><span>{stages.find(item => item.id === stage)?.next}</span></p>
  </section>;
}
