import type { Course } from '../types/lms';

export type CatalogGrade = '' | Course['academicYear'];
export const catalogGrades: CatalogGrade[] = ['', '1st_secondary', '2nd_secondary', '3rd_secondary'];

export function readCatalogState() {
  const params = new URLSearchParams(window.location.search);
  const grade = params.get('catalog_grade') || '';
  return { query: (params.get('catalog_search') || '').normalize('NFKC').slice(0, 100),
    grade: catalogGrades.includes(grade as CatalogGrade) ? grade as CatalogGrade : '' as CatalogGrade };
}

export function saveCatalogState(query: string, grade: CatalogGrade) {
  const url = new URL(window.location.href);
  for (const [key, value] of [['catalog_search', query], ['catalog_grade', grade]]) {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }
  // Retain routing/reset fragments and unrelated query parameters.
  window.history.replaceState(window.history.state, '', url);
}

export function filterCatalog(courses: Course[], query: string, grade: CatalogGrade) {
  const normalized = query.normalize('NFKC').trim().toLocaleLowerCase();
  return courses.filter(course => (!grade || course.academicYear === grade)
    && (!normalized || [course.title, course.description, course.subject, course.teacherName]
      .some(value => value?.normalize('NFKC').toLocaleLowerCase().includes(normalized))));
}

export type EnrollmentIntent = Pick<Course, 'id' | 'title' | 'academicYear'>;
const intentKey = 'lms_catalog_enrollment_intent';
export function readEnrollmentIntent(): EnrollmentIntent | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(intentKey) || 'null');
    return value && typeof value.id === 'string' && value.id.length <= 100
      && typeof value.title === 'string' && value.title.length <= 200
      && catalogGrades.slice(1).includes(value.academicYear) ? value : null;
  } catch { return null; }
}
export function saveEnrollmentIntent(value: EnrollmentIntent | null) {
  // Public catalog metadata only: no credential, entitlement or auth state.
  try {
    if (value) sessionStorage.setItem(intentKey, JSON.stringify(value));
    else sessionStorage.removeItem(intentKey);
  } catch { /* Selection still exists in memory when browser storage is blocked. */ }
}
