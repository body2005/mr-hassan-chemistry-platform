import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { McqOptionsEditor } from './McqOptionsEditor';
import { QuestionSourceReview } from './QuestionSourceReview';
import { contentReviewFingerprint } from '../services/quizContentReview';
import type { GeneratedQuestion } from '../types/quiz';

const source: GeneratedQuestion = {
  id: 3, question_type: 'multiple_choice', difficulty: 'easy', topic: '', points: 1,
  question_text: 'Which molecule?', correct_answer: 'A', explanation: '',
  options: [{ key: 'A', text: 'H₂O', is_correct: true }, { key: 'D', text: 'CO₂', is_correct: false }],
};
const handlers = { onCorrect: vi.fn(), onText: vi.fn(), onAdd: vi.fn(), onRemove: vi.fn(), onInitialize: vi.fn() };
let root: Root, host: HTMLDivElement;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  for (const handler of Object.values(handlers)) handler.mockReset();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function editor(question = source, editing = true) {
  await act(async () => root.render(<McqOptionsEditor question={question} editing={editing} {...handlers} />));
}
it('retains nonsequential historical keys and exposes answer/input semantics', async () => {
  await editor();
  const buttons = [...host.querySelectorAll('button[aria-pressed]')];
  expect(buttons.map(button => button.getAttribute('aria-pressed'))).toEqual(['true', 'false']);
  expect(host.querySelector('input[aria-label="نص الخيار D للسؤال 3"]')).not.toBeNull();
  await act(async () => (buttons[1] as HTMLButtonElement).click());
  expect(handlers.onCorrect).toHaveBeenCalledWith(3, 'D');
  expect(source.correct_answer).toBe('A'); // Pure presentation, no mutation.
  expect(host.querySelector('button[title="حذف هذا الخيار"]')).toBeNull(); // Minimum two preserved.
});
it('routes add/remove to existing identities without renumbering them', async () => {
  await editor({ ...source, options: [...source.options!, { key: 'Z', text: 'O₂', is_correct: false }] });
  await act(async () => host.querySelector<HTMLButtonElement>('button[aria-label="حذف الخيار Z للسؤال 3"]')!.click());
  expect(handlers.onRemove).toHaveBeenCalledWith(3, 'Z');
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent?.includes('إضافة خيار جديد'))!.click());
  expect(handlers.onAdd).toHaveBeenCalledWith(3);
});
it('shows initialization for empty choices and respects the26-choice boundary', async () => {
  await editor({ ...source, options: [] });
  await act(async () => host.querySelector('button')!.click());
  expect(handlers.onInitialize).toHaveBeenCalledTimes(1);
  await editor({ ...source, options: Array.from({ length: 26 }, (_, i) => ({ key: String.fromCharCode(65 + i), text: 'Text', is_correct: i === 0 })) });
  expect(host.textContent).not.toContain('إضافة خيار جديد');
  expect(host.querySelectorAll('input')).toHaveLength(26);
});
it('does not expose editing text or deletion in read mode', async () => {
  await editor(source, false);
  expect(host.querySelectorAll('input')).toHaveLength(0);
  expect(host.querySelector('button[title="حذف هذا الخيار"]')).toBeNull();
  expect(host.textContent).toContain('(D)');
});
it('invalidates OCR approval on a changed source fingerprint and requires explicit consent', async () => {
  const onReview = vi.fn();
  const question: GeneratedQuestion = { ...source, text_source: 'ocr', needs_content_review: true, source_page: 2 };
  question.content_review_fingerprint = contentReviewFingerprint(question);
  await act(async () => root.render(<QuestionSourceReview question={question} index={0} onReview={onReview} />));
  expect(host.querySelector<HTMLInputElement>('input')?.checked).toBe(true);
  await act(async () => root.render(<QuestionSourceReview question={{ ...question, question_text: 'Changed' }} index={0} onReview={onReview} />));
  const checkbox = host.querySelector<HTMLInputElement>('input')!;
  expect(checkbox.checked).toBe(false);
  expect(host.textContent).toContain('صفحة 2');
  await act(async () => checkbox.click());
  expect(onReview).toHaveBeenCalledWith(true);
});
