import { expect, it } from 'vitest';
import { validateAssessmentPublication, type PublicationInput } from './assessmentPublication';
import { contentReviewFingerprint } from './quizContentReview';

const input = (): PublicationInput => ({ title: 'اختبار الكيمياء', lessonId: 'lesson', isQuiz: true,
  duration: 30, startDate: '2027-01-01', startTime: '06:00 م', endDate: '2027-01-02', endTime: '08:00 م',
  questions: [{ id: 1, question_type: 'MCQ', question_text: 'أي عنصر؟', points: 10,
    correct_answer: 'A', difficulty: 'easy', topic: '', explanation: '',
    options: [{ key: 'A', text: 'حديد', is_correct: true }, { key: 'B', text: 'هواء', is_correct: false }] }],
});
it('keeps manually graded assignments publishable without an automatic answer key', () => {
  const value = input(); value.isQuiz = false; value.questions[0].correct_answer = null;
  value.questions[0].options!.forEach(option => { option.is_correct = false; });
  expect(validateAssessmentPublication(value)).toBeNull();
});
it('accepts the Arabic labels produced by the manual editor without changing them', () => {
  const value = input(); value.questions[0].options![0].key = 'أ'; value.questions[0].options![1].key = 'ب';
  value.questions[0].correct_answer = 'حديد';
  const before = structuredClone(value);
  expect(validateAssessmentPublication(value)).toBeNull();
  expect(value).toEqual(before);
  value.questions[0].options![1].key = 'A';
  expect(validateAssessmentPublication(value)?.message).toContain('فريدة');
});
it('routes missing settings, invalid questions, and missing dates to their owning stage', () => {
  expect(validateAssessmentPublication({ ...input(), title: '' })?.stage).toBe('setup');
  expect(validateAssessmentPublication({ ...input(), questions: [] })?.stage).toBe('review');
  expect(validateAssessmentPublication({ ...input(), startDate: '' })?.stage).toBe('publish');
  expect(validateAssessmentPublication(input())).toBeNull();
});
it.each([0, -1, 1001, Number.NaN, Number.POSITIVE_INFINITY])('rejects invalid points %s without mutating the draft', points => {
  const value = input(); value.questions[0].points = points;
  const before = structuredClone(value);
  expect(validateAssessmentPublication(value)?.stage).toBe('review');
  expect(value).toEqual(before);
});
it('requires unique option keys, one correct answer, and no more than 26 options', () => {
  const value = input(); value.questions[0].options![1].key = 'a';
  expect(validateAssessmentPublication(value)?.message).toContain('فريدة');
  value.questions[0].options![1].key = 'B'; value.questions[0].options![1].is_correct = true;
  expect(validateAssessmentPublication(value)?.message).toContain('واحدة');
  value.questions[0].options = Array.from({ length: 27 }, (_, index) => ({ key: String.fromCharCode(65 + index), text: 'خيار', is_correct: index === 0 }));
  expect(validateAssessmentPublication(value)?.message).toContain('26');
});
it('preserves OCR review binding on revalidation after opening a confirmation', () => {
  const value = input(); const question = value.questions[0]; question.text_source = 'ocr';
  expect(validateAssessmentPublication(value)?.message).toContain('الملف الأصلي');
  question.content_review_fingerprint = contentReviewFingerprint(question);
  expect(validateAssessmentPublication(value)).toBeNull();
  question.question_text = 'نص جديد';
  expect(validateAssessmentPublication(value)?.stage).toBe('review');
});
