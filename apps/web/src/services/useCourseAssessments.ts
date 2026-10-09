import { useCallback, useEffect, useState } from 'react';
import { courseService } from './lmsService';
import type { CourseAssessmentRef } from '../types/lms';

/** Load only the open course; one slow/failed unrelated course cannot hide it. */
export function useCourseAssessments(courseId: string | undefined, userId: string | undefined, accessRevision = '') {
  const key = `${userId || ''}:${courseId || ''}:${accessRevision}`;
  const [attempt, setAttempt] = useState(0);
  const [snapshot, setSnapshot] = useState<{ key: string; items: CourseAssessmentRef[]; error: boolean }>();
  const retry = useCallback(() => { setSnapshot(undefined); setAttempt(value => value + 1); }, []);
  useEffect(() => {
    if (!courseId || !userId) return;
    const events = ['lms_courses_updated', 'lms_submission_graded', 'lms_lesson_unlocked', 'lms_payment_updated'];
    const refresh = (event: Event) => {
      // SSE reconnect emits a no-detail payment hint. App reconciles actual
      // entitlements; retry only if that changes accessRevision, not on every
      // reconnect after a429/503. Real review events carry their payload.
      if (event.type === 'lms_payment_updated' && (!(event instanceof CustomEvent) || !event.detail)) return;
      retry();
    };
    for (const event of events) window.addEventListener(event, refresh);
    return () => { for (const event of events) window.removeEventListener(event, refresh); };
  }, [courseId, userId, retry]);
  useEffect(() => {
    if (!courseId || !userId) return;
    const controller = new AbortController();
    let active = true;
    void courseService.getCourseAssessmentRefs(courseId, { signal: controller.signal, skipCache: true })
      .then(items => { if (active) setSnapshot({ key, items, error: false }); })
      .catch(() => { if (active) setSnapshot({ key, items: [], error: true }); });
    return () => { active = false; controller.abort(); };
  }, [courseId, userId, key, attempt]);
  const current = snapshot?.key === key ? snapshot : undefined;
  return {
    items: current?.items || [],
    loading: !!courseId && !!userId && !current,
    error: current?.error || false,
    retry,
  };
}
