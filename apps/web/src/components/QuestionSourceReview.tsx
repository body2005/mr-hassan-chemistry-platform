import type { GeneratedQuestion } from '../types/quiz';
import { hasContentReview, requiresContentReview } from '../services/quizContentReview';

/** Explicit teacher source comparison; never substitutes OCR confidence for consent. */
export function QuestionSourceReview({ question, index, onReview }: {
  question: GeneratedQuestion; index: number; onReview: (checked: boolean) => void;
}) {
  if (!requiresContentReview(question)) return null;
  return <label style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px',
    marginBottom: '12px', borderRadius: '8px', border: '1px solid var(--border-color)',
    background: 'var(--bg-surface-secondary)', color: 'var(--text-main)', lineHeight: '1.7' }}>
    <input type="checkbox" aria-label={`مراجعة نص السؤال ${index + 1} مع المصدر`}
      checked={hasContentReview(question)} onChange={event => onReview(event.target.checked)} />
    <span>قارنت نص السؤال والاختيارات بالملف الأصلي{question.source_page ? ` — صفحة ${question.source_page}` : ''}.
      <small style={{ display: 'block', color: 'var(--text-muted)' }}>
        قراءة الصور قد تُسقط حروفًا أو رموزًا. صحّح النص أولًا؛ أي تعديل للنص أو الاختيارات يلغي هذا التأكيد.
      </small>
    </span>
  </label>;
}
