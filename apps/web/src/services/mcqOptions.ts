import type { CourseOption, GeneratedQuestion } from '../types/quiz';

// API policy is 2..26 for published MCQs. Existing keys/snapshots are not
// renumbered: the editor allocates the first unused key for a new option only.
export const MAX_MCQ_OPTIONS = 26;
const keys = ['أ', 'ب', 'ج', 'د', 'هـ', 'و', ...Array.from({ length: 20 }, (_, index) => String.fromCharCode(71 + index))];

/** Validate editor labels without renumbering a saved question or OCR binding.
 * The publication serializer separately emits the API's A..Z keys.
 */
export function canonicalEditorOptionKey(value: string): string {
  const key = value.normalize('NFKC').trim().toUpperCase();
  const aliases: Record<string, string> = { 'أ': 'A', 'ا': 'A', 'ب': 'B', 'ج': 'C', 'د': 'D', 'هـ': 'E', 'ه': 'E', 'و': 'F' };
  return aliases[key] ?? key;
}

export function appendMcqOption(options: CourseOption[]): CourseOption[] {
  if (options.length >= MAX_MCQ_OPTIONS) return options;
  const key = keys.find(candidate => !options.some(option => canonicalEditorOptionKey(option.key) === canonicalEditorOptionKey(candidate)));
  if (!key) return options;
  return [...options, { key, text: `خيار ${key}`, is_correct: false }];
}

export function removeMcqOption(question: GeneratedQuestion, key: string): GeneratedQuestion {
  if (!question.options || question.options.length <= 2 || !question.options.some(option => option.key === key)) return question;
  const removedAnswer = question.options.some(option => option.key === key && option.is_correct);
  const options = question.options.filter(option => option.key !== key);
  // Removing the selected answer cannot silently invent a replacement. The
  // publication validator requires the teacher to make a new explicit choice.
  return removedAnswer ? { ...question, options, correct_answer: null, needs_answer_review: true }
    : { ...question, options };
}
