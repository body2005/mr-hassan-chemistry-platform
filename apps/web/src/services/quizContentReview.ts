import type { GeneratedQuestion } from '../types/quiz';

export function requiresContentReview(question: GeneratedQuestion): boolean {
  return question.needs_content_review === true || question.text_source === 'ocr';
}

// Exact content identity, not a confidence score or an assertion that OCR is
// correct. Bind the teacher's acknowledgement to wording, type and option
// order. Scores/correct-answer selection do not alter source transcription.
export function contentReviewFingerprint(question: GeneratedQuestion): string {
  return JSON.stringify([question.question_text, question.question_type,
    (question.options || []).map(option => [option.key, option.text])]);
}

export function hasContentReview(question: GeneratedQuestion): boolean {
  return !requiresContentReview(question) || question.content_review_fingerprint === contentReviewFingerprint(question);
}
