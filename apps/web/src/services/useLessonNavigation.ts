import { useCallback, useEffect, useLayoutEffect, useRef } from 'react';
import type { Course, VideoLesson } from '../types/lms';

interface RestoreOptions {
  userId?: string;
  courses: Course[];
  onRestore: (course: Course) => void;
  canRestore?: (lesson: VideoLesson, course: Course) => Promise<boolean>;
}

/** A player is a history entry inside its originating list, for either role. */
export function useLessonNavigation(lesson: VideoLesson | null, setLesson: (lesson: VideoLesson | null) => void, options: RestoreOptions) {
  const known = useRef(new Map<string, VideoLesson>());
  const latest = useRef({ lesson, options });
  useLayoutEffect(() => { latest.current = { lesson, options }; }, [lesson, options]);
  const restoreRevision = useRef(0);
  const listPosition = useRef(0);
  const origin = useRef(window.location.hash);
  useEffect(() => {
    if (!lesson) return;
    known.current.set(lesson.id, lesson);
    const state = window.history.state;
    const selection = { lmsLesson: lesson.id, lessonCourse: lesson.courseId, lessonUser: options.userId };
    if (!state?.lmsLesson || state.lessonOrigin !== window.location.hash || state.lessonUser !== options.userId) {
      listPosition.current = window.scrollY;
      origin.current = window.location.hash;
      window.history.pushState({ ...state, ...selection, lessonOrigin: origin.current, lessonListPosition: listPosition.current }, '');
      window.scrollTo(0, 0);
    } else if (state.lmsLesson !== lesson.id || state.lessonCourse !== lesson.courseId) {
      // Playlist changes stay in this player entry; Back always returns to the list.
      window.history.replaceState({ ...state, ...selection }, '');
    }
  }, [lesson, options.userId]);
  const restore = useCallback(async () => {
    const revision = ++restoreRevision.current;
    const state = window.history.state;
    const { lesson: current, options: settings } = latest.current;
    if (!state?.lmsLesson || state.lessonOrigin !== window.location.hash || state.lessonUser !== settings.userId || !settings.userId) return;
    origin.current = state.lessonOrigin;
    listPosition.current = Number.isFinite(state.lessonListPosition) ? state.lessonListPosition : 0;
    if (current?.id === state.lmsLesson) return;
    // Only identifiers survive Refresh. Resolve content from this account's
    // current catalog; history state is never an authorization grant.
    const course = settings.courses.find(item => item.id === state.lessonCourse);
    const selected = course?.lessons.find(item => item.id === state.lmsLesson);
    if (!course || !selected) return;
    try {
      const allowed = !settings.canRestore || await settings.canRestore(selected, course);
      if (!allowed || restoreRevision.current !== revision || window.history.state?.lmsLesson !== selected.id ||
          window.history.state?.lessonUser !== settings.userId || latest.current.options.userId !== settings.userId ||
          window.location.hash !== state.lessonOrigin) return;
      known.current.set(selected.id, selected);
      latest.current.options.onRestore(course);
      setLesson(selected);
    } catch { /* Keep the list usable if admission cannot be verified. */ }
  }, [setLesson]);
  useEffect(() => {
    known.current.clear();
    void restore();
    return () => { restoreRevision.current++; };
  }, [options.courses, options.userId, restore]);
  useEffect(() => {
    const navigate = () => {
      const state = window.history.state;
      restoreRevision.current++;
      const selected = state?.lessonOrigin === window.location.hash && state?.lessonUser === latest.current.options.userId
        ? known.current.get(state?.lmsLesson) : undefined;
      const course = selected && latest.current.options.courses.find(item => item.id === selected.courseId);
      const needsAdmission = Boolean(latest.current.options.canRestore);
      if (selected && course && !needsAdmission) {
        latest.current.options.onRestore(course);
        setLesson(selected);
      } else {
        setLesson(null);
        void restore();
      }
      if (!state?.lmsLesson && window.location.hash === origin.current) {
        requestAnimationFrame(() => window.scrollTo(0, listPosition.current));
      }
    };
    window.addEventListener('popstate', navigate);
    return () => {
      window.removeEventListener('popstate', navigate);
    };
  }, [setLesson, restore]);
  return useCallback(() => {
    if (window.history.state?.lmsLesson) window.history.back();
    else setLesson(null);
  }, [setLesson]);
}
