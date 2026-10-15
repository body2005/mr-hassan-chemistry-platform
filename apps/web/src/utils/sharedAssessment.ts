export type SharedAssessment = { courseId: string; assessmentId: string; kind: 'quiz' | 'assignment' };
const storageKey = 'lms_shared_assessment';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function valid(value: unknown): value is SharedAssessment {
  if (!value || typeof value !== 'object') return false;
  const target = value as Partial<SharedAssessment>;
  return typeof target.courseId === 'string' && uuid.test(target.courseId)
    && typeof target.assessmentId === 'string' && uuid.test(target.assessmentId)
    && (target.kind === 'quiz' || target.kind === 'assignment');
}

export function sharedAssessmentUrl(target: SharedAssessment): string {
  const query = new URLSearchParams({ course: target.courseId, assessment: target.assessmentId, kind: target.kind });
  return `#mycourses?${query.toString()}`;
}

/** A link is only a navigation intent; the receiving view checks server access. */
export function readSharedAssessment(): SharedAssessment | null {
  try {
    const [page, query = ''] = window.location.hash.slice(1).split('?');
    const params = new URLSearchParams(query);
    if (params.has('assessment')) {
      const target = { courseId: params.get('course'), assessmentId: params.get('assessment'), kind: params.get('kind') };
      if (page.toLowerCase() === 'mycourses' && !params.has('lesson') && valid(target)) {
        sessionStorage.setItem(storageKey, JSON.stringify(target));
        return target;
      }
      clearSharedAssessment();
      return null;
    }
    // Preserve a target through sign-in, never reopen it on unrelated navigation.
    if (!['', 'auth', 'landing'].includes(page.toLowerCase()) || params.has('lesson')) return null;
    const saved: unknown = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
    return valid(saved) ? saved : null;
  } catch { return null; }
}

export function clearSharedAssessment(): void {
  try { sessionStorage.removeItem(storageKey); } catch { /* Navigation still works without storage. */ }
}
