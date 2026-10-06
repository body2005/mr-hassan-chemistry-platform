import { afterEach, beforeEach, expect, it, vi } from 'vitest';

beforeEach(() => { vi.resetModules(); localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());

it('publishes reviewed Extract aliases using the API question contract', async () => {
  const fetcher = vi.fn<(input: string, init?: RequestInit) => Promise<Response>>(async () => new Response('{"id":"quiz"}', { status: 201 }));
  vi.stubGlobal('fetch', fetcher);
  const { courseService } = await import('./lmsService');
  await courseService.publishQuizToServer({ course_id: 'course', title: 'Reviewed quiz', idempotency_key: 'qa',
    questions: [{ question_type: 'FILL_BLANK', question_text: 'Mass is measured in ____.', correct_answer: 'kg', points: 2 }] });
  expect(JSON.parse(fetcher.mock.calls[0][1]!.body as string).questions[0].question_type).toBe('fill_in_blank');
});

it('rejects unknown types before any network write instead of guessing multiple-choice', async () => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
  const { courseService } = await import('./lmsService');
  await expect(courseService.publishQuizToServer({ course_id: 'course', title: 'Reviewed quiz', idempotency_key: 'qa',
    questions: [{ question_type: 'unsupported', question_text: 'Review me', points: 2 }] })).rejects.toThrow('نوع سؤال غير مدعوم');
  expect(fetcher).not.toHaveBeenCalled();
});

it('publishes the explicitly selected MCQ option text, not a missing or stale answer', async () => {
  const fetcher = vi.fn<(input: string, init?: RequestInit) => Promise<Response>>(async () => new Response('{"id":"quiz"}', {status:201}));
  vi.stubGlobal('fetch', fetcher);
  const { courseService } = await import('./lmsService');
  await courseService.publishQuizToServer({course_id:'course', title:'MCQ', idempotency_key:'qa',
    questions:[{question_type:'multiple_choice', question_text:'Choose a unit', correct_answer:'stale',
      options:[{key:'A', text:'kg', is_correct:true},{key:'B', text:'s', is_correct:false}], points:2}]});
  expect(JSON.parse(fetcher.mock.calls[0][1]!.body as string).questions[0].correct_answer).toBe('kg');
});

it('rejects a fill blank with no answer before any network request', async () => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
  const { courseService } = await import('./lmsService');
  await expect(courseService.publishQuizToServer({course_id:'course', title:'Fill', idempotency_key:'qa',
    questions:[{question_type:'FILL_BLANK', question_text:'The unit is ____.', correct_answer:'  ', points:2}]}))
    .rejects.toThrow('الإجابة الصحيحة');
  expect(fetcher).not.toHaveBeenCalled();
});
