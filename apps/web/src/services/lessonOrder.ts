import type { VideoLesson } from '../types/lms';

export function compareNewestLessons(a: VideoLesson, b: VideoLesson): number {
  const aTime = Date.parse(a.uploadedAt);
  const bTime = Date.parse(b.uploadedAt);
  return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0)
    || b.order - a.order || a.id.localeCompare(b.id);
}

export function newestLessonsFirst(lessons: readonly VideoLesson[]): VideoLesson[] {
  return [...lessons].sort(compareNewestLessons);
}
