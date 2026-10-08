import { describe, expect, it } from 'vitest';
import { appendMcqOption, MAX_MCQ_OPTIONS, removeMcqOption } from './mcqOptions';
import type { GeneratedQuestion } from '../types/quiz';

describe('MCQ editor key and answer policy', () => {
  const question: GeneratedQuestion = { id: 1, question_type: 'multiple_choice', difficulty: 'easy', topic: '', points: 1,
    question_text: 'Question', explanation: '', correct_answer: 'Second', options: [
      { key: 'أ', text: 'First', is_correct: false }, { key: 'ب', text: 'Second', is_correct: true }, { key: 'ج', text: 'Third', is_correct: false }] };
  it('allocates a unique key after removing a middle option without renumbering survivors', () => {
    const reduced = removeMcqOption(question, 'ب');
    const result = appendMcqOption(reduced.options!);
    expect(result.map(option => option.key)).toEqual(['أ', 'ج', 'ب']);
    expect(new Set(result.map(option => option.key)).size).toBe(result.length);
  });
  it('requires explicit answer review and never mutates the previous draft when the correct option is deleted', () => {
    const result = removeMcqOption(question, 'ب');
    expect(result.correct_answer).toBeNull();
    expect(result.needs_answer_review).toBe(true);
    expect(result.options!.some(option => option.is_correct)).toBe(false);
    expect(question.options![0].is_correct).toBe(false);
    expect(question.correct_answer).toBe('Second');
  });
  it('retains an existing correct choice and historical explicit keys', () => {
    const result = removeMcqOption(question, 'أ');
    expect(result.options!.map(option => option.key)).toEqual(['ب', 'ج']);
    expect(result.correct_answer).toBe('Second');
    expect(removeMcqOption(result, 'ب')).toBe(result);
  });
  it('stops at 26 choices without generating the 27th ASCII bracket', () => {
    let options = question.options!;
    while (options.length < MAX_MCQ_OPTIONS) options = appendMcqOption(options);
    expect(options).toHaveLength(26);
    expect(options.some(option => option.key === '[')).toBe(false);
    expect(appendMcqOption(options)).toBe(options);
  });
});
