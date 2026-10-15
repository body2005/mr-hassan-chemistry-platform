import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { Course, VideoLesson } from '../types/lms';

function playerHash(lesson: VideoLesson) {
  const [page, query = ''] = window.location.hash.split('?');
  const params = new URLSearchParams(query);
  params.set('course', lesson.courseId);
  params.set('lesson', lesson.id);
  return `${page}?${params}`;
}

function listHash(hash: string) {
  const [page, query = ''] = hash.split('?');
  const params = new URLSearchParams(query);
  for (const key of ['course', 'lesson', 'discussion']) params.delete(key);
  return `${page}${params.size ? `?${params}` : ''}`;
}

interface RestoreOptions {
  userId?: string;
  courses: Course[];
  onRestore: (course: Course) => void;
  canRestore?: (lesson: VideoLesson, course: Course) => Promise<boolean>;
}

/** A player is a history entry inside its originating list, for either role. */
export function useLessonNavigation(lesson: VideoLesson | null, setLesson: (lesson: VideoLesson | null) => void, options: RestoreOptions) {
  const [restoring, setRestoring] = useState(() => Boolean(new URLSearchParams(window.location.hash.split('?')[1] || '').get('lesson')));
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
      origin.current = listHash(window.location.hash);
      const hash = playerHash(lesson);
      // The URL survives a reload even when a mobile browser discards history.state.
      // It contains identifiers only; admission is rechecked when restoring.
      window.history.pushState({ ...state, ...selection, lessonOrigin: hash, lessonListHash: origin.current,
        lessonCanGoBack: true, lessonListPosition: listPosition.current }, '', hash);
      window.scrollTo(0, 0);
    } else if (state.lmsLesson !== lesson.id || state.lessonCourse !== lesson.courseId) {
      // Playlist changes stay in this player entry; Back always returns to the list.
      const hash = playerHash(lesson);
      window.history.replaceState({ ...state, ...selection, lessonOrigin: hash }, '', hash);
    }
  }, [lesson, options.userId]);
  const restore = useCallback(async () => {
    const revision = ++restoreRevision.current;
    setRestoring(false);
    const { lesson: current, options: settings } = latest.current;
    if (!settings.userId) return;
    const hash = window.location.hash;
    const params = new URLSearchParams(hash.split('?')[1] || '');
    const state = window.history.state?.lmsLesson ? window.history.state : {
      lmsLesson: params.get('lesson'), lessonCourse: params.get('course'), lessonUser: settings.userId,
      lessonOrigin: hash, lessonListHash: listHash(hash), lessonCanGoBack: false,
    };
    if (!state.lmsLesson || state.lessonOrigin !== hash || state.lessonUser !== settings.userId) return;
    origin.current = state.lessonListHash || listHash(state.lessonOrigin);
    listPosition.current = Number.isFinite(state.lessonListPosition) ? state.lessonListPosition : 0;
    if (current?.id === state.lmsLesson) return;
    // Only identifiers survive Refresh. Resolve content from this account's
    // current catalog; history state is never an authorization grant.
    const course = settings.courses.find(item => item.id === state.lessonCourse);
    const selected = course?.lessons.find(item => item.id === state.lmsLesson);
    if (!course || !selected) return;
    setRestoring(true);
    try {
      const allowed = !settings.canRestore || await settings.canRestore(selected, course);
      if (!allowed || restoreRevision.current !== revision || latest.current.options.userId !== settings.userId ||
          window.location.hash !== hash || (window.history.state?.lessonUser && window.history.state.lessonUser !== settings.userId)) return;
      if (!window.history.state?.lmsLesson) window.history.replaceState(state, '', hash);
      known.current.set(selected.id, selected);
      latest.current.options.onRestore(course);
      setLesson(selected);
    } catch { /* Keep the list usable if admission cannot be verified. */ }
    finally { if (restoreRevision.current === revision) setRestoring(false); }
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
  const close = useCallback(() => {
    const state = window.history.state;
    if (state?.lmsLesson && state.lessonCanGoBack === false) {
      window.history.replaceState(null, '', state.lessonListHash || listHash(window.location.hash));
      setLesson(null);
    } else if (state?.lmsLesson) window.history.back();
    else setLesson(null);
  }, [setLesson]);
  return { close, restoring };
}
