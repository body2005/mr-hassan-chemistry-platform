import { describe, expect, it } from 'vitest';
import type { GeneratedQuestion } from '../types/quiz';
import { contentReviewFingerprint, hasContentReview } from './quizContentReview';

const question: GeneratedQuestion = { id: 1, question_type: 'multiple_choice', difficulty: 'medium',
  topic: '', points: null, question_text: 'Na₂CO₃ − 2. ما الإجابة؟', correct_answer: null, explanation: '',
  text_source: 'ocr', needs_content_review: true,
  options: [{ key: 'A', text: 'الخيار الأول', is_correct: false }, { key: 'B', text: 'الخيار الثاني', is_correct: false }] };

describe('source-content review, distinct from answer/marks review', () => {
  it('does not require OCR review for manual questions', () => {
    expect(hasContentReview({ ...question, text_source: undefined, needs_content_review: false })).toBe(true);
  });
  it('requires review for OCR even when the boolean flag is absent', () => {
    expect(hasContentReview({ ...question, needs_content_review: undefined })).toBe(false);
  });
  it('requires review for flagged corrupt text layers too', () => {
    expect(hasContentReview({ ...question, text_source: 'text_layer' })).toBe(false);
  });
  it('invalidates acknowledgement on stem, type, option text or order changes', () => {
    const reviewed = { ...question, content_review_fingerprint: contentReviewFingerprint(question) };
    expect(hasContentReview(JSON.parse(JSON.stringify(reviewed)))).toBe(true);
    expect(hasContentReview({ ...reviewed, question_text: reviewed.question_text.replace('−', '+') })).toBe(false);
    expect(hasContentReview({ ...reviewed, question_type: 'essay' })).toBe(false);
    expect(hasContentReview({ ...reviewed, options: [...reviewed.options!].reverse() })).toBe(false);
    expect(hasContentReview({ ...reviewed, options: reviewed.options!.map(o => ({ ...o, text: `${o.text} ن` })) })).toBe(false);
  });
  it('marks and answer selection cannot acknowledge or invalidate transcription review', () => {
    expect(hasContentReview({ ...question, points: 5, correct_answer: 'A' })).toBe(false);
    expect(hasContentReview({ ...question, content_review_fingerprint: contentReviewFingerprint(question),
      points: 5, options: question.options!.map(o => ({ ...o, is_correct: true })) })).toBe(true);
  });
});
