export type SharedLesson = { courseId: string; lessonId: string };
const key = 'lms_shared_lesson';
export function readSharedLesson(): SharedLesson | null {
  try {
    const [page, query = ''] = window.location.hash.slice(1).split('?');
    const params = new URLSearchParams(query);
    const courseId = params.get('course');
    const lessonId = params.get('lesson');
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (page.toLowerCase() === 'mycourses' && courseId && lessonId && uuid.test(courseId) && uuid.test(lessonId)) {
      const target = { courseId, lessonId };
      sessionStorage.setItem(key, JSON.stringify(target));
      return target;
    }
    const saved = JSON.parse(sessionStorage.getItem(key) || 'null') as SharedLesson | null;
    return saved && uuid.test(saved.courseId) && uuid.test(saved.lessonId) ? saved : null;
  } catch { return null; }
}
export function clearSharedLesson() {
  try { sessionStorage.removeItem(key); } catch { /* Navigation still works without storage. */ }
}
