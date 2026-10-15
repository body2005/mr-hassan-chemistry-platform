import type { GeneratedQuestion } from '../types/quiz';
import { canonicalQuestionType, type QuestionType } from '../services/questionType';
import { useTranslation } from '../utils/i18n';

const types: QuestionType[] = ['multiple_choice', 'true_false', 'essay', 'short_answer', 'fill_in_blank', 'ordering', 'matching'];

export function QuestionPointsTable({ questions, disabled, onChange }: {
  questions: GeneratedQuestion[]; disabled: boolean;
  onChange: (type: QuestionType, points: number | null) => void;
}) {
  const { t } = useTranslation();
  return <aside className="question-points-panel" aria-label={t('lesson.typePoints')}>
    <h3>{t('lesson.typePoints')}</h3>
    <p>{t('lesson.typePointsHint')}</p>
    <table>
      <thead><tr><th scope="col">{t('lesson.questionType')}</th><th scope="col">{t('lesson.questionCount')}</th><th scope="col">{t('lesson.pointsEach')}</th></tr></thead>
      <tbody>{types.map(type => {
        const items = questions.filter(question => canonicalQuestionType(question.question_type) === type);
        const common = items.length && items.every(question => question.points === items[0].points) ? items[0].points ?? '' : '';
        const label = t(`lesson.type_${type}`);
        return <tr key={type}><th scope="row">{label}</th><td>{items.length}</td><td>
          <input type="number" min="0.01" max="1000" step="any" inputMode="decimal"
            aria-label={t('lesson.pointsForType', { type: label })} disabled={disabled || items.length === 0}
            value={common} placeholder={items.length ? '—' : ''} onChange={event => {
              const raw = event.target.value;
              const points = raw === '' ? null : Number(raw);
              if (points === null || (Number.isFinite(points) && points > 0 && points <= 1000)) onChange(type, points);
            }} />
        </td></tr>;
      })}</tbody>
    </table>
  </aside>;
}
