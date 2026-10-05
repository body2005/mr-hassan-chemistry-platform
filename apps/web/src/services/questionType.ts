export type QuestionType = 'multiple_choice' | 'true_false' | 'essay' | 'short_answer' | 'fill_in_blank' | 'ordering' | 'matching';

/** Translate Extract's vocabulary at the API boundary, never guess an unknown type. */
export function canonicalQuestionType(value?: string): QuestionType | 'unknown' {
  const normalized = value?.trim().toLowerCase();
  if (normalized === 'mcq' || normalized === 'multiple_choice') return 'multiple_choice';
  if (normalized === 'truefalse' || normalized === 'true_false') return 'true_false';
  if (['fill_blank', 'fill_in_blank', 'fill_in_the_blank'].includes(normalized || '')) return 'fill_in_blank';
  if (['essay', 'short_answer', 'ordering', 'matching'].includes(normalized || '')) return normalized as QuestionType;
  return 'unknown';
}
