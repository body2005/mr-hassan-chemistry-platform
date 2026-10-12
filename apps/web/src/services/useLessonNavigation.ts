import { useCallback, useEffect, useRef } from 'react';
import type { VideoLesson } from '../types/lms';

/** A player is a history entry inside its originating list, for either role. */
export function useLessonNavigation(lesson: VideoLesson | null, setLesson: (lesson: VideoLesson | null) => void) {
  const known = useRef(new Map<string, VideoLesson>());
  const listPosition = useRef(0);
  const origin = useRef(window.location.hash);
  useEffect(() => {
    if (!lesson) return;
    known.current.set(lesson.id, lesson);
    const state = window.history.state;
    if (!state?.lmsLesson) {
      listPosition.current = window.scrollY;
      origin.current = window.location.hash;
      window.history.pushState({ ...state, lmsLesson: lesson.id, lessonOrigin: origin.current }, '');
      window.scrollTo(0, 0);
    } else if (state.lmsLesson !== lesson.id) {
      // Playlist changes stay in this player entry; Back always returns to the list.
      window.history.replaceState({ ...state, lmsLesson: lesson.id }, '');
    }
  }, [lesson]);
  useEffect(() => {
    const navigate = () => {
      const state = window.history.state;
      const selected = state?.lessonOrigin === window.location.hash ? known.current.get(state?.lmsLesson) : undefined;
      setLesson(selected ?? null);
      if (!selected && window.location.hash === origin.current) {
        requestAnimationFrame(() => window.scrollTo(0, listPosition.current));
      }
    };
    window.addEventListener('popstate', navigate);
    return () => {
      window.removeEventListener('popstate', navigate);
    };
  }, [setLesson]);
  return useCallback(() => {
    if (window.history.state?.lmsLesson) window.history.back();
    else setLesson(null);
  }, [setLesson]);
}
