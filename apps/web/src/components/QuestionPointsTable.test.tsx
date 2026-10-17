import { act, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { QuestionPointsTable } from './QuestionPointsTable';
import { canonicalQuestionType } from '../services/questionType';
import type { GeneratedQuestion } from '../types/quiz';

let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  localStorage.clear();
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
it('counts aliases and applies a shared score only to the selected type, preserving transcription approval', async () => {
  const initial = [
    { id: 1, question_type: 'mcq', points: 2, content_review_fingerprint: 'approved-source' },
    { id: 2, question_type: 'multiple_choice', points: 3 },
    { id: 3, question_type: 'essay', points: 9 },
  ] as GeneratedQuestion[];
  let latest = initial;
  function Probe() {
    const [questions, setQuestions] = useState(initial); latest = questions;
    return <QuestionPointsTable questions={questions} disabled={false} onChange={(type, points) => setQuestions(prev => prev.map(question =>
      canonicalQuestionType(question.question_type) === type ? { ...question, points } : question))} />;
  }
  await act(async () => root.render(<Probe />));
  expect(host.textContent).not.toContain('إجابة قصيرة');
  expect(host.textContent).not.toContain('توصيل');
  expect(host.querySelector('input[aria-label*="إجابة قصيرة"]')).toBeNull();
  const row = host.querySelector('tbody tr')!;
  expect(row.querySelector('td')?.textContent).toBe('2');
  const input = row.querySelector('input')!;
  expect(input.value).toBe(''); // Individual scores differ.
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, '7.5');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  expect(latest.map(question => question.points)).toEqual([7.5, 7.5, 9]);
  expect(latest[0].content_review_fingerprint).toBe('approved-source');
  expect(host.querySelector<HTMLInputElement>('tbody tr:nth-child(2) input')?.disabled).toBe(true);
});
