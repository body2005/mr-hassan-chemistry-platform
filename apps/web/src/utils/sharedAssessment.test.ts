import { afterEach, beforeEach, expect, it } from 'vitest';
import { clearSharedAssessment, readSharedAssessment, sharedAssessmentUrl } from './sharedAssessment';
import { readSharedLesson } from './sharedLesson';
const target = { courseId: '11111111-1111-4111-8111-111111111111', assessmentId: '22222222-2222-4222-8222-222222222222', kind: 'quiz' as const };
beforeEach(() => { sessionStorage.clear(); window.history.replaceState(null, '', '/#mycourses'); });
afterEach(() => sessionStorage.clear());
it('roundtrips a course-specific quiz or assignment URL', () => {
  for (const kind of ['quiz', 'assignment'] as const) {
    const expected = { ...target, kind };
    window.history.replaceState(null, '', sharedAssessmentUrl(expected));
    expect(readSharedAssessment()).toEqual(expected);
  }
});
it('retains the target through sign-in then clears it after handling', () => {
  window.history.replaceState(null, '', sharedAssessmentUrl(target)); expect(readSharedAssessment()).toEqual(target);
  window.history.replaceState(null, '', '#auth'); expect(readSharedAssessment()).toEqual(target);
  clearSharedAssessment(); expect(readSharedAssessment()).toBeNull();
});
it.each(['#mycourses?assessment=invalid&kind=quiz', `#mycourses?course=${target.courseId}&assessment=${target.assessmentId}&kind=unknown`, `#payments?course=${target.courseId}&assessment=${target.assessmentId}&kind=quiz`])('rejects malformed and unsupported targets: %s', hash => {
  window.history.replaceState(null, '', hash); expect(readSharedAssessment()).toBeNull();
});
it('does not reuse a stale target when navigating to another page or a lesson link', () => {
  window.history.replaceState(null, '', sharedAssessmentUrl(target)); readSharedAssessment();
  window.history.replaceState(null, '', '#mycourses'); expect(readSharedAssessment()).toBeNull();
  window.history.replaceState(null, '', `#mycourses?course=${target.courseId}&lesson=${target.assessmentId}`);
  expect(readSharedLesson()).toEqual({ courseId: target.courseId, lessonId: target.assessmentId });
  expect(readSharedAssessment()).toBeNull();
});
it('an assessment link does not restore an older saved video link', () => {
  window.history.replaceState(null, '', `#mycourses?course=${target.courseId}&lesson=${target.assessmentId}`); readSharedLesson();
  window.history.replaceState(null, '', sharedAssessmentUrl(target));
  expect(readSharedLesson()).toBeNull(); expect(readSharedAssessment()).toEqual(target);
});
